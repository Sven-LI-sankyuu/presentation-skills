# 时间轴（timeline.json）Schema（严格版）

该文件定义“timeline 驱动”的统一结构：把“每段台词的起止时间 + 对应页面锚点”固化成可审计主键。

核心原则：
- `timeline.json` 是主键：录屏、混音、字幕都以它为准。
- timeline 必须是确定性的：同一份 `cues.json` + 同一套参数应生成同一份 timeline。
- 不接受隐式/自动降级：字段缺失或类型不对要直接报错。

## 顶层结构

```json
{
  "segments": [
    {
      "seg_index": 0,
      "cue_id": "step-intro",
      "text": "This section introduces the problem setup.",
      "start_sec": 0.0,
      "end_sec": 4.2,
      "duration_sec": 4.2,
      "silence_after_sec": 2.5,
      "audio_path": "…/segment_audio/seg_000.mp3"
    }
  ],
  "scroll_events": [
    {
      "after_seg_index": 0,
      "to_seg_index": 1,
      "scroll_action_at_sec": 5.5,
      "next_voice_start_sec": 6.7,
      "scroll_lag_sec": 1.2
    }
  ],
  "timeline_total_sec": 230.96,
  "schedule_total_sec": 233.46
}
```

## 字段说明

顶层：
- `segments`：必填，非空数组。
- `scroll_events`：必填，可为空数组。
- `timeline_total_sec`：必填，最后一段的 `end_sec`。
- `schedule_total_sec`：必填，包含段间静默后的总排程时长（通常 >= `timeline_total_sec`）。

每个 segment（关键字段）：
- `seg_index`：必填，0-based 连续整数。
- `cue_id`：可选，页面锚点 id（DOM element id）。录屏滚动使用它定位到对应章节。
- `text`：必填，本段台词（用于最终字幕）。
- `start_sec` / `end_sec`：必填，秒数，且 `end_sec > start_sec`。
- `duration_sec`：必填，秒数，通常 `≈ end_sec - start_sec`（允许微小舍入误差）。
- `silence_after_sec`：必填，段后静默秒数（用于听感与滚动缓冲）。
- `audio_path`：必填，分段音频文件路径（用于混音/审计）。

每个 scroll_event：
- `after_seg_index`：必填，本次滚动发生在该段之后。
- `to_seg_index`：必填，滚动目标段。
- `scroll_action_at_sec`：必填，建议执行滚动动作的时间点（秒）。
- `next_voice_start_sec`：必填，下一段语音开始时间点（秒）。
- `scroll_lag_sec`：必填，滚动后到下一段开声的最小等待预算（秒）。

## 约束

- `segments` 的 `seg_index` 必须从 0 开始递增且不缺号。
- `start_sec` 必须非负；`end_sec > start_sec`。
- `scroll_events` 引用的 `to_seg_index` 必须在 segment 范围内。
- `timeline_total_sec` 必须等于最后一个 segment 的 `end_sec`（允许 0.01s 以内的舍入误差）。

## 备注

本仓库内的一个典型生成器是 `tools/video_narration_pipeline/run_segmented_dubbing.py`：
- 逐段 TTS 得到 `duration_sec`
- 按 “段长 + 段间静默” 驱动生成 `start_sec/end_sec`
- 基于 `scroll_lag_sec` 推导 `scroll_action_at_sec`

在本 skill（独立发布）里，推荐语义为：
- 滚动动作在上一段语音结束时触发（`scroll_action_at_sec ≈ end_sec`）
- 下一段开声时间由 `max(inter_gap_sec, scroll_lag_sec)` 决定（确保滚动有足够就位时间）
