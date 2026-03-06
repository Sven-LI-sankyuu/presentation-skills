#!/usr/bin/env python3
"""把一次“run 目录”的产物提升(promote)到稳定 workspace 目录（可选工具）。

为什么存在：
- 一些团队已有“按 run 产物落盘”的旧流水线，希望把结果迁移到 workspace 协作范式。
- 本 skill 的推荐路线是直接使用 `tts_build_workspace.py` 写入 workspace；不强制使用本脚本。

该脚本做的事：
1) 复制 `output/segment_audio/` 到 workspace 的 `segment_audio/`
2) 复制 `output/timeline.json` 到 workspace 的 `timeline/timeline.json`，并把 audio_path 重写为 workspace 内路径
3) 可选复制 `output/timeline_audio.mp3` 到 workspace 的 `audio/timeline_audio.mp3`

失败策略：
- 任何关键输入缺失直接报错退出（正确失败，不做静默降级）。
"""

from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path
from typing import Any, Dict, List


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Promote run output into a stable workspace")
    parser.add_argument("--run-dir", required=True, help="run 目录（包含 output/）")
    parser.add_argument("--workspace-dir", required=True, help="workspace 目录")
    parser.add_argument(
        "--copy-timeline-audio",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="是否复制 timeline_audio.mp3（默认复制）",
    )
    return parser.parse_args()


def read_json(path: Path) -> Dict[str, Any]:
    obj = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(obj, dict):
        raise ValueError(f"JSON 顶层必须是对象: {path}")
    return obj


def write_json(path: Path, obj: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")


def copy_tree(src: Path, dst: Path) -> None:
    if not src.exists() or not src.is_dir():
        raise FileNotFoundError(f"目录不存在: {src}")
    dst.mkdir(parents=True, exist_ok=True)
    for p in src.iterdir():
        if p.is_dir():
            continue
        shutil.copy2(p, dst / p.name)


def rewrite_audio_paths(timeline: Dict[str, Any], segment_audio_dir: Path) -> Dict[str, Any]:
    segs = timeline.get("segments")
    if not isinstance(segs, list) or not segs:
        raise ValueError("timeline.segments 必须是非空数组")

    new_segs: List[Dict[str, Any]] = []
    for seg in segs:
        if not isinstance(seg, dict):
            raise ValueError("timeline.segments 元素必须是对象")
        audio_path = seg.get("audio_path")
        if not isinstance(audio_path, str) or not audio_path.strip():
            raise ValueError("segment.audio_path 缺失或非法")
        src_name = Path(audio_path).name
        new_audio = (segment_audio_dir / src_name).resolve()
        if not new_audio.exists():
            raise FileNotFoundError(f"workspace 内缺少音频文件: {new_audio}")
        seg2 = dict(seg)
        seg2["audio_path"] = str(new_audio)
        new_segs.append(seg2)

    out = dict(timeline)
    out["segments"] = new_segs
    return out


def main() -> None:
    args = parse_args()
    run_dir = Path(args.run_dir).resolve()
    ws = Path(args.workspace_dir).resolve()

    out_dir = run_dir / "output"
    seg_src = out_dir / "segment_audio"
    timeline_src = out_dir / "timeline.json"
    audio_src = out_dir / "timeline_audio.mp3"

    if not seg_src.exists():
        raise FileNotFoundError(f"缺少 segment_audio: {seg_src}")
    if not timeline_src.exists():
        raise FileNotFoundError(f"缺少 timeline.json: {timeline_src}")

    ws_inputs = ws / "inputs"
    ws_seg = ws / "segment_audio"
    ws_timeline_dir = ws / "timeline"
    ws_audio_dir = ws / "audio"

    for d in (ws_inputs, ws_seg, ws_timeline_dir, ws_audio_dir):
        d.mkdir(parents=True, exist_ok=True)

    copy_tree(seg_src, ws_seg)

    timeline = read_json(timeline_src)
    timeline2 = rewrite_audio_paths(timeline, ws_seg)
    timeline_out = ws_timeline_dir / "timeline.json"
    write_json(timeline_out, timeline2)

    if args.copy_timeline_audio:
        if not audio_src.exists():
            raise FileNotFoundError(f"缺少 timeline_audio.mp3: {audio_src}")
        shutil.copy2(audio_src, ws_audio_dir / "timeline_audio.mp3")

    meta = {
        "promoted_from_run_dir": str(run_dir),
        "workspace_dir": str(ws),
        "outputs": {
            "segment_audio_dir": str(ws_seg),
            "timeline_json": str(timeline_out),
            "timeline_audio": str((ws_audio_dir / "timeline_audio.mp3").resolve())
            if args.copy_timeline_audio
            else None,
        },
    }
    write_json(ws / "workspace_meta.json", meta)
    print(json.dumps(meta, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
