#!/usr/bin/env python3
"""从结构化 JSON 生成 SRT 字幕文件。

定位：
- 作为网页 demo 视频合成链路中的字幕预处理步骤。
- 输入必须是“纯字幕内容”的 JSON，禁止混入导演提示/操作建议。

流程：
1. 读取并校验 JSON schema（最小字段：cues）。
2. 解析每个 cue 的时间（支持时间戳或秒数）。
3. 输出标准 SRT，并在错误时直接失败。
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

TIME_RE = re.compile(r"^(?:(\d+):)?(\d+):(\d+)(?:\.(\d{1,3}))?$")


def parse_args() -> argparse.Namespace:
    """解析命令行参数。"""
    parser = argparse.ArgumentParser(description="JSON 字幕转 SRT")
    parser.add_argument("--input", required=True, help="输入字幕 JSON 文件")
    parser.add_argument("--output", required=True, help="输出 SRT 文件")
    return parser.parse_args()


def parse_timestamp(value: Any, field_name: str) -> float:
    """解析时间字段，支持 float/int 秒数或 HH:MM:SS(.mmm) / MM:SS(.mmm)。"""
    if isinstance(value, (int, float)):
        if value < 0:
            raise ValueError(f"{field_name} 不能为负数")
        return float(value)

    if isinstance(value, str):
        s = value.strip()
        if not s:
            raise ValueError(f"{field_name} 不能为空字符串")

        if s.replace(".", "", 1).isdigit():
            sec = float(s)
            if sec < 0:
                raise ValueError(f"{field_name} 不能为负数")
            return sec

        match = TIME_RE.match(s)
        if not match:
            raise ValueError(f"{field_name} 时间格式非法: {value}")

        hh = int(match.group(1) or 0)
        mm = int(match.group(2))
        ss = int(match.group(3))
        ms_raw = match.group(4) or "0"
        ms = int(ms_raw.ljust(3, "0"))

        if mm >= 60 or ss >= 60:
            raise ValueError(f"{field_name} 时间格式非法: {value}")

        return hh * 3600 + mm * 60 + ss + ms / 1000.0

    raise ValueError(f"{field_name} 类型非法: {type(value)}")


def to_srt_time(seconds: float) -> str:
    """将秒数转为 SRT 时间戳。"""
    if seconds < 0:
        raise ValueError("时间不能为负")
    total_ms = round(seconds * 1000)
    hh = total_ms // 3_600_000
    total_ms %= 3_600_000
    mm = total_ms // 60_000
    total_ms %= 60_000
    ss = total_ms // 1000
    ms = total_ms % 1000
    return f"{hh:02d}:{mm:02d}:{ss:02d},{ms:03d}"


def normalize_text(text: Any, field_name: str) -> str:
    """标准化字幕文本。"""
    if not isinstance(text, str):
        raise ValueError(f"{field_name} 必须是字符串")
    cleaned = text.strip()
    if not cleaned:
        raise ValueError(f"{field_name} 不能为空")
    return cleaned.replace("\r\n", "\n").replace("\r", "\n")


def build_srt_entries(payload: dict[str, Any]) -> list[str]:
    """将 JSON payload 转为 SRT 条目文本列表。"""
    cues = payload.get("cues")
    if not isinstance(cues, list) or not cues:
        raise ValueError("JSON 必须包含非空 cues 数组")

    entries: list[str] = []
    cursor = 0.0

    for idx, cue in enumerate(cues, start=1):
        if not isinstance(cue, dict):
            raise ValueError(f"cues[{idx-1}] 必须是对象")

        text = normalize_text(cue.get("text"), f"cues[{idx-1}].text")

        if "start" in cue:
            start = parse_timestamp(cue["start"], f"cues[{idx-1}].start")
        else:
            start = cursor

        if "end" in cue:
            end = parse_timestamp(cue["end"], f"cues[{idx-1}].end")
        elif "duration" in cue:
            duration = parse_timestamp(cue["duration"], f"cues[{idx-1}].duration")
            if duration <= 0:
                raise ValueError(f"cues[{idx-1}].duration 必须 > 0")
            end = start + duration
        else:
            raise ValueError(f"cues[{idx-1}] 需要 end 或 duration")

        if end <= start:
            raise ValueError(f"cues[{idx-1}] 的 end 必须大于 start")

        entries.append(
            "\n".join(
                [
                    str(idx),
                    f"{to_srt_time(start)} --> {to_srt_time(end)}",
                    text,
                    "",
                ]
            )
        )
        cursor = end

    return entries


def main() -> None:
    """命令入口。"""
    args = parse_args()
    input_path = Path(args.input)
    output_path = Path(args.output)

    payload = json.loads(input_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("顶层 JSON 必须是对象")

    entries = build_srt_entries(payload)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(entries).rstrip() + "\n", encoding="utf-8")

    print(json.dumps({"input": str(input_path), "output": str(output_path), "entries": len(entries)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
