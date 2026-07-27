# Principles

**这份文档的定位。** 本文定义 `word-polished-doc-collab` 的核心业务逻辑与开发逻辑，给出稳定对象、版式契约和 references 分层地图，让 Markdown、DOCX、Python 资产与后续 Office 原生对象共享同一套定义。

## 核心对象

**`workflow_mode` 是最小路由对象。** 文档任务首先被分成 `lightweight` 和 `refined`。轻量模式追求最小可交付路径，精细模式追求可复用 workspace、资产分流和验证闭环。

**`doc_workspace` 是协作对象，不是单一目录模板。** 轻量模式可以只有 `doc.md + assets + out`。精细模式才默认围绕 `original/`、`markdown/`、`build/`、`temp/` 与 `scripts/` 组织长期协作。

**`source_docx` 是收到的原始文件对象。** 它负责保留外部来源和初始样貌，不承担长期迭代编辑职责。

**`canonical_markdown` 是默认的人类维护对象。** 一旦文档进入“持续修改、批量统一样式、版本可审计”的阶段，Markdown 应成为默认可维护源，而不是继续在导出的 `.docx` 上人工小修小补。

**`style_profile` 是最小版式对象。** 它统一定义中英文字体组合、标题梯度、正文/表格字号、首行缩进、行距、段前段后、caption 规则和表格对齐。没有显式 `style_profile` 的流水线，本质上没有真正锁定版式。

**`caption_policy` 是 `style_profile` 的组成部分。** 它至少定义 `table_title`、`figure_title`、`table_caption`、`figure_note`、`source_note` 的位置和段落节奏。默认中文正式文档和咨询报告 preset 可以拥有不同的 `figure_title` 位置，但不能模糊不写。

**`asset_mode` 是最小资产路由对象。** 每个复杂视觉资产至少属于 `office_native_chart`、`office_native_illustration` 或 `python_figure` 之一。没有 `asset_mode` 的精细模式资产体系，后续无法稳定验证编辑性和来源。

**`asset_manifest` 是精细模式的条件性资产清单对象。** 当文档包含多张图表、Office 原生对象、生成脚本、来源说明或多种 caption 位置时，应显式维护资产清单；纯文本或只有极少简单静态图片的精细模式任务，可以不为形式主义强行引入它。

**`block_role` 是最小语义块对象。** 一个段落或对象至少要先被识别为 `doc_title`、`subtitle`、`heading_1`、`heading_2`、`heading_3`、`body`、`list`、`table_title`、`table_body`、`table_caption`、`figure_body`、`figure_title`、`figure_note`、`source_note` 或 `code_block`，再谈视觉样式。

**`light_delivery_bundle` 是轻量模式的最小验收对象。** 它至少包含 Markdown 源或输入 Word、输出 `.docx`，以及必要的图片资产。轻量模式默认不强制单独 review 记录。

**`validation_bundle` 是精细模式的最小验收对象。** 完整交付至少包含 Markdown 源、输出 `.docx`、必要的中间资产、关键参数说明、一次可追溯的复核记录，以及在存在复杂视觉资产时对应的 `asset_manifest`。没有验证证据的精细模式导出物不算完成。

## 顶层原则

**Markdown-first，原件归档。** 默认把原始 Word 留在 `original/`，把 Markdown 作为长期可维护对象，再从 Markdown 统一导出正式 `.docx`。

**语义优先于视觉。** Markdown 应先表达“这是标题、正文、表题、表注还是图题”，而不是用空行、加粗和手工缩进去赌渲染结果。

**Style profile 必须显式。** 中英文字体组合、字号、行距、段前段后、caption 位置必须能被明确声明、读取和复用，而不是散落在脚本常量里。

**模式切换必须单调。** 轻量模式是最小交付路径，精细模式是在轻量模式之上追加资产清单、可编辑对象和验证闭环，不应出现“先定义重流程，再在边上写一堆轻量例外”的结构。

