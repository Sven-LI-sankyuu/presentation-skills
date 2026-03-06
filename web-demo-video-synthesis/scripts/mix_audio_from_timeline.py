#!/usr/bin/env python3
"""按 timeline.json 混音生成总旁白音轨（timeline_audio.mp3）。

定位：
- workspace 迭代过程中，人类/Codex 可能会手工调整 `timeline/timeline.json` 的 start/end。
- 这会改变每段语音的开始时间，需要重新混音，但不应该重跑 TTS。

做法：
- 读取 timeline.segments 的 `audio_path` 与 `start_sec`
- 用 ffmpeg 的 `adelay + amix` 合成一条音轨

依赖：
- 需要可用的 `ffmpeg`（建议完整构建，支持 `adelay/amix`）。
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
from pathlib import Path
from typing import Any, Dict, List


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Mix timeline audio")
    parser.add_argument("--timeline", required=True, help="timeline.json 路径")
    parser.add_argument("--output", required=True, help="输出 mp3 路径")
    parser.add_argument(
        "--ffmpeg",
        default="auto",
        help="ffmpeg 命令（auto 或显式指定，例如 'ffmpeg'）",
    )
    parser.add_argument("--bitrate", default="192k", help="输出 mp3 码率")
    return parser.parse_args()


def resolve_ffmpeg(cmd: str) -> List[str]:
    if cmd != "auto":
        return cmd.split(" ")
    if shutil.which("ffmpeg"):
        return ["ffmpeg"]
    raise RuntimeError("未找到 ffmpeg，请先安装（或用 --ffmpeg 显式指定命令）")


def read_json(path: Path) -> Dict[str, Any]:
    obj = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(obj, dict):
        raise ValueError("timeline 顶层必须是对象")
    return obj


def main() -> None:
    args = parse_args()
    timeline_path = Path(args.timeline).resolve()
    out_path = Path(args.output).resolve()
    timeline = read_json(timeline_path)

    segs = timeline.get("segments")
    if not isinstance(segs, list) or not segs:
        raise ValueError("timeline.segments 必须是非空数组")

    ffmpeg = resolve_ffmpeg(str(args.ffmpeg))

    cmd: List[str] = [*ffmpeg, "-y"]
    for seg in segs:
        if not isinstance(seg, dict):
            raise ValueError("timeline.segments 元素必须是对象")
        ap = seg.get("audio_path")
        if not isinstance(ap, str) or not ap.strip():
            raise ValueError("segment.audio_path 缺失或非法")
        p = Path(ap).resolve()
        if not p.exists():
            raise FileNotFoundError(f"音频文件不存在: {p}")
        cmd.extend(["-i", str(p)])

    filter_parts: List[str] = []
    mix_inputs: List[str] = []
    for i, seg in enumerate(segs):
        start = float(seg.get("start_sec", 0.0))
        if start < 0:
            raise ValueError("segment.start_sec 不能为负")
        delay_ms = int(round(start * 1000.0))
        label = f"a{i}"
        filter_parts.append(f"[{i}:a]adelay={delay_ms}:all=1[{label}]")
        mix_inputs.append(f"[{label}]")

    filter_parts.append(
        f"{''.join(mix_inputs)}amix=inputs={len(mix_inputs)}:normalize=0:dropout_transition=0[aout]"
    )

    out_path.parent.mkdir(parents=True, exist_ok=True)
    cmd.extend(
        [
            "-filter_complex",
            ";".join(filter_parts),
            "-map",
            "[aout]",
            "-c:a",
            "libmp3lame",
            "-b:a",
            str(args.bitrate),
            str(out_path),
        ]
    )

    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        raise RuntimeError(f"混音失败: {proc.stderr[:4000]}")

    print(json.dumps({"timeline": str(timeline_path), "output": str(out_path), "cmd": cmd}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
