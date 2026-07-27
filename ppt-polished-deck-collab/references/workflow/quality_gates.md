# Quality Gates

**这份文档的定位。** 本文定义 `ppt-polished-deck-collab` 在 `build` 之后应经过的三道 deck 级质量 gate：`package_preflight`、`structure_precheck` 与 `render_review`。它回答的是“PPT 文件能不能安全外发、结构层是否已经失控、成图层是否还藏着结构看不见的问题”，不是“页面美不美”。

## 为什么要单独设 gate

**这三类问题的根因不同。** `package_preflight` 关心的是文件包结构、元信息一致性、移动端兼容风险和外发安全；`structure_precheck` 关心的是结构可见层的文字边界、对象遮挡和结构化对象内部排版风险；`render_review` 关心的是只有成图之后才能看到的问题，例如边界触墨和扁平化图像内部的文字风险。

**把它们拆开更干净。** 一个 gate 失败时，agent 可以直接知道是“文件级问题”“结构层问题”还是“成图层问题”，而不是在一份混杂报告里猜。

## 在主链路中的位置

**推荐主链路。** `brief -> style/domain profile lock -> template audit(if pptx) -> narrative -> derive slide_specs -> planning_checkpoint -> assets -> build -> package_preflight -> structure_precheck -> module_validation -> preview -> render_review -> visual_review/contact_sheet -> first_draft_checkpoint -> final`

**执行顺序必须固定。**
- 先跑 `package_preflight`，确认 deck 文件本身没有内部不一致和移动端高风险信号。
- 再跑 `structure_precheck`，确认文本框 fit、遮挡和结构化对象边界没有明显问题。
- 再跑 `connector`、`chart_editable` 等模块级 validation。
- 再做逐页 preview。
- 预览图落盘后跑 `render_review`，补足结构层看不到的边界触墨和扁平化图像风险。
- 最后看逐页 preview 或 contact sheet，做人工 visual review，再进入 first draft checkpoint 或 final。

## Validation Bundle

**输出目录建议固定如下。**

```text
validation/
  package_preflight/
    history/
      package_preflight_YYYYMMDD_HHMMSS.json
      package_preflight_YYYYMMDD_HHMMSS.md
  structure_precheck/
    history/
      structure_precheck_YYYYMMDD_HHMMSS.json
      structure_precheck_YYYYMMDD_HHMMSS.md
    shape_inventory.json
  render_review/
    history/
      render_review_YYYYMMDD_HHMMSS.json
      render_review_YYYYMMDD_HHMMSS.md
```

**这三个 bundle 都属于 deck 级证据。** 它们不是某一页的 `validation_mode` 替代品，而是 final delivery 前的统一质量 gate。

**推荐优先使用 `--workspace-dir` 自动归档。** 这样每次执行都会按标准目录写入带时间戳的 `json + md` 报告，后续更适合回溯、对比和复盘。

**visual review 也应留下证据。** 推荐在 `validation/visual/review_log.md` 或 `final/handoff.md` 中记录最新 preview 路径、contact sheet 路径、fatal / warning / preference 结论，以及是否存在人工接受的 residual risk。

## 问题类型分层

**先按可见性分层，再按规则分型。**

| 层级 | Gate | 典型问题 |
| --- | --- | --- |
| 文件级 | `package_preflight` | `docprops_slide_count_mismatch`、`stale_section_reference`、移动端兼容风险 |
| 结构可见层 | `structure_precheck` | `textbox_fit_failure`、`text_occluded_by_shape`、`table_cell_vertical_alignment_not_centered`、`table_paragraph_special_indent`、`structured_chart_label_collision_not_checked` |
| 成图可见层 | `render_review` | `boundary_touch_ink_bottom`、`boundary_touch_ink_right`、`flattened_graphic_internal_text_requires_review` |

**同一个视觉故障可能跨层存在。** 例如图表内部标签打架，如果图表仍是结构化对象，优先在 `structure_precheck` 里处理；如果它已经压成图片，就必须进入 `render_review` 或后续 OCR 终检。

## `package_preflight`

**它检查的是文件级一致性与兼容风险。** 首期重点覆盖以下问题。
- `zip_integrity_failure`
- `presentation_slide_count_mismatch`
- `docprops_slide_count_mismatch`
- `stale_section_reference`
- `missing_slide_relationship_target`
- `slide_relationship_count_mismatch`
- `mobile_compatibility_embedded_object`

**这类问题应优先按 `error` / `warning` 处理。** 文件内部不一致通常不是视觉问题，而是“某些解析器直接拒绝打开”的问题。移动端微信和移动端 WPS 都属于更脆弱的解析器，应优先被这道 gate 保护。

**推荐命令。**

```bash
python scripts/check_pptx_package_preflight.py \
  --pptx <path/to/deck.pptx> \
  --workspace-dir <path/to/deck_workspace> \
  --fail-on error
```

## `structure_precheck`

**它检查的是结构层排版合理性。** 当前重点覆盖以下结果。
- `textbox_fit_failure`
- `text_occluded_by_shape`
- `font_size_off_half_point_grid` / `font_size_outside_theme_scale` / `body_text_below_theme_token` / `table_font_below_theme_token`
- `font_size_below_caption_floor` / `font_size_fragmentation`
- `table_cell_vertical_alignment_not_centered`
- `table_paragraph_special_indent`
- `structured_chart_label_collision_not_checked`
- `full_slide_picture_background_risk`

**它现在还应显式汇报量化指标。** 首期至少应给出：
- `overflow_ratio`
- `bottom_gap_pt`
- `right_gap_pt`
- `overflow_area_pt2`