**Correct-failure。** 字体缺失、图像缺失、表图语义不完整、构建路线不满足精度要求时，应直接失败并暴露原因。禁止静默降级。

**视觉规则和技术路线显式分层。** 版式规范由 `typography_profiles.md` 管，技术实现边界由 `technical_support.md` 管，具体路线选择由 `build_routes.md` 管。

## 默认版式契约

**正文是主档位。** 默认正文使用 `中文宋体 + 英文 Times New Roman + 小四 12pt + 首行缩进 2 字符`，它是整份文档的基准，不应被频繁改写。

**标题梯度必须单调递减。** 标题等级越高，字号越大，且同级标题在整个文档中保持一致。

**正文和标题共享基础段落节奏。** 正文与标题默认使用 `1.5` 倍行距，段前段后统一为 `0.5` 行。实现层为了跨 Word 引擎稳定，统一按 `6pt` 落地。

**表格是独立密度体系。** 表格正文默认 `五号 10.5pt`，密表允许降到 `小五 9pt`，段前段后与首行/悬挂/左右缩进均为 `0`，不继承正文段落节奏。单元格内容默认上下居中；表头默认水平居中，左侧索引列左对齐，右侧数值列右对齐。长文本单元格或外部模板存在明确版式理由时可以保留缩进或其他垂直对齐方式，并在 QA warning 中记录例外理由。

**Warning 表示可解释的默认契约。** Agent 检测到 warning 时默认修复；只有存在明确业务、内容或模板理由时才保留偏离，并在 handoff 或复核记录中说明理由。warning 不改变自动 gate 的通过状态。

**表图说明有稳定文面，位置由 `caption_policy` 决定。** 表题和图题优先直接写成 `表 3 ...`、`图 2 ...` 这种最终交付文本。`cn_song_times` 默认使用“表题在表上方、图题在图下方、表注在表下方”的中文正式文档规则；preset 可以显式覆盖 `figure_title` 位置。

## 字体 profile 原则

**默认 profile 是 `cn_song_times`。** 这套 profile 使用中文 `宋体`、英文 `Times New Roman`，用于大多数正式中文文档。

**`cn_kaiti_times` 是正式强调 profile。** 这套 profile 使用中文 `楷体`、英文 `Times New Roman`，适合引用、签批说明、强调性正式段落，不应把整份密集技术文档全部切成楷体。

**`cn_heiti_arial` 是展示型 profile。** 这套 profile 使用中文 `黑体`、英文 `Arial`，适合现代商务风格的标题、标签、图表短标题和局部强调。

**Profile 是可选路由，不是自由混搭。** 一个文档可以允许多个 profile 共存，但必须先定义每个 profile 对应的 block role，不能在段落级随意漂移。

## 资产层原则

**表格、图片、原生图表、原生插图、Python figure 都是文档资产。** 它们共享同一套标题、编号和说明体系，不应被当作临时插图处理。

**Office 原生 visual 是重要路线。** 只要用户后续要编辑数据、KPI 卡片、流程框、标签或图例，Office 原生 chart / illustration 都比纯图片更合适。

**Python figure 服务高复杂度表达。** 研究图、热力图、复杂时间线和统计图可以走 Python figure 路线，但字体、色彩、图注和页内宽度仍应服从文档 style profile。

## 文档分层

**轻量模式默认先读一份入口文档。** 如果任务明显属于轻量模式，默认先读 `lightweight_mode.md` 即可，只有在能力边界不够时再升级到更重文档。

**精细模式核心文档有四份。** 默认先读：
- `principles.md`
- `doc_workflow.md`
- `typography_profiles.md`
- `technical_support.md`

**专项文档按需读取。** 只有在需要更细路线或验证时，再读：
- `build_routes.md`
- `office_chart_support.md`
- `python_figure_support.md`
- `quality_gates.md`
- `local_pipeline_case_study.md`
- `preset_style_guides.md`
