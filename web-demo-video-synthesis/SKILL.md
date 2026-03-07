---
name: web-demo-video-synthesis
description: 用于“网页 demo 分段配音 + timeline 驱动录屏 + 后期合成”的 workspace 协作流程：先搭建一个可审计工作目录（cues/timeline/segment_audio/video/subtitles/final），再由人类 + Codex 迭代维护这些文件，按需只重跑局部步骤，最终合成高质量 MP4。适用于强调可复盘、可编辑、清晰度与字幕安全区可控的场景。
---

# Web Demo Video Synthesis

## 核心原则

1. 先锁定文案，再执行技术流水线。
2. 语音必须按段生成（每段独立可重试，可定位失败）。
3. `timeline.json` 是全链路主键：录屏、音频编排、字幕都基于它。
4. 录屏阶段输出“无字幕母带”，字幕在最终合成阶段统一烧录。
5. 禁止静默降级：缺参数、schema 错误、时序冲突必须直接报错。

## 依赖与安装（独立发布必需）

该 skill 可单独拷贝发布，但需要安装运行依赖：

- `python3`（建议 3.10+）
  - 需要的 Python 包：`requests`
  - 录屏与后期合成不依赖 Python 的 GUI
- `node`（建议 18+）+ `npm`
  - 需要 Node 包：`playwright`
  - 需要安装浏览器：`npx playwright install chromium`
- `ffmpeg`
  - 需要完整构建，至少支持：`libass`（字幕烧录）与 `libx264`（H.264 编码）

最小安装示例（仅供参考，具体按你的环境调整）：

```bash
pip install requests
npm install playwright
npx playwright install chromium
```

执行目录约定：
- 以下命令默认在 `web-demo-video-synthesis/` 目录内执行（即本 `SKILL.md` 同级目录）。
- 若你从其他目录执行，请自行加上前缀路径。

## 向人类索要的密钥/Token（必须明确）

该流程可能需要人类提供以下敏感信息（不应提交到代码仓库）：

- 阿里云 ISI（Intelligent Speech Interaction）TTS：
  - `Appkey`（项目级 Appkey）
  - `AccessToken`（短期 token）
  - 保存为 `key.json`，字段名兼容：`appkey/app_key/api_key` 与 `token/access_token/AccessToken/accessToken`
- 给人类的参考链接（建议在索要秘钥时一并发给对方；链接可能会变化，若失效请在阿里云文档站内搜索关键词）：
  - 控制台（NLS Portal / 智能语音交互）：`https://nls-portal.console.aliyun.com/overview`
  - RESTful API 文档（语音合成）：`https://help.aliyun.com/zh/isi/developer-reference/restful-api-3`
    - 备注：我在 2026-03-06（Asia/Shanghai）验证过该链接可访问，但页面内部锚点（`#topic-...`）可能不稳定。
  - ISI 文档入口（用于查“Token 获取方式/鉴权说明/参数表”等）：`https://help.aliyun.com/zh/isi/`

推荐优先级（明确，不做静默降级）：

1. **先进的 TTS API（推荐，优先级最高）**：例如阿里云 ISI（本 skill 默认实现），或你们自行接入其他更先进的 TTS。
2. **本地替代（仅用于无秘钥快速验证）**：例如 macOS `say`（无需密钥，但音色/自然度通常弱于先进 TTS）。

也可以替换其他 TTS 服务商，但需要你们自行研究对应 API，并保证输出满足：
- 分段音频可落盘（每段一个文件）
- 可拿到每段时长（用于 timeline）

## Workspace 风格（推荐）

目标不是“每次从头跑一个专门的 run”，而是搭建一个可协作的工作目录，然后按顺序维护关键文件：

建议 workspace 目录结构（示例：`temp/web_demo_video_ws/demo01/`）：

- `inputs/cues.json`：旁白分段文案（锁版本）
- `secrets/key.json`：TTS 鉴权（不入库）
- `segment_audio/`：每段音频缓存（可复用）
- `timeline/timeline.json`：主键时间轴（可编辑）
- `audio/timeline_audio.mp3`：按 timeline 混出的总音轨（可重建）
- `video/video_nocap.webm`：按 timeline 录制的无字幕母带（可重录）
- `subtitles/captions.srt`：由 timeline 导出的字幕（可重建）
- `final/final.mp4`：最终成片（可重建）

