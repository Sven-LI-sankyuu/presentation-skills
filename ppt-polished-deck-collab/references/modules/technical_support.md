# Technical Support

**这份文档的定位。** 本文定义 `ppt-polished-deck-collab` 的技术支持体系，回答“某类页面应使用什么 SDK、什么工具、什么代码路径、什么验证方式”。它是 skill 的技术总索引，不负责替代各专项细则。

## 目录

- 技术支持的边界
- asset slot 模块接口
- 状态标签
- 技术支持总表
- 当前已落地的主链路
- 工具栈与职责
- 如何选择技术路线
- 技术选择查表
- 验证映射
- 与旧复杂图 skill 的衔接
- 下一步技术扩展清单
- 细化阅读路径

## 什么时候先读它

**当你已经知道 deck 要表达什么，但还没决定实现路径时，先读这份文档。** 它先给出技术支持全景，再把你路由到更细的专项文档或脚本。

## 技术支持的边界

**技术支持回答实现问题。** 它关心对象能否编辑、图能否复跑、脚本怎么组织、预览怎么导出、结构怎么校验、环境依赖是什么。

**技术支持不替代设计支持。** “这页该不该用系统架构图”“该用原生柱状图还是 Python 生成的热力图”首先是设计判断，技术支持只在设计判断之后决定最合适的落地路线。

## asset slot 模块接口

**所有资产模块都通过 `asset_slot` 接入。** slot 是页面合同的一部分，至少应包含 `slot_id`、`asset_type`、`module`、`backend`、`validation_mode` 和 `status`。复杂任务再补 `page_role`、`input_files`、`output_files`、`constraints`、`aspect_ratio`、`crop_policy` 和 `editable_expectation`。

**模块的共同职责是四步。** 读取 slot，生产 artifact，回写 `output_files/status`，把验证证据放进 `validation/`。模块不应绕过 slot 直接把文件塞进页面，也不应在资产生产阶段重新决定页面叙事。

**slot 状态需要忠实暴露。** `pending_user_generation` 表示等待用户用网页端 GPT 生图并把图片放回 workspace；`blocked` 表示缺数据、缺权限、缺模板或环境不满足。不要用空图片、占位 prompt 或假的输出文件把状态伪装成已完成。

## 状态标签

**当前所有技术模块都带状态标签。**
- `available`: 已经在 skill 内有文档、脚本或资产，能直接复用
- `partial`: 已经有部分积累，但还没收口成标准模块
- `planned`: 已经纳入 skill 规划，但当前还没有稳定脚本或统一接口

## 技术支持总表

| 资产模块 | 主要实现 | 主要 SDK / 工具 | Editable | 当前状态 | 默认验证 |
| --- | --- | --- | --- | --- | --- |
| `text-layout-native` | 文本框、卡片、基础版式 | `python-pptx` | 高 | `available` | `preview_only` |
| `diagram-connector` | 真绑定复杂图、系统架构图、依赖图 | `python-pptx` + `pptx XML` 校验 | 高 | `available` | `diagram_connector` |
| `diagram-visual` | 纯视觉流程图、层次图、研究示意图 | `python-pptx`，可选 Mermaid 草稿 | 高 | `available` | `diagram_visual` |
| `office-chart-native` | PowerPoint / Office 原生可编辑图表 | `python-pptx chart` API | 高 | `available` | `chart_editable` |
| `python-figure-image` | 高复杂度图、研究图、热力图、排序图 | `matplotlib` / `seaborn` / `pandas` | 低到中 | `available` | `chart_image` |
| `table-native` | 原生数据表、明细页、附录表 | `python-pptx` table | 中 | `available` | `preview_only` + `visual_review` |
| `image-hero` | 背景图、产品图、截图、照片 | 图片文件 + `python-pptx` | 低 | `available` | `preview_only` |
| `icon-accent` | 标题旁图标、卡片锚点、导航增强 | `icon_registry.py` + `PyMuPDF` | 低 | `available` | `preview_only` |
| `image-generation` | GPT 生图、强风格 hero 图、场景图、截图再设计 prompt | `generate_image_asset.py` 或 manual web | 低 | `available` | `image_generated` |

## 当前已落地的主链路

**当前 deck 构建的硬主链路是 `slide_contracts + asset_slots + python-pptx + preview export + validation`。** 这是 skill 现阶段最稳定的可发布路线，也是所有新模块接入时必须兼容的基础。

**当前已经收口的脚本能力如下。**
- `scripts/check_environment.py`
- `scripts/check_pptx_package_preflight.py`
- `scripts/check_pptx_structure_precheck.py`
- `scripts/check_pptx_render_review.py`
- `scripts/export_pptx_previews.py`
- `scripts/check_pptx_connectors.py`
- `scripts/lint_deck_assets.py`
- `scripts/icon_registry.py`
- `scripts/generate_image_asset.py`
- `scripts/ppt_quality_helpers.py`
- `scripts/ppt_asset_helpers.py`
- `scripts/python_figure_helpers.py`

