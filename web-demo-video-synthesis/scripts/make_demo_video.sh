#!/usr/bin/env bash
# 一键串联（最新路线）：
# 1) 固化文案 cues.json
# 2) 分段TTS -> timeline.json + timeline_audio.mp3
# 3) 按 timeline 二次录屏（无字幕母带）
# 4) timeline -> SRT
# 5) ffmpeg 合成（视频 + 语音 + 字幕）

set -euo pipefail

SEED_VIDEO=""
CUES_JSON=""
KEY_JSON=""
RECORD_URL=""
WORKSPACE_DIR=""
VOICE="auto"
SAMPLE_RATE="48000"
INTER_GAP_SEC="2.5"
SCROLL_LAG_SEC="1.2"
DEFAULT_WAIT_SEC="8.5"

RECORD_LANG="en"
RECORD_VIEWPORT="1920x1080"
RECORD_SIZE="3840x2160"
RECORD_DEVICE_SCALE_FACTOR="2"
RECORD_TAIL_SEC="1.0"
RECORD_WAIT_UNTIL="networkidle"
RECORD_FAIL_ON_JSON="true"
RECORD_EXPECT_SELECTOR=""
RECORD_EXPECT_TITLE_INCLUDES=""
RECORD_EXPECT_TIMEOUT_MS="12000"

SUBTITLE_FONT_SIZE="13"
SUBTITLE_MARGIN_V="24"

FFMPEG_BIN="ffmpeg"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --seed-video)
      SEED_VIDEO="$2"; shift 2 ;;
    --cues-json)
      CUES_JSON="$2"; shift 2 ;;
    --key-json)
      KEY_JSON="$2"; shift 2 ;;
    --record-url)
      RECORD_URL="$2"; shift 2 ;;
    --workspace-dir)
      WORKSPACE_DIR="$2"; shift 2 ;;
    --voice)
      VOICE="$2"; shift 2 ;;
    --model)
      MODEL="$2"; shift 2 ;;
    --sample-rate)
      SAMPLE_RATE="$2"; shift 2 ;;
    --inter-gap-sec)
      INTER_GAP_SEC="$2"; shift 2 ;;
    --scroll-lag-sec)
      SCROLL_LAG_SEC="$2"; shift 2 ;;
    --default-wait-sec)
      DEFAULT_WAIT_SEC="$2"; shift 2 ;;
    --record-lang)
      RECORD_LANG="$2"; shift 2 ;;
    --record-viewport)
      RECORD_VIEWPORT="$2"; shift 2 ;;
    --record-size)
      RECORD_SIZE="$2"; shift 2 ;;
    --record-device-scale-factor)
      RECORD_DEVICE_SCALE_FACTOR="$2"; shift 2 ;;
    --record-tail-sec)
      RECORD_TAIL_SEC="$2"; shift 2 ;;
    --record-wait-until)
      RECORD_WAIT_UNTIL="$2"; shift 2 ;;
    --record-fail-on-json)
      RECORD_FAIL_ON_JSON="$2"; shift 2 ;;
    --record-expect-selector)
      RECORD_EXPECT_SELECTOR="$2"; shift 2 ;;
    --record-expect-title-includes)
      RECORD_EXPECT_TITLE_INCLUDES="$2"; shift 2 ;;
    --record-expect-timeout-ms)
      RECORD_EXPECT_TIMEOUT_MS="$2"; shift 2 ;;
    --subtitle-font-size)
      SUBTITLE_FONT_SIZE="$2"; shift 2 ;;
    --subtitle-margin-v)
      SUBTITLE_MARGIN_V="$2"; shift 2 ;;
    --ffmpeg)
      FFMPEG_BIN="$2"; shift 2 ;;
    *)
      echo "未知参数: $1" >&2
      exit 1 ;;
  esac
done

if [[ -z "$WORKSPACE_DIR" ]]; then
  echo "用法: --workspace-dir DIR [--seed-video VIDEO --cues-json CUES --key-json KEY --record-url URL]" >&2
  exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if ! command -v "$FFMPEG_BIN" >/dev/null 2>&1; then
  echo "未找到 ffmpeg: $FFMPEG_BIN" >&2
  echo "请安装系统 ffmpeg（需支持 libass+libx264），或用 --ffmpeg 指向可用的 ffmpeg 可执行文件名/路径。" >&2
  exit 1
fi

mkdir -p "$WORKSPACE_DIR"
WORKSPACE_DIR="$(cd "$WORKSPACE_DIR" && pwd)"
mkdir -p "$WORKSPACE_DIR"/{inputs,secrets,segment_audio,timeline,audio,video,subtitles,final} || true

WS_TIMELINE="$WORKSPACE_DIR/timeline/timeline.json"
WS_AUDIO="$WORKSPACE_DIR/audio/timeline_audio.mp3"
WS_VIDEO="$WORKSPACE_DIR/video/video_nocap.webm"
WS_SRT="$WORKSPACE_DIR/subtitles/captions.srt"
WS_FINAL="$WORKSPACE_DIR/final/final.mp4"

