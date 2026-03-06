#!/usr/bin/env bash
# 输出视频关键参数，便于验收清晰度与编码结果。

set -euo pipefail

INPUT=""
while [[ $# -gt 0 ]]; do
  case "$1" in
    --input)
      INPUT="$2"; shift 2 ;;
    *)
      echo "未知参数: $1" >&2
      exit 1 ;;
  esac
done

if [[ -z "$INPUT" ]]; then
  echo "用法: --input VIDEO" >&2
  exit 1
fi

if [[ ! -f "$INPUT" ]]; then
  echo "视频不存在: $INPUT" >&2
  exit 1
fi

if ! command -v ffprobe >/dev/null 2>&1; then
  echo "未找到 ffprobe，请先安装 ffmpeg" >&2
  exit 1
fi

ffprobe -v error \
  -select_streams v:0 \
  -show_entries stream=codec_name,width,height,avg_frame_rate,bit_rate \
  -show_entries format=duration,size,bit_rate \
  -of default=noprint_wrappers=1:nokey=0 \
  "$INPUT"
