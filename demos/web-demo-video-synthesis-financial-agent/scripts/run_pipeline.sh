#!/usr/bin/env bash
set -euo pipefail

DEMO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
REPO_ROOT="$(cd "${DEMO_DIR}/../.." && pwd)"
SKILL_DIR="${REPO_ROOT}/web-demo-video-synthesis"

DEFAULT_PORT="6150"
PORT="${PORT:-}"
WORKSPACE_DIR="${WORKSPACE_DIR:-${REPO_ROOT}/temp/web_demo_video_ws/fin_agent_demo01}"
TTS_PROVIDER="${TTS_PROVIDER:-macos_say}" # macos_say | isi_rest
KEY_JSON="${KEY_JSON:-}"
VOICE="${VOICE:-}"
SAY_RATE="${SAY_RATE:-}"
FORCE_TTS="${FORCE_TTS:-0}"

RECORD_VIEWPORT="${RECORD_VIEWPORT:-1920x1080}"
RECORD_SIZE="${RECORD_SIZE:-3840x2160}"
DEVICE_SCALE_FACTOR="${DEVICE_SCALE_FACTOR:-2}"
TAIL_SEC="${TAIL_SEC:-1.0}"

SUBTITLE_FONT_SIZE="${SUBTITLE_FONT_SIZE:-13}"
SUBTITLE_MARGIN_V="${SUBTITLE_MARGIN_V:-24}"

SITE_DIR="${DEMO_DIR}/site"

port_is_free() {
  python3 - "$1" <<'PY'
import socket, sys
port = int(sys.argv[1])
s = socket.socket()
try:
    s.bind(("127.0.0.1", port))
except OSError:
    sys.exit(1)
finally:
    try:
        s.close()
    except Exception:
        pass
PY
}

pick_free_port() {
  python3 - <<'PY'
import socket
s = socket.socket()
s.bind(("127.0.0.1", 0))
print(s.getsockname()[1])
s.close()
PY
}

resolve_port() {
  local desired="$1"
  if port_is_free "$desired"; then
    echo "$desired"
    return 0
  fi
  echo "$(pick_free_port)"
}

if [[ -z "${PORT}" ]]; then
  PORT="$(resolve_port "${DEFAULT_PORT}")"
else
  if ! port_is_free "${PORT}"; then
    echo "端口已被占用: PORT=${PORT}。请换一个空闲端口，例如 PORT=6160。" >&2
    exit 1
  fi
fi

RECORD_URL="http://127.0.0.1:${PORT}/index.html"

WS_TIMELINE="${WORKSPACE_DIR}/timeline/timeline.json"
WS_AUDIO="${WORKSPACE_DIR}/audio/timeline_audio.mp3"
WS_VIDEO="${WORKSPACE_DIR}/video/video_nocap.webm"
WS_SRT="${WORKSPACE_DIR}/subtitles/captions.srt"
WS_FINAL="${WORKSPACE_DIR}/final/final.mp4"

OUT_DIR="${DEMO_DIR}/_output"
OUT_FINAL="${OUT_DIR}/final.mp4"

mkdir -p "${WORKSPACE_DIR}"/{inputs,segment_audio,timeline,audio,video,subtitles,final} "${OUT_DIR}"

python_server_pid=""
cleanup() {
  if [[ -n "${python_server_pid}" ]]; then
    kill "${python_server_pid}" >/dev/null 2>&1 || true
  fi
}
trap cleanup EXIT

echo "[1/5] 启动静态站点: ${RECORD_URL}"
SERVER_LOG="${WORKSPACE_DIR}/server_${PORT}.log"
(cd "${SITE_DIR}" && python3 -m http.server "${PORT}" --bind 127.0.0.1 >"${SERVER_LOG}" 2>&1) &
python_server_pid="$!"
sleep 0.6
if ! kill -0 "${python_server_pid}" >/dev/null 2>&1; then
  echo "静态站点启动失败（可能是端口占用或目录问题）。日志: ${SERVER_LOG}" >&2
  tail -n 80 "${SERVER_LOG}" >&2 || true
  exit 1
fi
if ! curl -fsS "${RECORD_URL}" | grep -q 'id="step-hero"'; then
  echo "静态站点校验失败：返回内容不是预期网页（可能是端口被其他服务劫持）。" >&2
  echo "请尝试改端口: PORT=6160 bash .../run_pipeline.sh" >&2
  echo "日志: ${SERVER_LOG}" >&2
  tail -n 80 "${SERVER_LOG}" >&2 || true
  exit 1
fi