RECORD_LANG_LOWER="$(printf '%s' "$RECORD_LANG" | tr '[:upper:]' '[:lower:]')"
RESOLVED_VOICE="$VOICE"
if [[ "$VOICE" == "auto" ]]; then
  if [[ "$RECORD_LANG_LOWER" == zh* ]]; then
    RESOLVED_VOICE="zhida"
  else
    RESOLVED_VOICE="emily"
  fi
fi

if [[ -z "$RESOLVED_VOICE" ]]; then
  echo "--voice 不能为空" >&2
  exit 1
fi
echo "TTS voice: $RESOLVED_VOICE (input=$VOICE, record_lang=$RECORD_LANG)"

# 若 workspace 缺少核心文件，则必须执行一次 TTS+timeline 生成并 promote 进 workspace。
if [[ ! -f "$WS_TIMELINE" || ! -d "$WORKSPACE_DIR/segment_audio" || -z "$(ls -A "$WORKSPACE_DIR/segment_audio" 2>/dev/null || true)" ]]; then
  if [[ -z "$CUES_JSON" || -z "$KEY_JSON" ]]; then
    echo "workspace 缺少 timeline/segment_audio，且未提供 --cues-json/--key-json 无法初始化。" >&2
    exit 1
  fi

  # 直接在 workspace 内生成 segment_audio + timeline（自包含，不依赖仓库其他目录）
  python3 "$SCRIPT_DIR/tts_build_workspace.py" \
    --workspace-dir "$WORKSPACE_DIR" \
    --cues-json "$CUES_JSON" \
    --key-json "$KEY_JSON" \
    --voice "$RESOLVED_VOICE" \
    --sample-rate "$SAMPLE_RATE" \
    --format "wav" \
    --inter-gap-sec "$INTER_GAP_SEC" \
    --scroll-lag-sec "$SCROLL_LAG_SEC" \
    --mix-audio true
fi

if [[ ! -f "$WS_TIMELINE" ]]; then
  echo "workspace 缺少 timeline: $WS_TIMELINE" >&2
  exit 1
fi

if [[ -z "$RECORD_URL" ]]; then
  echo "缺少 --record-url（录屏需要）" >&2
  exit 1
fi

extra_record_args=()
if [[ -n "$RECORD_EXPECT_SELECTOR" ]]; then
  extra_record_args+=(--expect-selector "$RECORD_EXPECT_SELECTOR")
fi
if [[ -n "$RECORD_EXPECT_TITLE_INCLUDES" ]]; then
  extra_record_args+=(--expect-title-includes "$RECORD_EXPECT_TITLE_INCLUDES")
fi

node "$SCRIPT_DIR/record_demo_from_timeline.mjs" \
  --url "$RECORD_URL" \
  --timeline-json "$WS_TIMELINE" \
  --out "$WS_VIDEO" \
  --tail-sec "$RECORD_TAIL_SEC" \
  --viewport "$RECORD_VIEWPORT" \
  --record-size "$RECORD_SIZE" \
  --device-scale-factor "$RECORD_DEVICE_SCALE_FACTOR" \
  --lang "$RECORD_LANG" \
  --wait-until "$RECORD_WAIT_UNTIL" \
  --fail-on-json "$RECORD_FAIL_ON_JSON" \
  --expect-timeout-ms "$RECORD_EXPECT_TIMEOUT_MS" \
  "${extra_record_args[@]}" \
  --scroll-behavior auto \
  --scroll-settle-ms 420 \
  --no-captions true

python3 "$SCRIPT_DIR/build_srt_from_timeline.py" \
  --timeline "$WS_TIMELINE" \
  --output "$WS_SRT"

# 备注：这里直接“烧录字幕 + 混入旁白音轨”，输出最终 MP4。
# 需要完整 ffmpeg（libass + libx264）。
if [[ ! -f "$WS_AUDIO" ]]; then
  # timeline_audio 不存在时，尝试用 workspace timeline 混音重建（常见于手工编辑 timeline 的场景）。
  python3 "$SCRIPT_DIR/mix_audio_from_timeline.py" \
    --timeline "$WS_TIMELINE" \
    --output "$WS_AUDIO"
fi

"$FFMPEG_BIN" -y \
  -i "$WS_VIDEO" \
  -i "$WS_AUDIO" \
  -vf "subtitles=${WS_SRT}:force_style='Alignment=2,MarginV=${SUBTITLE_MARGIN_V},FontName=Arial,FontSize=${SUBTITLE_FONT_SIZE},PrimaryColour=&H00FFFFFF,OutlineColour=&H00000000,BorderStyle=3,Outline=1,Shadow=0'" \
  -c:v libx264 -preset medium -crf 18 \
  -c:a aac -b:a 192k \
  -shortest \
  "$WS_FINAL"

echo "完成: $WS_FINAL"
