#!/usr/bin/env python3
"""用 macOS `say` 在 workspace 中生成分段音频 + timeline.json（主键），并可选混出总音轨。

定位
----
`web-demo-video-synthesis` 的默认 TTS 路线是「先进的 TTS API」（本 skill 默认实现为阿里云 ISI REST），
这通常能得到更自然、更稳定的配音质量，但需要人类提供 `key.json`（不入库）。

为了在 **没有任何密钥** 的情况下也能快速跑通端到端流程（网页录屏、字幕、合成等），本脚本提供一个可选的
本地 TTS 路线：使用 macOS 系统自带 `say` 来逐段生成语音。

产物（写入 workspace）
---------------------
- `segment_audio/seg_000.wav` ...：每段一个音频文件
- `timeline/timeline.json`：时间轴主键（segments + scroll_events）
- 可选 `audio/timeline_audio.mp3`：按 timeline 混音后的旁白音轨
- `workspace_meta.json`：记录 cues/tts 参数 hash，防止静默复用旧音频

失败策略（学术级：正确失败）
--------------------------
- cues 或 TTS 参数变更时，默认直接失败，要求显式 `--force-tts true`。
- 任意段落合成失败直接失败（可定位 seg_index）。

依赖
----
- macOS `say`（系统自带）
- `ffmpeg`（用于把 say 输出转成目标 wav，以及后续混音）
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
import wave
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional


@dataclass(frozen=True)
class MacSayConfig:
    """macOS say 的关键参数集合（用于签名与审计）。"""

    voice: str
    rate: Optional[int]
    sample_rate: int


def parse_args() -> argparse.Namespace:
    """解析命令行参数。"""

    parser = argparse.ArgumentParser(description="macOS say TTS cues -> workspace segment_audio + timeline.json")
    parser.add_argument("--workspace-dir", required=True, help="workspace 目录")
    parser.add_argument("--cues-json", required=True, help="cues.json 路径（只含台词）")
    parser.add_argument("--voice", default="Tingting", help="macOS say 音色（例如 Tingting / Samantha）")
    parser.add_argument("--rate", type=int, default=None, help="say 语速（可选，单位 words per minute）")
    parser.add_argument("--sample-rate", type=int, default=48000, help="输出 wav 采样率")
    parser.add_argument("--inter-gap-sec", type=float, default=2.0, help="段间静默秒数")
    parser.add_argument("--scroll-lag-sec", type=float, default=1.2, help="滚动后到下一段开声的最小等待预算秒数")
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
    parser.add_argument("--ffmpeg", default="ffmpeg", help="ffmpeg 可执行文件名/路径")
    return parser.parse_args()


def read_json(path: Path) -> Dict[str, Any]:
    """读取并校验 JSON 顶层对象。"""

    obj = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(obj, dict):
        raise ValueError(f"JSON 顶层必须是对象: {path}")
    return obj


def write_json(path: Path, obj: Dict[str, Any]) -> None:
    """写入 JSON（UTF-8，indent=2）。"""

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")


def sha256_text(text: str) -> str:
    """对文本做 sha256。"""

    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def normalize_cues(cues_payload: Dict[str, Any]) -> List[Dict[str, Any]]:
    """规范化 cues.json（仅保留必要字段，严格校验）。"""

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


def compute_signature(cues_payload: Dict[str, Any], tts_cfg: MacSayConfig) -> str:
    """把 cues + TTS 参数固化为签名，防止静默复用旧音频。"""

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
            "provider": "macos_say",
            "voice": tts_cfg.voice,
            "rate": tts_cfg.rate,
            "sample_rate": tts_cfg.sample_rate,
        },
    }
    return sha256_text(json.dumps(norm, ensure_ascii=False, sort_keys=True))


def wav_duration_seconds(path: Path) -> float:
    """读取 wav 时长（秒）。"""

    with wave.open(str(path), "rb") as wf:
        frames = wf.getnframes()
        rate = wf.getframerate()
        if rate <= 0:
            raise RuntimeError(f"非法采样率: {rate}")
        return float(frames / rate)


def ensure_cmd(cmd: str) -> str:
    """确保系统存在该命令。"""

    if shutil.which(cmd):
        return cmd
    raise RuntimeError(f"未找到可执行文件: {cmd}")


def synthesize_say_to_wav(
    *,
    text: str,
    out_wav: Path,
    cfg: MacSayConfig,
    ffmpeg_bin: str,
) -> Dict[str, Any]:
    """用 say 生成临时 AIFF，再用 ffmpeg 转为目标 WAV（单声道、指定采样率）。"""

    ensure_cmd("say")
    ensure_cmd(ffmpeg_bin)

    out_wav.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as td:
        aiff = Path(td) / "seg.aiff"
        say_cmd: List[str] = ["say", "-v", cfg.voice, "-o", str(aiff)]
        if cfg.rate is not None:
            say_cmd.extend(["-r", str(cfg.rate)])
        say_cmd.append(text)

        proc = subprocess.run(say_cmd, capture_output=True, text=True)
        if proc.returncode != 0:
            raise RuntimeError(f"say 失败: {proc.stderr[:2000]}")

        ffmpeg_cmd = [
            ffmpeg_bin,
            "-y",
            "-i",
            str(aiff),
            "-ac",
            "1",
            "-ar",
            str(cfg.sample_rate),
            "-c:a",
            "pcm_s16le",
            str(out_wav),
        ]
        proc2 = subprocess.run(ffmpeg_cmd, capture_output=True, text=True)
        if proc2.returncode != 0:
            raise RuntimeError(f"ffmpeg 转码失败: {proc2.stderr[:4000]}")

    return {"say_cmd": say_cmd, "ffmpeg_cmd": ffmpeg_cmd}


def build_timeline(
    *,
    cues: List[Dict[str, Any]],
    segment_paths: List[Path],
    segment_durations: List[float],
    inter_gap_sec: float,
    scroll_lag_sec: float,
) -> Dict[str, Any]:
    """按“段长 + gap 驱动”规则生成 timeline.json（严格 schema）。"""

    if not (len(cues) == len(segment_paths) == len(segment_durations)):
        raise ValueError("cues/segment_paths/segment_durations 长度不一致")

    segments: List[Dict[str, Any]] = []
    scroll_events: List[Dict[str, Any]] = []
    cursor = 0.0
    for i, cue in enumerate(cues):
        duration = float(segment_durations[i])
        start = cursor
        end = start + duration
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
            scroll_events.append(
                {
                    "after_seg_index": i,
                    "to_seg_index": i + 1,
                    "scroll_action_at_sec": round(end, 3),
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


def run_mix_audio_from_timeline(*, timeline_json: Path, out_mp3: Path) -> None:
    """调用同目录下的 mix_audio_from_timeline.py 进行混音。"""

    script_dir = Path(__file__).resolve().parent
    mix_py = (script_dir / "mix_audio_from_timeline.py").resolve()
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
    """主流程：cues -> 分段 wav -> timeline -> (可选) 混音 mp3。"""

    args = parse_args()
    ws = Path(args.workspace_dir).resolve()
    cues_path = Path(args.cues_json).resolve()

    ws_inputs = ws / "inputs"
    ws_seg = ws / "segment_audio"
    ws_timeline_dir = ws / "timeline"
    ws_audio_dir = ws / "audio"
    for d in (ws_inputs, ws_seg, ws_timeline_dir, ws_audio_dir):
        d.mkdir(parents=True, exist_ok=True)

    cues_payload = read_json(cues_path)
    tts_cfg = MacSayConfig(voice=str(args.voice).strip(), rate=args.rate, sample_rate=int(args.sample_rate))

    signature = compute_signature(cues_payload, tts_cfg)
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
    (ws_inputs / "cues.json").write_text(
        json.dumps(cues_payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    segment_paths: List[Path] = []
    segment_durations: List[float] = []

    for i, cue in enumerate(cues):
        out_wav = ws_seg / f"seg_{i:03d}.wav"
        if out_wav.exists() and not args.force_tts and old_sig == signature:
            dur = wav_duration_seconds(out_wav)
            segment_paths.append(out_wav)
            segment_durations.append(dur)
            continue

        info = synthesize_say_to_wav(
            text=cue["text"],
            out_wav=out_wav,
            cfg=tts_cfg,
            ffmpeg_bin=str(args.ffmpeg),
        )
        dur = wav_duration_seconds(out_wav)
        segment_paths.append(out_wav)
        segment_durations.append(dur)
        write_json(
            ws_seg / f"seg_{i:03d}.meta.json",
            {
                "seg_index": i,
                "cue_id": cue.get("id"),
                "audio_path": str(out_wav.resolve()),
                "duration_sec": round(dur, 3),
                "tts": {"provider": "macos_say", "voice": tts_cfg.voice, "rate": tts_cfg.rate},
                "commands": info,
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
        run_mix_audio_from_timeline(timeline_json=timeline_path, out_mp3=out_mp3)

    write_json(
        meta_path,
        {
            "workspace_dir": str(ws),
            "cues_json": str(cues_path),
            "tts": {"provider": "macos_say", "voice": tts_cfg.voice, "rate": tts_cfg.rate, "sample_rate": tts_cfg.sample_rate},
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

