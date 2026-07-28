# Schema Contract

**这份文档的定位。** 本文定义 `ppt-polished-deck-collab` 的轻量合同对象：`deck_contract`、`slide_contract`、`asset_slot` 和 `validation_bundle`。这些对象用于统一语言、减少分叉和约束关键风险，不是要求每个小任务都填写复杂 schema。

## 使用原则

**简单任务走轻量路径。** 纯文本润色、少量页面重排、已有模板内改几页、单张图表补强等任务，可以只记录最小 brief、关键页面合同和验证证据。

**复杂任务使用完整合同。** 新建整套 deck、强模板继承、多模块资产、GPT 生图、复杂 diagram、正式研报和需要外发复用的材料，应完整使用 `deck_contract -> slide_contract -> asset_slot -> validation_bundle`。

**合同是执行边界。** build 脚本和人工 review 都应围绕合同工作。不要在组装 PPT 时临时发明业务逻辑、页面意图或资产路线。

## `deck_contract`

`deck_contract` 是 deck 级合同，记录不会频繁变化的全局事实。它可以放在 `brief.md`，也可以作为 `deck_narrative.md` frontmatter 里的 `deck` mapping。

**建议字段如下。**

```yaml
deck:
  title: "<deck title>"
  audience: "<target audience>"
  scenario: "<meeting / sendout / class / roadshow>"
  objective: "<decision / understanding / action>"
  source_context: "no_template"
  delivery_context: "hybrid_review_deck"
  communication_profile: "business_report"
  visual_profile: "corporate_clear"
  density_profile: "balanced_brief"
  editability_profile: "fully_editable"
  template_file: null
  personalization:
    speaker_or_brand_voice: null
    desired_impression: null
    must_emphasize: []
    must_avoid: []
    visual_likes: []
    visual_dislikes: []
  theme_tokens:
    typography_profile: "zh_formal"
    domain_profile: null
    visual_theme_preset: null
    page_width_in: 13.333
    page_height_in: 7.5
    hero_title_font_pt: 40
    section_title_font_pt: 30
    page_title_font_pt: 24
    subtitle_font_pt: 16
    minor_title_font_pt: 14
    latin_font_name: "Times New Roman"
    east_asia_font_name: "宋体"
    body_font_pt: 12
    label_font_pt: 10.5
    caption_font_pt: 9
    body_line_spacing_multiple: 1.5
    title_line_spacing_multiple: 1.0
    title_paragraph_space_lines: 0.5
    body_first_line_indent_chars: 2
    body_paragraph_space_lines: 0.5
    table_font_pt: 10.5
    table_line_spacing_multiple: 1.0
    table_paragraph_space_lines: 0
    table_first_line_indent_chars: 0
    table_vertical_anchor: "middle"
    table_header_alignment: "center"
    table_index_alignment: "left"
    table_text_alignment: "left"
    table_numeric_alignment: "right"
```

**`source_context`。** 推荐值：`template_locked`、`template_guided`、`content_migration`、`brand_assets_only`、`no_template`。

**`delivery_context`。** 推荐值：`self-contained_reading_deck`、`speaker-led_stage_deck`、`hybrid_review_deck`、`reference_or_appendix_deck`。

**`communication_profile`。** 推荐值：`business_report`、`technical_explainer`、`research_review`、`keynote_story`。

**`visual_profile`。** 推荐值：`corporate_clear`、`editorial_ink`、`swiss_modernist`、`product_launch`。它只定义视觉语言，不替代 `delivery_context`、`communication_profile` 或 `domain_profile`。

**`density_profile`。** 推荐值：`dense_reference`、`balanced_brief`、`low_density_stage`。

**`editability_profile`。** 推荐值：`fully_editable`、`chart_editable`、`mixed_assets`、`snapshot_allowed`。

**`personalization`。** 可选且向后兼容的 mapping，用于记录 Grill-Me 中无法由现有 profile 完整表达的个性化护栏。能够映射到 `audience`、`scenario`、`objective`、现有 profile、`theme_tokens` 或资产路线的答案仍写入原字段，不重复创建平行字段。旧 workspace 可以省略整个 mapping。

**`theme_tokens.domain_profile`。** 推荐值按任务扩展，例如 `financial_report_review`。它用于表达研报、财报点评等行业文体纪律，可以和 `visual_profile: editorial_ink` 或 `swiss_modernist` 同时存在。

**`theme_tokens.visual_theme_preset`。** 可选字段，用于记录少数经过验证的视觉主题预设，例如 `editorial_ink_indigo_porcelain`、`editorial_ink_kraft`、`swiss_ikb`、`swiss_safety_orange`。它不开放任意配色自由，主要服务复现与 review。

**`theme_tokens` 是正式 deck 的排版合同。** build 前应已经锁定标题、正文、标签、图注和表格 token。构建脚本应读取或显式映射这些 token；低于 `body_font_pt` 或 `table_font_pt` 的正文 / 表格文字属于 review 风险，不能用来常规解决空间不足。

## `workflow`

`workflow` 是 `deck_narrative.md` frontmatter 的顶层 mapping，记录 Grill-Me 与五阶段生产的执行状态。它不属于 `deck_contract`，也不改变旧 workspace 的 deck schema。

```yaml
workflow:
  version: 1
  state: "questioning"
  outline_version: null
  approval:
    status: "pending"
    outline_version: null
    evidence: null
    approved_at: null
```

