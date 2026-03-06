#!/usr/bin/env bash
# 网页 demo 视频转码与字幕烧录
#
# 作用：
# - 将原始录屏视频转为 H.264 MP4。
# - 可选烧录 SRT 字幕，并设置底部安全区样式。
#
# 失败策略：
# - 任一关键参数缺失或 ffmpeg 失败，立即退出。

set -euo pipefail

INPUT=""
OUTPUT=""
SUBTITLE=""
WIDTH=""
HEIGHT=""
FPS="30"
CRF="18"
PRESET="medium"
MAXRATE="16M"
BUFSIZE="32M"
AUDIO_BITRATE="160k"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --input)
      INPUT="$2"; shift 2 ;;
    --output)
      OUTPUT="$2"; shift 2 ;;
    --subtitle)
      SUBTITLE="$2"; shift 2 ;;
    --width)
      WIDTH="$2"; shift 2 ;;
    --height)
      HEIGHT="$2"; shift 2 ;;
    --fps)
      FPS="$2"; shift 2 ;;
    --crf)
      CRF="$2"; shift 2 ;;
    --preset)
      PRESET="$2"; shift 2 ;;
    --maxrate)
      MAXRATE="$2"; shift 2 ;;
    --bufsize)
      BUFSIZE="$2"; shift 2 ;;
    --audio-bitrate)
      AUDIO_BITRATE="$2"; shift 2 ;;
    *)
      echo "未知参数: $1" >&2
      exit 1 ;;
  esac
done

if [[ -z "$INPUT" || -z "$OUTPUT" || -z "$WIDTH" || -z "$HEIGHT" ]]; then
  echo "用法: --input IN --output OUT --width W --height H [--subtitle SRT] [--fps 30] [--crf 18] [--maxrate 16M]" >&2
  exit 1
fi

if [[ ! -f "$INPUT" ]]; then
  echo "输入视频不存在: $INPUT" >&2
  exit 1
fi

if ! command -v ffmpeg >/dev/null 2>&1; then
  echo "未找到 ffmpeg，请先安装" >&2
  exit 1
fi

mkdir -p "$(dirname "$OUTPUT")"

base_filter="scale=${WIDTH}:${HEIGHT}:force_original_aspect_ratio=decrease,pad=${WIDTH}:${HEIGHT}:(ow-iw)/2:(oh-ih)/2:black,fps=${FPS},format=yuv420p"

if [[ -n "$SUBTITLE" ]]; then
  if [[ ! -f "$SUBTITLE" ]]; then
    echo "字幕文件不存在: $SUBTITLE" >&2
    exit 1
  fi

  # subtitles 过滤器需要转义路径中的特殊字符
  subtitle_escaped="$SUBTITLE"
  subtitle_escaped="${subtitle_escaped//\\/\\\\}"
  subtitle_escaped="${subtitle_escaped//:/\\:}"
  subtitle_escaped="${subtitle_escaped//,/\\,}"
  subtitle_escaped="${subtitle_escaped//\'/\\\'}"

  sub_filter="subtitles='${subtitle_escaped}':force_style='Alignment=2,MarginV=54,Fontsize=20,Outline=1,Shadow=0,PrimaryColour=&H00FFFFFF&,BackColour=&H80000000&,BorderStyle=4'"
  vf="${base_filter},${sub_filter}"
else
  vf="${base_filter}"
fi

ffmpeg -y \
  -i "$INPUT" \
  -vf "$vf" \
  -c:v libx264 \
  -preset "$PRESET" \
  -crf "$CRF" \
  -maxrate "$MAXRATE" \
  -bufsize "$BUFSIZE" \
  -c:a aac \
  -b:a "$AUDIO_BITRATE" \
  -movflags +faststart \
  "$OUTPUT"

echo "输出完成: $OUTPUT"