**当前最成熟的专项能力仍然是 diagram connector。** 复杂图的真绑定 connector、`pptx XML` 校验、PowerPoint 预览导出，是目前最强的工程壁垒，应继续作为新 skill 的深能力保留。

**当前 GPT 生图已经有最小 API backend。** `scripts/generate_image_asset.py` 负责单个 `image-generation` asset slot 的 API 生图、图片落盘和 metadata 记录；`manual-web` 仍用于没有 API 权限或需要用户网页端生成的场景。真实执行时应如实记录 `generated`、`pending_user_generation` 或 `blocked` 状态。

## 工具栈与职责

| 工具 / SDK | 职责 | 是否硬依赖 | 当前状态 |
| --- | --- | --- | --- |
| `python-pptx` | 生成 editable `pptx`、文本框、形状、图表、connector | 是 | `available` |
| PowerPoint Automation | 高保真导出 `PDF -> PNG` | 否 | `available` |
| LibreOffice | 无 Office 环境的预览导出备选 | 否 | `available` |
| `pdftoppm` | PDF 到 PNG 的高质量渲染 | 否 | `available` |
| `PyMuPDF` | PDF 渲染、SVG 渲染、icon 主 backend | 否 | `available` |
| Mermaid | diagram 草稿和讨论层 | 否 | `partial` |
| `matplotlib` / `seaborn` / `pandas` | Python figure 生成 | 否 | `available` |
| GPT Image API / ChatGPT web | 强风格图片、场景图和 prompt-driven image slot | 否 | `available` |

## 如何选择技术路线

**先判断是不是必须 editable。** 只要页面后续会改文字、调位置、换数字、拖节点，就优先走原生 editable 路线。

**结构图先判断是否需要拖动维护。** 需要拖动维护的系统架构图、dataflow、dependency map 走 `diagram-connector`。只服务表达的研究示意图、war-room board、概念流程图走 `diagram-visual`。

**图表先判断数字是否会继续改。** 会后高概率继续改数、改系列、改图例的页，应优先走 `office-chart-native`。一次性、视觉密度极高、超出 Office 图表表达能力的页，走 `python-figure-image`。

**icon 永远是补充资产。** icon 只负责节奏增强、导航锚点和轻语义提示，不应替代主结构、主图表和主证据。

**背景不是图片模块。** 如果页面只是需要底色、纸纹、渐变、浅网格、装饰色块或整页视觉底板，应优先使用 `slide.background.fill`、母版背景、原生形状、线条和透明度组合。`image-hero` 和 `image-generation` 只用于有独立资产角色的照片、产品场景、截图、主视觉或概念视觉，不用于把整页版式烤成背景图。

**生图永远不承载精确证据。** `image-generation` 适合氛围图、场景图、产品情境图、强风格 hero 图和截图再设计，不适合生成带精确数字、财务事实、复杂文字或真实 logo 的证据图。

**字体策略需要端到端落地。** 当 deck 存在中英混排，且 `python-pptx` 或底层 helper 只能部分写入字体信息时，可以在最终 `pptx` 上补做 XML 级字体槽位修正，统一 `latin` 与 `ea` 字体。不要把“Office 自己会选字体”当成稳定方案。

**表格语义需要显式传入。** `table-native` 页应在 build 脚本或页面 spec 中声明 `numeric_columns`、`index_columns`、`text_columns` 或等价字段。表头默认居中，index / 类目列和文本列居左，财务数值列靠右，所有单元格上下居中。不要只靠“第几列以后都是数字”的隐式推断，除非该表非常小且已在代码里写清楚例外。

**表格单元格要显式上下居中。** 构建脚本应对每个非空单元格设置 `cell.vertical_anchor = MSO_VERTICAL_ANCHOR.MIDDLE`。`None`、`top`、`bottom` 等状态会在 `structure_precheck` 中生成 `table_cell_vertical_alignment_not_centered` warning；warning 允许继续，但默认应修复，模板确有特殊表格规则时才记录例外。

**表格段落缩进要显式归零。** PPT 段落 API 暴露 `level`，底层 `a:pPr` 还可能保存 `marL`、`marR` 与 `indent`。构建脚本应把表格单元格内段落的 `level` 设为 `0`，并移除或归零这些 OOXML 缩进属性；`structure_precheck` 检出非零值时生成 `table_paragraph_special_indent` warning。只有单元格承载大段连续文本且版式确实需要首行缩进时，才保留并写入 review note。

## 技术选择查表