**状态。** 只允许 `questioning`、`outline_ready`、`awaiting_outline_feedback`、`outline_approved`、`executing`、`reviewing`、`revising`、`final`、`blocked`、`stopped`。

**批准绑定版本。** `outline_version` 在完整大纲首次生成时赋值，实质修改后递增。完整 build 前，`approval.status` 必须为 `approved`，`approval.outline_version` 必须等于当前 `outline_version`，`approval.evidence` 必须保存用户对当前完整大纲的明确批准原话或持久化引用。大纲发生实质修改时，将批准重置为 `pending`。

**兼容性。** 旧 workspace 缺少 `workflow` 时，验证脚本默认给出 warning；新 deck 和重大重构必须使用 `--require-workflow`，缺少该 mapping 时阻断 build。

## `slide_contract`

`slide_contract` 是页面级合同，默认从 `deck_narrative.md` 的每页 `yaml slide_spec` 派生。旧字段继续保留，新增字段按风险渐进填写。

**最小字段如下。**

```yaml
title: "<slide title>"
reader_question: "<what this page should answer>"
page_task: "persuade"
reading_mode: "decision"
archetype: "decision-logic"
asset_mode: "text-layout-native"
validation_mode: "preview_only"
key_message: "<single core message>"
required_assets: []
```

**增强字段如下。**

```yaml
layout_recipe: "business-summary-grid"
rhythm_role: "evidence"
visual_constraints:
  title_alignment: "left"
  max_accent_colors: 1
profile_validation_rules:
  - "answer_title_required"
  - "chart_source_required"
asset_slots:
  - slot_id: "s03_chart_primary"
    page_role: "main_evidence"
    asset_type: "chart"
    module: "office-chart-native"
    backend: "python-pptx"
    validation_mode: "chart_editable"
    status: "planned"
```

**`layout_recipe`。** 页面版式语法，例如 `hero-statement-accent`、`duo-compare`、`kpi-tower`、`image-hero-strip`、`matrix-with-stat`、`business-summary-grid`、`technical-layered-architecture`。

**`layout_recipe` 可以承载强设计感 native PPTX 语法。** 示例包括 `editorial-cover`、`editorial-big-number`、`editorial-product-mix-strip`、`editorial-data-pipeline`、`swiss-split-statement`、`swiss-kpi-tower`、`swiss-duo-compare`、`swiss-image-hero`。这些 recipe 仍然服从页面 `archetype`，不能绕开 `reader_question` 和 `key_message`。

**`rhythm_role`。** 页面节奏角色，例如 `opener`、`breath`、`dense`、`evidence`、`transition`、`closing`。强设计感 deck 应显式使用它控制 hero / non-hero、深浅页面、密度和章节呼吸。

## `asset_slot`

`asset_slot` 是所有资产模块的统一接口。Office 原生图表、Python figure、GPT 生图、icon、复杂 connector 图、普通图片和原生表格都应通过 slot 进入页面。

**轻量字段如下。**

```yaml
slot_id: "s05_hero_image"
asset_type: "image"
module: "image-generation"
output_files: []
validation_mode: "image_generated"
status: "pending_user_generation"
```

**完整字段如下。**

```yaml
slot_id: "s05_hero_image"
page_role: "main_visual"
asset_type: "image"
content_source: "generated"
module: "image-generation"
backend: "gpt-image-api"
aspect_ratio: "16:9"
crop_policy: "cover_center_safe_area"
editable_expectation: "snapshot_allowed"
input_files:
  - "assets/images/prompts/s05_hero_image.md"
output_files:
  - "assets/images/generated/s05_hero_image_v01.png"
constraints:
  language: "zh"
  no_page_chrome: true
  no_fake_logo: true
validation_mode: "image_generated"
status: "generated"
validation_evidence:
  - "validation/image_generation/s05_hero_image.metadata.json"
```

**`asset_type`。** 推荐值：`text`、`chart`、`figure`、`table`、`diagram`、`icon`、`image`、`prompt`、`mixed`。

**`module`。** 推荐值：`text-layout-native`、`office-chart-native`、`python-figure-image`、`table-native`、`diagram-connector`、`diagram-visual`、`icon-accent`、`image-generation`。

**`backend`。** 示例值：`python-pptx`、`matplotlib`、`seaborn`、`icon-registry`、`gpt-image-api`、`manual-web`。`gpt-image-api` 表示由 `scripts/generate_image_asset.py` 生成图片和 metadata；`manual-web` 表示 prompt 已写好但等待用户网页端生成。

**`status`。** 推荐值：`planned`、`ready`、`generated`、`pending_user_generation`、`inserted`、`validated`、`blocked`。

## `validation_bundle`

`validation_bundle` 是验收证据集合。它既包含 deck 级 gate，也包含 slot 级模块验证。

**deck 级证据。**
- `package_preflight`
- `structure_precheck`
- `preview_export`
- `render_review`
- `visual_review`

**slot 级证据。**
- `chart_editable_check`
- `connector_report`
- `figure_preview`
- `table_alignment_review`
- `icon_contrast_check`
- `image_generation_prompt_record`

**失败语义。** `error` 阻断后续流程；`warning` 允许继续但必须进入 review note；`not_checked` 必须显式写入报告，不能当成通过。
