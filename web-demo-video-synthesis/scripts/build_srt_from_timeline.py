#!/usr/bin/env python3
"""从 timeline.json 生成 SRT 字幕文件。

定位：
- timeline 是主键数据：segments 内含 start/end/text。
- 该脚本用于“先录无字幕母带，再后期烧录字幕”的路线。

输入：
- timeline.json（要求包含 segments，每段有 start_sec/end_sec/text）

输出：
- 标准 .srt（UTF-8）
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict, List


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="timeline.json -> SRT")
    parser.add_argument("--timeline", required=True, help="timeline.json 路径")
    parser.add_argument("--output", required=True, help="输出 .srt 路径")
    return parser.parse_args()


def to_srt_time(seconds: float) -> str:
    if seconds < 0:
        raise ValueError("时间不能为负")
    total_ms = int(round(seconds * 1000))
    hh = total_ms // 3_600_000
    total_ms %= 3_600_000
    mm = total_ms // 60_000
    total_ms %= 60_000
    ss = total_ms // 1000
    ms = total_ms % 1000
    return f"{hh:02d}:{mm:02d}:{ss:02d},{ms:03d}"


def normalize_text(value: Any) -> str:
    if not isinstance(value, str):
        raise ValueError("segment.text 必须是字符串")
    text = value.strip()
    if not text:
        raise ValueError("segment.text 不能为空")
    return text.replace("\r\n", "\n").replace("\r", "\n")


def load_timeline(path: Path) -> Dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("timeline 顶层必须是对象")
    segments = payload.get("segments")
    if not isinstance(segments, list) or not segments:
        raise ValueError("timeline.segments 必须是非空数组")
    return payload


def build_entries(segments: List[Dict[str, Any]]) -> List[str]:
    entries: List[str] = []
    last_end = -1.0
    for i, seg in enumerate(segments, start=1):
        if not isinstance(seg, dict):
            raise ValueError("timeline.segments 元素必须是对象")
        start = float(seg.get("start_sec", 0.0))
        end = float(seg.get("end_sec", 0.0))
        if start < 0 or end <= start:
            raise ValueError(f"segment[{i-1}] 的 start/end 非法")
        if last_end > start + 1e-6:
            raise ValueError(f"segment[{i-1}] 的 start 早于上一段 end")
        text = normalize_text(seg.get("text", ""))
        entries.append(
            "\n".join(
                [
                    str(i),
                    f"{to_srt_time(start)} --> {to_srt_time(end)}",
                    text,
                    "",
                ]
            )
        )
        last_end = end
    return entries


def main() -> None:
    args = parse_args()
    timeline_path = Path(args.timeline)
    out_path = Path(args.output)

    timeline = load_timeline(timeline_path)
    segments = timeline["segments"]
    entries = build_entries(segments)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("\n".join(entries).rstrip() + "\n", encoding="utf-8")
    print(json.dumps({"timeline": str(timeline_path), "output": str(out_path), "entries": len(entries)}, ensure_ascii=False))


if __name__ == "__main__":
    main()