| 页面特征 | 推荐技术模块 | 原因 | 不推荐路线 |
| --- | --- | --- | --- |
| 系统架构图需要后续手改节点 | `diagram-connector` | 拖动后连线仍绑定 | 纯图片、视觉假线 |
| 管理层流程解释页 | `diagram-visual` | 阅读负担低，结构够清晰 | 默认上 connector |
| KPI 趋势页要周周改数 | `office-chart-native` | 数据和图例可继续编辑 | 把折线图烤成图片 |
| 研究热力图、密集散点、复杂排序图 | `python-figure-image` | 表达能力强 | 强行用 Office chart 拼凑 |
| 明细数据、财务表、附录表 | `table-native` | 行列语义清晰且可继续编辑 | 用 shape grid 冒充数据表 |
| 摘要页、结论页、章节页 | `text-layout-native` + 可选 `icon-accent` | 以语言和层次为主 | 先找图再拼页 |
| 截图、产品界面、品牌大图 | `image-hero` | 图片本身就是证据 | 用整页图片冒充背景底板 |
| 强风格 hero、场景化视觉、概念主图 | `image-generation` | 视觉情绪与记忆点优先 | 把精确数字、长文字或整页版式交给生图 |

**deck 级质量 gate 分两段。** `package_preflight` 与 `structure_precheck` 负责 `build` 后的文件级与结构级检查；`render_review` 负责 `preview` 后的成图级检查。

## 验证映射

| 技术模块 | 最低验证证据 |
| --- | --- |
| `package_preflight` | 时间戳归档的 `package_preflight_YYYYMMDD_HHMMSS.json/.md` |
| `structure_precheck` | 时间戳归档的 `structure_precheck_YYYYMMDD_HHMMSS.json/.md` + 可选 `shape_inventory.json` |
| `render_review` | 时间戳归档的 `render_review_YYYYMMDD_HHMMSS.json/.md` |
| `text-layout-native` | 逐页预览图 + 人工复核 |
| `diagram-connector` | connector 报告 + 逐页预览图 |
| `diagram-visual` | 逐页预览图 + 主路径人工复核 |
| `office-chart-native` | 逐页预览图 + 图表可编辑性确认 |
| `python-figure-image` | 逐页预览图 + 比例 / 清晰度检查 |
| `table-native` | `structure_precheck` 表格格式 warning + 逐页预览图 + 表格列语义、表头居中、文本 / 数值对齐人工复核 |
| `icon-accent` | 逐页预览图 + 颜色 / 对比度检查 |
| `image-generation` | prompt 文档 + 生成参数 / backend + 输出文件 + 事实 / 文字 / 安全区复核 |

## 与旧复杂图 skill 的衔接

**旧 skill 的技术强项应模块化并入。** 应优先继承以下能力：
- `python-pptx` connector 真绑定
- `pptx XML` 结构校验
- Mermaid 草稿层
- PowerPoint 高保真预览导出

**旧 skill 的单图叙事不应整体搬入。** 新 skill 的主对象是 deck，不是单图图包，因此图表模块必须挂到 `slide_spec.asset_mode` 之下，而不是反过来让所有页面围着复杂图工作流转。

## 下一步技术深化清单

**当前三个模块已经接入 skill。** diagram、Office native chart 和 Python figure 都已经有对应文档、helper 或环境探测支持。

**下一步要做的是深化，而不是从零接入。**
- 把 diagram helper 从“节点 + connector”继续扩展到更完整的架构图语法模板
- 给 native chart 补更多稳定模板，例如 line、stacked、combo 的页面套路
- 给 Python figure 补更多研究图类型和可复用 layout 规范

**这些深化工作仍然要服从统一 workflow。** 不论是 diagram、Office chart、Python figure、icon 还是 GPT 生图，都必须回到 `deck_contract -> slide_contracts -> asset_slots -> build -> validation -> preview` 这条主链路。

## 细化阅读路径

**选 backend、环境和导出路线时，继续读 `references/workflow/build_routes.md`。** 它负责更细的实现路线与环境注意事项。

**做 deck 级文件安全 / 兼容性 / 结构排版 / 成图级 gate 时，继续读 `references/workflow/quality_gates.md`。** 它负责 `package_preflight`、`structure_precheck` 与 `render_review` 的职责分层、输出目录和失败语义。

**做复杂图时，继续读 `references/modules/diagram_support.md`。** 它负责 connector、视觉语法、edge budget 和 Mermaid 草稿层的使用边界。

**做原生图表时，继续读 `references/modules/office_chart_support.md`。** 它负责 native chart 的适用场景、helper 和验证方式。

**做 Python figure 时，继续读 `references/modules/python_figure_support.md`。** 它负责高 DPI 图片图表的当前库栈、helper 和输出规范。

**做 icon 资产时，继续读 `references/modules/icon_system.md`。** 它负责 icon registry、自动着色和 SVG / PNG 落地细则。

**做 GPT 生图、manual web prompt 或截图再设计时，继续读 `references/modules/image_generation_support.md`。** 它负责 prompt 文档、backend、slot 状态、比例、安全区和事实复核。