这种布局支持你们迭代：
- 改文案：只重跑 TTS + 生成 timeline
- 改 timeline：只重混音 + 重录屏 + 重合成
- 改字幕样式：只重合成（烧录字幕）

## 推荐操作顺序（手动可控，便于协作）

1. 初始化 workspace（第一次）
- 准备 `inputs/cues.json`（锁版本）
- 准备 `secrets/key.json`（人类提供，不入库）
- 跑一次分段 TTS + timeline（生成器会产出 run 历史）
- 把该次 run 的产物 promote 到 workspace（后续迭代用 workspace 文件为准）

2. 迭代调 timeline（常见）
- 人类/Codex 编辑 `timeline/timeline.json`
- 用 `mix_audio_from_timeline.py` 重建 `audio/timeline_audio.mp3`

3. 迭代录屏（常见）
- 用 `record_demo_from_timeline.mjs --no-captions true` 生成 `video/video_nocap.webm`
 - 前提：你的 demo 前端服务必须已启动且 `record_url` 可访问，否则 Playwright 会失败并退出（正确失败）。
 - 若出现“滚动就位慢于开声”，优先调大 `scripts/tts_build_workspace.py` 的 `--scroll-lag-sec` 或 `--inter-gap-sec`（让开声更晚），其次再考虑提高录屏脚本的 `--scroll-settle-ms`（仅影响录屏等待，不改变音轨时间）。

4. 迭代字幕与合成（常见）
- 用 `build_srt_from_timeline.py` 生成 `subtitles/captions.srt`
- 用完整 ffmpeg 合成最终 `final/final.mp4`

## 输入约定（最小集）

- `cues.json`：最终旁白文案（只含可播报文本，不含导演提示）。
- `record_url`：demo 页 URL（例如 `http://127.0.0.1:6150/demo`）。
- `key.json`：TTS 鉴权（阿里云 Appkey + AccessToken）。
- `seed_video`：任意可读取视频（用于时间预算与流水线基准输入）。

输入 schema：
- 旁白 cues：见 [references/subtitle_schema.md](references/subtitle_schema.md)
- timeline 结构：见 [references/steps_schema.md](references/steps_schema.md)

## 标准流程（workspace 迭代版）

1. 固化文案（锁版本）
- 文案先冻结，再录制与合成，避免“视频一半后字幕改稿”。

2. 分段 TTS
- 调用 `scripts/tts_build_workspace.py`，逐段生成音频并生成 `timeline/timeline.json`。
- 产物：`segment_audio/*.wav`、`timeline/timeline.json`、可选 `audio/timeline_audio.mp3`。

### 可选：无秘钥的本地 TTS（macOS say）

当你暂时拿不到任何 TTS API 的秘钥/Token，但仍希望先把“网页录屏/字幕/合成”跑通，可以显式改用 macOS `say`：

```bash
python3 scripts/tts_build_workspace_macos_say.py \
  --workspace-dir temp/web_demo_video_ws/demo01 \
  --cues-json temp/web_demo_video_ws/demo01/inputs/cues.json \
  --voice Tingting \
  --sample-rate 48000 \
  --inter-gap-sec 2.5 \
  --scroll-lag-sec 1.2 \
  --mix-audio true
```

注意：
- 这是 **显式选择** 的替代方案，不会在 `tts_build_workspace.py` 里自动 fallback（避免“看起来成功”的静默降级）。
- `voice` 的取值与服务商强相关：
  - ISI 的 voice（例如 `emily`/`zhida`）以服务商文档为准；
  - macOS `say` 的 voice（例如 `Tingting`/`Samantha`）用 `say -v '?'` 查询。

3. 基于 timeline 二次录屏（无字幕）
- 使用 `scripts/record_demo_from_timeline.mjs --no-captions true`。
- 产物：`video_from_timeline_nocap.webm`。

4. timeline -> 字幕文件
- 从 `timeline.json` 的 `segments` 生成 `.srt`（逐段 `start_sec/end_sec/text`）。

5. 最终合成（视频 + 语音 + 字幕）
- 使用完整构建的 ffmpeg（系统安装版本即可）。
- 输出高质量 MP4。

## 一键执行（仍可用，但不强制）

```bash
bash scripts/make_demo_video.sh \
  --cues-json PATH/TO/cues.json \
  --key-json PATH/TO/key.json \
  --record-url http://127.0.0.1:6150/demo \
  --workspace-dir temp/web_demo_video_ws/demo01 \
  --voice auto \
  --record-lang en \
  --record-viewport 1920x1080 \
  --record-size 3840x2160 \
  --record-device-scale-factor 2 \
  --subtitle-font-size 13 \
  --subtitle-margin-v 24
```

