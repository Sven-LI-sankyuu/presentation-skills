# 旁白/字幕分段（cues.json）Schema（严格版）

## 目的

该文件定义“先锁定文案，再驱动分段 TTS 与时间轴（timeline）”的输入格式。

设计原则：
- `cues.json` 只包含最终可播报/可展示的台词文本。
- 不包含导演备注、屏幕操作建议、剪辑指令（这些应放在单独文件）。
- 允许为每段绑定一个页面锚点 id，供 timeline 录屏时滚动定位。
- 若混入非台词内容，建议在生成阶段就报错并修正（避免“错误入字幕/入TTS”）。

## 顶层结构

```json
{
  "lang": "en",
  "title": "demo narration cues",
  "cues": [
    {
      "id": "step-intro",
      "text": "This section introduces the problem setup.",
      "wait": 8500
    },
    {
      "id": "step-law",
      "text": "Now we execute the flow and collect evidence."
    }
  ]
}
```

## 字段说明

- `lang`：可选，语言标记（如 `en`、`zh`）。
- `title`：可选，文案集名称。
- `cues`：必填，非空数组。

每个 cue：
- `text`：必填，最终台词（用于 TTS 与最终字幕）。
- `id`：可选，页面锚点 id（DOM element id）。用于 timeline 录屏滚动定位。
  - 例：页面某章节容器为 `<div id="step-law">...</div>`，此处写 `"id": "step-law"`。
- `wait`：可选，建议停留窗口（毫秒）。用于人为期望的节奏表达或后续校对参考。
  - 注意：在“时长驱动”的 timeline 规则下，`wait` 不是硬约束窗口，不会强行裁剪语音。

## 约束

- `text` 不能为空。
- `id` 若提供，必须是非空字符串。
- `wait` 若提供，必须是正整数（单位毫秒）。

## 反例（不要放进 cues.json）

- "Pause on chart for 3 seconds"
- "Scroll to the lower card"
- "Highlight this button"

这类内容应写到单独的导演备注/脚本文件，而不是 `cues.json`。
