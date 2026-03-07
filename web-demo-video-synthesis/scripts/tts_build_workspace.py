#!/usr/bin/env python3
"""在 workspace 中生成分段音频 + timeline.json（主键），并可选混出总音轨。

定位（workspace 协作范式）：
- 让 `web-demo-video-synthesis` 可以独立发布：不依赖仓库其他目录。
- 人类与 Codex 共同维护 workspace 文件；该脚本只负责“把 cues + key 变成可审计产物”。

产物（默认写到 workspace）：
- `segment_audio/seg_000.wav` ...：每段一个音频文件
- `timeline/timeline.json`：时间轴主键（segments + scroll_events）
- 可选 `audio/timeline_audio.mp3`：按 timeline 混音后的旁白音轨
- `workspace_meta.json`：记录 cues/tts 参数 hash，防止静默复用旧音频

失败策略：
- cues 变更/tts 参数变更时，默认直接失败，要求显式 `--force-tts true`。
- 任意段落 TTS 失败直接失败（可定位到 seg_index）。
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
import wave
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

import requests


@dataclass
class ISIRestConfig:
    """阿里云 ISI REST TTS 配置。"""

    appkey: str
    token: str
    voice: str
    sample_rate: int
    fmt: str


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="TTS cues -> workspace segment_audio + timeline.json")
    parser.add_argument("--workspace-dir", required=True, help="workspace 目录")
    parser.add_argument("--cues-json", required=True, help="cues.json 路径（只含台词）")
    parser.add_argument("--key-json", required=True, help="key.json 路径（Appkey + AccessToken）")
    parser.add_argument("--voice", default="emily", help="音色（ISI REST），例如 emily / zhida")
    parser.add_argument("--sample-rate", type=int, default=48000, help="采样率")
    parser.add_argument("--format", default="wav", help="音频格式（建议 wav，便于本地测时长）")
    parser.add_argument("--inter-gap-sec", type=float, default=2.5, help="段间静默秒数")
    parser.add_argument("--scroll-lag-sec", type=float, default=1.2, help="滚动提前量秒数")
    parser.add_argument(
        "--force-tts",
        action=argparse.BooleanOptionalAction,
        default=False,
        help="若 cues 或 tts 参数变化，是否强制重生成所有 segment_audio（默认 false 直接失败）",
    )
    parser.add_argument(
        "--mix-audio",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="是否按 timeline 混音输出 audio/timeline_audio.mp3（默认 true）",
    )
    parser.add_argument("--requests-timeout-sec", type=int, default=120, help="TTS HTTP 超时秒数")
    return parser.parse_args()


def read_json(path: Path) -> Dict[str, Any]:
    obj = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(obj, dict):
        raise ValueError(f"JSON 顶层必须是对象: {path}")
    return obj


def write_json(path: Path, obj: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def compute_cues_signature(cues_payload: Dict[str, Any], tts_cfg: ISIRestConfig) -> str:
    """把 cues + tts 参数固化为签名，防止静默复用旧音频。"""

    cues = cues_payload.get("cues")
    if not isinstance(cues, list):
        raise ValueError("cues.json 缺少 cues 数组")

    norm = {
        "cues": [
            {
                "id": (c.get("id") if isinstance(c, dict) else None),
                "text": (c.get("text") if isinstance(c, dict) else None),
                "wait": (c.get("wait") if isinstance(c, dict) else None),
            }
            for c in cues
        ],
        "tts": {
            "voice": tts_cfg.voice,
            "sample_rate": tts_cfg.sample_rate,
            "format": tts_cfg.fmt,
        },
    }
    return sha256_text(json.dumps(norm, ensure_ascii=False, sort_keys=True))


def load_isi_rest_config(key_json: Path, voice: str, sample_rate: int, fmt: str) -> ISIRestConfig:
    cfg = read_json(key_json)
    appkey = cfg.get("appkey") or cfg.get("app_key") or cfg.get("api_key")
    token = (
        cfg.get("token")
        or cfg.get("access_token")
        or cfg.get("AccessToken")
        or cfg.get("accessToken")
    )
    if not appkey or not token:
        raise ValueError("key.json 缺少 appkey 或 token/access_token")
    return ISIRestConfig(
        appkey=str(appkey).strip(),
        token=str(token).strip(),
        voice=str(voice).strip(),
        sample_rate=int(sample_rate),
        fmt=str(fmt).strip(),
    )


def normalize_cues(cues_payload: Dict[str, Any]) -> List[Dict[str, Any]]:
    raw = cues_payload.get("cues")
    if not isinstance(raw, list) or not raw:
        raise ValueError("cues.json 的 cues 必须是非空数组")
    out: List[Dict[str, Any]] = []
    for idx, item in enumerate(raw):
        if not isinstance(item, dict):
            raise ValueError(f"cues[{idx}] 必须是对象")
        text = str(item.get("text", "")).strip()
        if not text:
            raise ValueError(f"cues[{idx}].text 不能为空")
        cue_id = item.get("id")
        if cue_id is not None and not str(cue_id).strip():
            raise ValueError(f"cues[{idx}].id 不能为空字符串")
        wait = item.get("wait")
        if wait is not None:
            try:
                wait_int = int(wait)
            except Exception as exc:  # noqa: BLE001
                raise ValueError(f"cues[{idx}].wait 必须是整数毫秒") from exc
            if wait_int <= 0:
                raise ValueError(f"cues[{idx}].wait 必须 > 0")
        out.append(
            {
                "idx": idx,
                "id": (str(cue_id).strip() if cue_id is not None else None),
                "text": text,
                "wait_ms": (int(wait) if wait is not None else None),
            }
        )
    return out


def wav_duration_seconds(path: Path) -> float:
    """计算 wav 时长（秒）。

    重要：不要使用 `wf.getnframes()` 直接信任 header。
    某些 TTS 服务会返回“header 标注的 data chunk size 大于实际文件长度”的 wav：
    - `wave` 会返回被 header 夸大的 nframes；
    - 但解码器（如 ffmpeg）会以实际可读数据为准。

    因此这里用 `readframes()` 逐块读取到 EOF，并按实际读取到的字节数统计 frame 数，
    以获得“可播放音频”的真实时长。
    """

    with wave.open(str(path), "rb") as wf:
        rate = int(wf.getframerate())
        if rate <= 0:
            raise RuntimeError(f"非法采样率: {rate}")
        nch = int(wf.getnchannels())
        sw = int(wf.getsampwidth())
        bytes_per_frame = nch * sw
        if bytes_per_frame <= 0:
            raise RuntimeError(f"非法 bytes_per_frame: nch={nch}, sampwidth={sw}")

        total_frames = 0
        # 每次按 ~1 秒读取，避免一次性读取超大数据
        chunk_frames = max(1024, rate)
        while True:
            data = wf.readframes(chunk_frames)
            if not data:
                break
            total_frames += len(data) // bytes_per_frame

        return float(total_frames / rate)


def synthesize_isi_rest(cfg: ISIRestConfig, text: str, out_wav: Path, timeout_sec: int) -> Dict[str, Any]:
    """调用阿里云 ISI REST TTS，输出 wav。"""

    url = "https://nls-gateway-cn-shanghai.aliyuncs.com/stream/v1/tts"
    params = {
        "appkey": cfg.appkey,
        "token": cfg.token,
        "text": text,
        "format": cfg.fmt,
        "sample_rate": str(cfg.sample_rate),
        "voice": cfg.voice,
    }
    resp = requests.get(url, params=params, timeout=timeout_sec)
    content_type = resp.headers.get("Content-Type", "")
    if resp.status_code != 200:
        raise RuntimeError(f"ISI REST HTTP 失败: status={resp.status_code}, body={resp.text[:500]}")
    if "audio" not in content_type.lower():
        raise RuntimeError(f"ISI REST 返回非音频: content_type={content_type}, body={resp.text[:500]}")
    out_wav.write_bytes(resp.content)
    return {"status_code": resp.status_code, "content_type": content_type, "audio_bytes": len(resp.content)}


def build_timeline(
    cues: List[Dict[str, Any]],
    segment_paths: List[Path],
    segment_durations: List[float],
    inter_gap_sec: float,
    scroll_lag_sec: float,
) -> Dict[str, Any]:
    if not (len(cues) == len(segment_paths) == len(segment_durations)):
        raise ValueError("cues/segment_paths/segment_durations 长度不一致")

    segments: List[Dict[str, Any]] = []
    scroll_events: List[Dict[str, Any]] = []
    cursor = 0.0
    for i, cue in enumerate(cues):
        duration = float(segment_durations[i])
        start = cursor
        end = start + duration
        # 关键规则（解决“滚动就位慢于开声”）：
        # - 滚动动作在上一段语音结束后立即触发（scroll_action_at = end）
        # - 下一段开声至少等待 max(inter_gap_sec, scroll_lag_sec)
        #   其中 scroll_lag_sec 在此语义下表示“滚动后最小等待时间/缓冲预算”
        effective_gap_sec = max(float(inter_gap_sec), float(scroll_lag_sec))
        next_start = end + effective_gap_sec

        segments.append(
            {
                "seg_index": i,
                "cue_index": cue["idx"],
                "cue_id": cue.get("id"),
                "text": cue["text"],
                "source_wait_ms": cue.get("wait_ms"),
                "start_sec": round(start, 3),
                "end_sec": round(end, 3),
                "duration_sec": round(duration, 3),
                "silence_after_sec": round(effective_gap_sec, 3),
                "recommended_hold_sec": round(duration + effective_gap_sec, 3),
                "inter_gap_sec": round(float(inter_gap_sec), 3),
                "scroll_lag_sec": round(float(scroll_lag_sec), 3),
                "audio_path": str(segment_paths[i].resolve()),
            }
        )

        if i < len(cues) - 1:
            scroll_at = end
            scroll_events.append(
                {
                    "after_seg_index": i,
                    "to_seg_index": i + 1,
                    "scroll_action_at_sec": round(scroll_at, 3),
                    "next_voice_start_sec": round(next_start, 3),
                    "scroll_lag_sec": round(float(scroll_lag_sec), 3),
                    "inter_gap_sec": round(float(inter_gap_sec), 3),
                    "effective_gap_sec": round(effective_gap_sec, 3),
                }
            )
        cursor = next_start

    return {
        "segments": segments,
        "scroll_events": scroll_events,
        "timeline_total_sec": round(segments[-1]["end_sec"], 3) if segments else 0.0,
        "schedule_total_sec": round(cursor, 3),
    }


def run_mix_audio_from_timeline(timeline_json: Path, out_mp3: Path) -> None:
    script_dir = Path(__file__).resolve().parent
    mix_py = script_dir / "mix_audio_from_timeline.py"
    if not mix_py.exists():
        raise FileNotFoundError(f"缺少混音脚本: {mix_py}")
    cmd = [
        sys.executable,
        str(mix_py),
        "--timeline",
        str(timeline_json),
        "--output",
        str(out_mp3),
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        raise RuntimeError(f"混音失败: {proc.stderr[:2000]}")


def main() -> None:
    args = parse_args()
    ws = Path(args.workspace_dir).resolve()
    cues_path = Path(args.cues_json).resolve()
    key_path = Path(args.key_json).resolve()

    ws_inputs = ws / "inputs"
    ws_secrets = ws / "secrets"
    ws_seg = ws / "segment_audio"
    ws_timeline_dir = ws / "timeline"
    ws_audio_dir = ws / "audio"
    for d in (ws_inputs, ws_secrets, ws_seg, ws_timeline_dir, ws_audio_dir):
        d.mkdir(parents=True, exist_ok=True)

    cues_payload = read_json(cues_path)
    isi_cfg = load_isi_rest_config(
        key_json=key_path,
        voice=args.voice,
        sample_rate=args.sample_rate,
        fmt=args.format,
    )

    signature = compute_cues_signature(cues_payload, isi_cfg)
    meta_path = ws / "workspace_meta.json"
    old_sig: Optional[str] = None
    if meta_path.exists():
        old = read_json(meta_path)
        old_sig = old.get("cues_tts_signature")

    if old_sig and old_sig != signature and not args.force_tts:
        raise RuntimeError(
            "检测到 cues 或 TTS 参数变更，但未开启 --force-tts。"
            "为避免静默复用旧音频，本次直接失败。"
        )

    cues = normalize_cues(cues_payload)

    # 固化 inputs 快照（key 属于 secrets，不复制）
    (ws_inputs / "cues.json").write_text(json.dumps(cues_payload, ensure_ascii=False, indent=2), encoding="utf-8")

    segment_paths: List[Path] = []
    segment_durations: List[float] = []

    for i, cue in enumerate(cues):
        out_wav = ws_seg / f"seg_{i:03d}.wav"
        if out_wav.exists() and not args.force_tts and old_sig == signature:
            dur = wav_duration_seconds(out_wav)
            segment_paths.append(out_wav)
            segment_durations.append(dur)
            # 仍然更新/修正 duration（有些 wav header 可能不可信，需以可读数据为准）
            meta_p = ws_seg / f"seg_{i:03d}.meta.json"
            if meta_p.exists():
                try:
                    meta = read_json(meta_p)
                    meta["duration_sec"] = round(dur, 3)
                    write_json(meta_p, meta)
                except Exception:  # noqa: BLE001
                    # 审计文件不应阻断主流程；但 duration 会在 timeline 中体现
                    pass
            continue

        # 需要重生成（force 或首次生成）
        info = synthesize_isi_rest(isi_cfg, cue["text"], out_wav, timeout_sec=int(args.requests_timeout_sec))
        dur = wav_duration_seconds(out_wav)
        segment_paths.append(out_wav)
        segment_durations.append(dur)
        # 落盘一份 per-seg meta（便于审计）
        write_json(
            ws_seg / f"seg_{i:03d}.meta.json",
            {
                "seg_index": i,
                "cue_id": cue.get("id"),
                "audio_path": str(out_wav.resolve()),
                "duration_sec": round(dur, 3),
                "isi_rest": info,
            },
        )

    timeline = build_timeline(
        cues=cues,
        segment_paths=segment_paths,
        segment_durations=segment_durations,
        inter_gap_sec=float(args.inter_gap_sec),
        scroll_lag_sec=float(args.scroll_lag_sec),
    )
    timeline_path = ws_timeline_dir / "timeline.json"
    write_json(timeline_path, timeline)

    if args.mix_audio:
        out_mp3 = ws_audio_dir / "timeline_audio.mp3"
        run_mix_audio_from_timeline(timeline_path, out_mp3)

    write_json(
        meta_path,
        {
            "workspace_dir": str(ws),
            "cues_json": str(cues_path),
            "key_json": str(key_path),
            "tts": {
                "provider": "isi_rest",
                "voice": isi_cfg.voice,
                "sample_rate": isi_cfg.sample_rate,
                "format": isi_cfg.fmt,
            },
            "cues_tts_signature": signature,
            "segment_count": len(cues),
        },
    )

    print(
        json.dumps(
            {
                "workspace_dir": str(ws),
                "timeline_json": str(timeline_path),
                "segment_audio_dir": str(ws_seg),
                "timeline_audio": str((ws_audio_dir / "timeline_audio.mp3").resolve()) if args.mix_audio else None,
                "segment_count": len(cues),
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