**首期先做结构预检，不直接做 PNG 终检。** 结构预检更适合当前 skill，因为它能在 `slide_id / shape_id` 层直接指出问题位置，也更容易驱动 agent 定向修复。

**整页图片默认拦截。** `full_slide_picture_background_risk` 用来防止把整页 PNG / JPG 当成背景底板。默认严重级别是 `error`；如果页面确实是声明过的 full-bleed `image-hero` 或 `image-generation` 主视觉，才可以在明确记录原因后用 `--full-slide-picture-severity warning` 降级。

**首期边界必须写清楚。** 对已经图片化的复杂图、外部导入图和 chart 内部细粒度标签，首期允许显式输出 `not_checked`，而不是假装通过。

**推荐命令。**

```bash
python scripts/check_pptx_structure_precheck.py \
  --pptx <path/to/deck.pptx> \
  --workspace-dir <path/to/deck_workspace> \
  --inventory-out <path/to/deck_workspace/validation/structure_precheck/shape_inventory.json> \
  --fail-on error
```

## `render_review`

**它检查的是成图后才会暴露的问题。** 首期重点覆盖以下两类结果。
- `boundary_touch_ink_bottom` / `boundary_touch_ink_right`
- `flattened_graphic_internal_text_requires_review`

**`boundary_touch_ink` 的意义是补结构估算的盲区。** 当最后一行或最后几个字只被切掉 1 到 3 像素时，纯结构预检不一定稳定，而成图 strip 检查更容易直接发现“字形笔画已经触边”。

**首期的 `render_review` 不是 OCR 终检完整版。** 它先用预览图做边界触墨和扁平化对象的风险提示，后续再把 OCR、label overlap 和图像内部文字检测继续补上。

**推荐命令。**

```bash
python scripts/check_pptx_render_review.py \
  --pptx <path/to/deck.pptx> \
  --preview-dir <path/to/ppt_preview> \
  --workspace-dir <path/to/deck_workspace> \
  --fail-on error
```

## 失败语义

**这三个 gate 都不允许静默降级。**
- `error`：默认阻断后续流程。
- `warning`：允许继续，但默认应修复；有模板、业务语义或版式理由保留时，必须进入 review note。
- `not_checked`：必须显式写入报告，供后续 `render_review`、preview review 或 OCR 终检接手。

**不要把 `not_checked` 当成通过。** 它只表示“当前 gate 没能力判断”，不表示“当前页面没有问题”。

## 与模块级 validation 的关系

**deck 级 gate 分成两段。** `package_preflight` 与 `structure_precheck` 在 `build` 后立即执行；`render_review` 在 preview 导出后执行。

**模块级 validation 不能替代 deck 级 gate。** connector 通过不代表文件能在移动端打开；逐页 preview 正常也不代表 `docProps` 和 `sectionLst` 一致；结构预检通过也不代表图片内部标签没有互相打架。

**typography 与 table profile 需要同时进入自动 gate 和 visual review。** 中文正式材料的宋体 / Times 字体槽、正文段落、表格字号、表格上下居中和表格特殊缩进已经由 `structure_precheck` 提供结构层 warning；表头居中、文本 / 数值水平对齐、研报质感、版心纪律、图号单位和免责声明位置仍应在 preview contact sheet 与人工 visual review 中确认，不能仅凭 `render_review` 通过就把最终 PPTX 放入 `final/`。

**表格格式 warning 是 advisory。** `table_cell_vertical_alignment_not_centered` 与 `table_paragraph_special_indent` 不阻断交付，但默认应在当前修订轮处理。外部模板有明确单元格垂直对齐规则，或单元格承载大段连续文本并确实需要首行缩进时，可以记录例外并继续。

**typography token 要被抽查兑现。** visual review 应抽查封面、章节页、正文页、图表页和表格页，确认 hero / section / page title / subtitle / body / label / caption / table 文本符合 `theme_tokens`。低于 `body_font_pt` 的正文、低于 `table_font_pt` 的表格、碎片化字号和临时字体切换都应记录为 warning 或 preference fix，不能被当成自然排版差异。

**字号提醒使用压缩报告。** 默认字号网格为 `0.5pt`，因此 `10.5pt` 合法而 `9.6pt`、`11.3pt` 需要提醒。`lint_deck_assets.py` 扫描 source/config 层的字号 literal，`structure_precheck` 扫描 PPTX 产物层的可见字号。字号问题默认是 `warning/advisory`，不因单个小数档位阻断交付；如果同页同时存在文本越界、遮挡或包结构错误，对应 finding 会独立 hard block。

**字号修复优先使用 active token。** 能解析 role 时，reminder 直接显示 active `theme_tokens` 的推荐值，例如中文正文 `theme_tokens.body_font_pt=12pt`、中文表格 `theme_tokens.table_font_pt=10.5pt`。最近 `0.5pt` 只在无法解析 role token 时作为临时候选，不能替代 active contract。

**页面可见文案也要进入 visual review。** 自动 gate 主要检查结构和成图风险，不能判断一句话是否属于外发页面。人工复核应抽查标题、正文、卡片、图注和章节页，确认没有把 `Narrative Role`、讲者提示、协作说明、敏感性处理策略或“这页 / 本部分 / 公开课应 / 建议讲者 / 帮助听众理解”等元叙述直接放到 PPT 可见层。

## 当前脚本

**当前已预设的脚本如下。**
- `scripts/ppt_quality_helpers.py`
- `scripts/check_pptx_package_preflight.py`
- `scripts/check_pptx_structure_precheck.py`
- `scripts/check_pptx_render_review.py`

**后续可以继续细化，但主接口不要再变。** 首期优先稳定脚本命名、输入输出格式、问题类型分层和 validation bundle 目录，细节规则与阈值后续迭代。
