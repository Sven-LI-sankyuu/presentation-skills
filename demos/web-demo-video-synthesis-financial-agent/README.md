# Web Demo Video Synthesis - 金融 Agent 展示视频（端到端）

这个 demo 用 `web-demo-video-synthesis` 的 workspace 范式，完成：

- 一页滚动式网页（金融 Agent 主题）
- 分段配音（本机 macOS `say`，无需密钥）
- `timeline.json` 驱动录屏（Playwright + Chromium）
- timeline 生成字幕（SRT）
- ffmpeg 合成：母带视频 + 旁白音轨 + 烧录字幕，输出 MP4

## 目录结构

- `site/`：静态网页（录屏目标）
- `inputs/cues.zh.json`：分段旁白（锁版本）
- `scripts/tts_build_workspace_macos_say.py`：本机分段 TTS + 生成 timeline（兼容该 skill 的 timeline schema）
- `scripts/run_pipeline.sh`：一键从网页到成片

视频产物的 workspace 默认写到仓库的 `temp/` 下（便于反复迭代、避免污染 demo 目录）；脚本会额外复制一份最终 MP4 到本 demo 的 `_output/` 便于查看。

## 依赖

- Python 3（本 demo 只用标准库）
- macOS `say`（系统自带；用于中文配音）
- Node 18+ + npm
- `web-demo-video-synthesis` 已安装依赖：
  - `npm install playwright`
  - `npx playwright install chromium`
- `ffmpeg`（需支持 `libass` + `libx264`，本项目环境已满足）

## 一键运行

在本仓库根目录执行：

```bash
bash demos/web-demo-video-synthesis-financial-agent/scripts/run_pipeline.sh
```

成功后你会得到：

- workspace：`temp/web_demo_video_ws/fin_agent_demo01/final/final.mp4`
- 便于查看的副本：`demos/web-demo-video-synthesis-financial-agent/_output/final.mp4`

## 英文版本（网页 + 文案 + 英文配音）

```bash
bash demos/web-demo-video-synthesis-financial-agent/scripts/run_pipeline_en.sh
```

成功后你会得到：

- workspace：`temp/web_demo_video_ws/fin_agent_demo_en01/final/final.mp4`
- 便于查看的副本：`demos/web-demo-video-synthesis-financial-agent/_output/final_en.mp4`

可选环境变量：

- `TTS_PROVIDER`：TTS 提供方（默认 `macos_say`；可选 `isi_rest`）
- `KEY_JSON`：当 `TTS_PROVIDER=isi_rest` 时，阿里云 ISI 的鉴权文件路径（不入库）
- `VOICE`：
  - `macos_say`：macOS `say` 的英文音色（默认 `Samantha`）
  - `isi_rest`：阿里云 ISI 的 `voice` 参数（推荐 `emily`）
- `SAY_RATE`：`say -r` 语速（例如 `SAY_RATE=185`）
- `FORCE_TTS=1`：文案变更后强制重生成分段音频（否则会“正确失败”）

如果你希望英文用 `emily`、中文用 `zhida`（需要阿里云 ISI 凭证）：

```bash
KEY_JSON=secrets/key.json TTS_PROVIDER=isi_rest VOICE=emily bash demos/web-demo-video-synthesis-financial-agent/scripts/run_pipeline_en.sh
KEY_JSON=secrets/key.json TTS_PROVIDER=isi_rest VOICE=zhida  bash demos/web-demo-video-synthesis-financial-agent/scripts/run_pipeline.sh
```

## 常见问题

- Playwright 找不到 Chromium：
  - 在 `web-demo-video-synthesis/` 下执行 `npx playwright install chromium`
- 想改文案但不想被“签名保护”拦住：
  - 在运行时加 `FORCE_TTS=1`，例如：
    - `FORCE_TTS=1 bash demos/web-demo-video-synthesis-financial-agent/scripts/run_pipeline.sh`