echo "[2/5] 生成分段配音 + timeline（TTS_PROVIDER=${TTS_PROVIDER}）"
tts_force_flag="--no-force-tts"
if [[ "${FORCE_TTS}" == "1" ]]; then
  tts_force_flag="--force-tts"
fi

if [[ -z "${VOICE}" ]]; then
  if [[ "${TTS_PROVIDER}" == "isi_rest" ]]; then
    VOICE="zhida"
  else
    VOICE="Tingting"
  fi
fi

declare -a say_rate_args=()
if [[ -n "${SAY_RATE}" ]]; then
  say_rate_args=(--rate "${SAY_RATE}")
fi

if [[ "${TTS_PROVIDER}" == "macos_say" ]]; then
  python3 "${DEMO_DIR}/scripts/tts_build_workspace_macos_say.py" \
    --workspace-dir "${WORKSPACE_DIR}" \
    --cues-json "${DEMO_DIR}/inputs/cues.zh.json" \
    --voice "${VOICE}" \
    ${say_rate_args[@]+"${say_rate_args[@]}"} \
    --sample-rate 48000 \
    --inter-gap-sec 2.0 \
    --scroll-lag-sec 1.2 \
    ${tts_force_flag} \
    --mix-audio \
    --skill-dir "${SKILL_DIR}"
elif [[ "${TTS_PROVIDER}" == "isi_rest" ]]; then
  if [[ -z "${KEY_JSON}" || ! -f "${KEY_JSON}" ]]; then
    echo "TTS_PROVIDER=isi_rest 需要 KEY_JSON 指向阿里云 ISI 的鉴权文件（不入库）。" >&2
    echo "示例：KEY_JSON=secrets/key.json TTS_PROVIDER=isi_rest VOICE=zhida bash .../run_pipeline.sh" >&2
    exit 1
  fi
  python3 "${SKILL_DIR}/scripts/tts_build_workspace.py" \
    --workspace-dir "${WORKSPACE_DIR}" \
    --cues-json "${DEMO_DIR}/inputs/cues.zh.json" \
    --key-json "${KEY_JSON}" \
    --voice "${VOICE}" \
    --sample-rate 48000 \
    --format "wav" \
    --inter-gap-sec 2.0 \
    --scroll-lag-sec 1.2 \
    ${tts_force_flag} \
    --mix-audio
else
  echo "未知 TTS_PROVIDER: ${TTS_PROVIDER}（仅支持 macos_say / isi_rest）" >&2
  exit 1
fi

echo "[3/5] 按 timeline 录制无字幕母带（Playwright）"
node "${SKILL_DIR}/scripts/record_demo_from_timeline.mjs" \
  --url "${RECORD_URL}" \
  --timeline-json "${WS_TIMELINE}" \
  --out "${WS_VIDEO}" \
  --tail-sec "${TAIL_SEC}" \
  --viewport "${RECORD_VIEWPORT}" \
  --record-size "${RECORD_SIZE}" \
  --device-scale-factor "${DEVICE_SCALE_FACTOR}" \
  --lang zh \
  --fail-on-json true \
  --expect-selector "#step-hero" \
  --scroll-behavior auto \
  --scroll-settle-ms 420 \
  --no-captions true

echo "[4/5] timeline -> SRT 字幕"
python3 "${SKILL_DIR}/scripts/build_srt_from_timeline.py" \
  --timeline "${WS_TIMELINE}" \
  --output "${WS_SRT}"

echo "[5/5] 合成最终 MP4（母带视频 + 旁白音轨 + 烧录字幕）"
if [[ ! -f "${WS_AUDIO}" ]]; then
  python3 "${SKILL_DIR}/scripts/mix_audio_from_timeline.py" \
    --timeline "${WS_TIMELINE}" \
    --output "${WS_AUDIO}"
fi

ffmpeg -y \
  -i "${WS_VIDEO}" \
  -i "${WS_AUDIO}" \
  -vf "subtitles=${WS_SRT}:force_style='Alignment=2,MarginV=${SUBTITLE_MARGIN_V},FontName=Arial,FontSize=${SUBTITLE_FONT_SIZE},PrimaryColour=&H00FFFFFF,OutlineColour=&H00000000,BorderStyle=3,Outline=1,Shadow=0'" \
  -c:v libx264 -preset medium -crf 18 \
  -c:a aac -b:a 192k \
  -shortest \
  "${WS_FINAL}"

cp -f "${WS_FINAL}" "${OUT_FINAL}"
echo "完成:"
echo "- workspace: ${WS_FINAL}"
echo "- output:    ${OUT_FINAL}"