`--voice auto` 规则：
- `--record-lang en*` -> `emily`
- `--record-lang zh*` -> `zhida`
- 其他语言默认回退到 `emily`

## 常用局部命令（只重跑某一步）

分段TTS + timeline（直接写 workspace，可迭代；默认防止静默复用旧音频）：

```bash
python3 scripts/tts_build_workspace.py \
  --workspace-dir temp/web_demo_video_ws/demo01 \
  --cues-json temp/web_demo_video_ws/demo01/inputs/cues.json \
  --key-json temp/web_demo_video_ws/demo01/secrets/key.json \
  --voice emily \
  --sample-rate 48000 \
  --inter-gap-sec 2.5 \
  --scroll-lag-sec 1.2
```

改了 timeline 后重混音：

```bash
python3 scripts/mix_audio_from_timeline.py \
  --timeline temp/web_demo_video_ws/demo01/timeline/timeline.json \
  --output temp/web_demo_video_ws/demo01/audio/timeline_audio.mp3
```

按 timeline 录无字幕母带：

```bash
node scripts/record_demo_from_timeline.mjs \
  --url http://127.0.0.1:6150/demo \
  --timeline-json temp/web_demo_video_ws/demo01/timeline/timeline.json \
  --out temp/web_demo_video_ws/demo01/video/video_nocap.webm \
  --viewport 1920x1080 \
  --record-size 3840x2160 \
  --device-scale-factor 2 \
  --lang en \
  --wait-until networkidle \
  --fail-on-json true \
  --expect-selector "#step-hero" \
  --expect-timeout-ms 12000 \
  --no-captions true
```

录屏阶段的“正确失败”防护（强烈建议）：

- `--fail-on-json true`（默认 true）：如果 `record_url` 返回 `application/json`，会直接失败。
  - 典型原因：端口被占用导致访问到了别的服务，或录到了 API/404 JSON 而不是网页。
- `--expect-selector` / `--expect-title-includes`：对目标页面做最小的存在性校验，避免把错误页面录成“看起来成功”的视频。
- `--wait-until domcontentloaded`：对 SPA/持续请求的页面更稳（否则 `networkidle` 可能等不到）。

timeline -> SRT：

```bash
python3 scripts/build_srt_from_timeline.py \
  --timeline temp/web_demo_video_ws/demo01/timeline/timeline.json \
  --output temp/web_demo_video_ws/demo01/subtitles/captions.srt
```

最终合成（视频+音轨+字幕）：

```bash
ffmpeg -y \
  -i temp/web_demo_video_ws/demo01/video/video_nocap.webm \
  -i temp/web_demo_video_ws/demo01/audio/timeline_audio.mp3 \
  -vf "subtitles=temp/web_demo_video_ws/demo01/subtitles/captions.srt:force_style='Alignment=2,MarginV=24,FontName=Arial,FontSize=13,PrimaryColour=&H00FFFFFF,OutlineColour=&H00000000,BorderStyle=3,Outline=1,Shadow=0'" \
  -c:v libx264 -preset medium -crf 18 \
  -c:a aac -b:a 192k \
  -shortest \
  temp/web_demo_video_ws/demo01/final/final.mp4
```

## 关键产物

- workspace 内产物（推荐）：`inputs/ segment_audio/ timeline/ audio/ video/ subtitles/ final/`
 

## 必读参考

- [references/subtitle_schema.md](references/subtitle_schema.md)：文案分段输入规范
- [references/steps_schema.md](references/steps_schema.md)：timeline 结构与约束
- [references/quality_tuning.md](references/quality_tuning.md)：清晰度和字幕安全区调优
- [references/troubleshooting.md](references/troubleshooting.md)：踩坑与排障清单

## Legacy（不推荐）

本 skill 目录里保留了旧的“steps 驱动录屏 + subtitles.json”脚本（用于历史兼容与对照）：
- `scripts/record_web_demo_with_playwright.mjs`
- `scripts/build_subtitles_from_json.py`
- `scripts/transcode_burn_subtitles.sh`
- `scripts/inspect_video.sh`

建议优先使用 workspace + timeline 路线，避免字幕层在录屏阶段受页面重绘/语言切换影响。
