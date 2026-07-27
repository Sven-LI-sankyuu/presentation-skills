---
name: word-polished-doc-collab
description: Use when collaborating with humans to turn Markdown, DOCX, and structured visual assets into polished Word deliverables with explicit Chinese/English typography, caption policy, asset routing, and mode-aware validation. Supports lightweight and refined workflows, DOCX-to-Markdown cleanup, Markdown-to-DOCX rebuild, typography profile selection, and editable Office-native or Python-generated visual routes.
---

# Word Polished Doc Collab

## 概览
把“文档任务说清楚 + Markdown 可维护 + Word 版式统一 + 验证证据齐全”作为同一个任务完成。
默认服务 `markdown <-> docx <-> visual assets` 的往返协作流程，重点是可维护、可复跑、可控版式，不是一次性导出一个看起来差不多的文件。
这个 skill 内部提供 **轻量模式** 和 **精细模式** 两条路线。轻量模式负责最小可交付文档，精细模式负责可复用 workspace、资产分流和验证闭环。

## 什么时候用

- 用户要把 Markdown 稿件稳定地转成正式 `.docx`，并且对中英文字体组合、字号、标题层级、行距和段前段后有明确要求。
- 用户要把收到的 Word 原件抽取成 Markdown 持续维护，再统一导出风格一致的新 `.docx`。
- 用户需要把 Python 生成的图、表或后续的 Office 原生图表、插图对象接到 Word 主文档里，并保持编号、标题和说明位置稳定。
- 用户希望未来扩展多个版式档位或字体 profile，而不是把所有格式写死在单个脚本里。

## 模式路由

### 轻量模式

- 用户要的是 **先把单篇或少量文档快速转顺**，重点是把字体、字号、标题层级、行距、表题图题表注位置落对。
- 用户已经把主要版式要求说清楚，不要求 workspace 很重，不要求默认 review，不要求 Office 原生 chart 或复杂 OOXML patch。
- 用户更关心“先出一个干净、好看、能交付的 `.docx`”，而不是先建设一整套长期基础设施。

### 精细模式

- 用户要的是 **长期可维护的文档体系**，或者要处理多文档批量协作、可配置 style profile、Python figure、Office 原生 chart / illustration、模板继承、OOXML patch、自动 QA。
- 用户要求交付物不仅是 `.docx`，还包括更完整的 workspace、文档体系、验证证据和后续可扩展路线。

### 路由规则

- 如果用户明确说要走 **轻量模式** 或 **精细模式**，就直接听用户的，不要擅自改路由。
- 如果用户没有明确指定模式，优先看硬需求，不看说话口吻。
- 只要出现下列任一信号，默认走 **精细模式**：正式报告、较多图表或插图、Office 原生可编辑对象、preset/template、section/页眉页脚/多栏、长期维护、多文档批量协作、显式 QA/visual review、可复用 workspace。
- 只有当需求同时满足“单文档、篇幅较短、图表简单、没有模板/preset、没有 Office 原生对象、没有显式 review 证据要求、目标是快速交付”时，默认走 **轻量模式**。
- 如果任务同时带有轻量和精细两种硬信号，或者文档最终是否需要复用、验证、可编辑对象还不清楚，就应 **主动向用户确认**，不要凭语气猜。

## 轻量模式工作流

1. **先锁定文档任务和默认样式**
- 明确文档用途：合同、制度、报告、汇报附件、研究说明。
- 明确 source of truth：原始 `.docx` 还是维护中的 Markdown。
- 明确默认字体组合、标题梯度、表图规则，避免导出后才靠人工回修。

2. **再保持 Markdown 语义最小可用**
- 标题、正文、列表、表格、图片必须先保留为稳定语义，而不是在 Markdown 里硬凑视觉效果。
- 表题、表注、图题要有稳定语义约定。表题和图题优先直接写成 `表 3 情景分析摘要`、`图 2 成本结构变化` 这种最终可交付文本，不要强迫作者写 `表题：` 这种源文本噪声。

3. **再走最简单可用的构建路线**
- 普通文本型文档优先走 `docx -> markdown -> docx` 或 `markdown -> docx`。
- 轻量模式默认不引入 QA gate、不建设复杂 workspace、不要求 `meta.json` 或 `asset_manifest`、不预设 Office 原生 chart。

4. **再做显式版式映射**
- 正文默认 `小四 12pt`，中文 `宋体`，英文 `Times New Roman`，首行缩进 `2` 字符。
- 正文和标题默认 `1.5` 倍行距，段前段后统一按 `0.5` 行落地。
- 表格正文默认 `五号 10.5pt`，密表允许降到 `小五 9pt`，段前段后与首行/悬挂/左右缩进均为 `0`，单元格内容上下居中；表头水平居中、左侧索引列左对齐、右侧数值列右对齐。
- `cn_song_times` 默认使用“表题在表上方且加粗、图题在图下方、表注在表下方”的中文正式文档规则；如果 active `style_profile` 或 preset 显式覆盖 `figure_title` 位置，就必须让构建与 QA 一起跟随 `caption_policy` 落地。

5. **轻量模式默认不做 review**
- 默认交付重点是把 `final/*.docx` 本体快速、干净地落出来，不自动附带 visual review 或质量 gate。
- 只有用户明确要求自动 review、人工复核或任务已经明显升级成精细模式时，才追加检查步骤。

## 精细模式工作流

1. **先锁定文档任务和 style profile**
- 明确文档用途、source of truth、交付标准和后续复用边界。
- 明确 `style_profile`、`caption_policy`、资产模式和 future extension boundary。

2. **先保持 Markdown 的语义稳定**
- 标题、正文、列表、表格、图片必须先保留为稳定语义，而不是在 Markdown 里硬凑视觉效果。
- 表题、表注、图题、图注和来源说明要有稳定语义约定。表题和图题优先直接写成最终交付文本，并结合相对位置识别 role。
- 当文档包含多个图表或 Office 原生对象时，应显式维护 `asset_manifest`，不要把“这张图怎么生成、是否可编辑、题注放哪”散落在脚本常量里。

3. **再选择构建路线**
- 普通文本型文档优先走 `docx -> markdown -> docx` 或 `markdown -> docx`。
- 需要精确控制 Word 样式槽位、caption 位置、图注来源说明、分节、页眉页脚或原生对象时，再进入 OOXML patch 或 Office 原生对象路线。

4. **再做显式版式映射**
- 正文默认 `小四 12pt`，中文 `宋体`，英文 `Times New Roman`，首行缩进 `2` 字符。
- 正文和标题默认 `1.5` 倍行距，段前段后统一按 `0.5` 行落地。
- 表格正文默认 `五号 10.5pt`，密表允许降到 `小五 9pt`，段前段后与首行/悬挂/左右缩进均为 `0`，单元格内容上下居中；表头水平居中、左侧索引列左对齐、右侧数值列右对齐。
- `cn_song_times` 默认使用“表题在表上方且加粗、图题在图下方、表注在表下方”的中文正式文档规则；如果 active `style_profile` 或 preset 显式覆盖 `figure_title` 位置，就必须让构建与 QA 一起跟随 `caption_policy` 落地。

5. **再接 Python 图表或 Office 原生图表 / 插图**
- 图表和插图都是文档资产，不是版式例外。
- 需要继续编辑数据、KPI 卡片、流程框或简单示意图时，优先考虑 Office 原生 visual route，并在 `asset_manifest` 中标记为 `office_native_chart` 或 `office_native_illustration`。
- 需要高复杂度研究图时走 Python figure 路线，并在 `asset_manifest` 中标记为 `python_figure`。
- 所有资产都必须继承同一份 `style_profile` 与 `caption_policy`，不能各自发明题注位置和说明样式。

6. **强制做 QA**
- 至少检查字体槽位、中英文字体、标题层级、正文首行缩进、行距、段前段后、表图标题位置、图注/来源说明、表格字号、表题加粗、表格对齐、图片裁切和原生对象可编辑性。
- 字号 QA 同时检查 source/config 层 literal、DOCX 产物层 role/profile 漂移、profile 外临时档位、字号碎片化和半点网格。Word 字号底层按半点表达，因此整数与 `10.5pt` 合法，`9.6pt`、`11.3pt` 这类配置应提醒；能解析 active role 时优先直接收敛到 active `style_profile` 的默认 token，例如中文正文回 `cn_song_times.body=12pt`。
- 字号 observation 默认是 advisory；如果同一异常导致段落 `style_contract`、字体槽位、表格契约或 visual review gate 失败，对应 contract finding 仍会独立 hard block。Agent 应先修 hard block，再处理或记录字号 advisory。
- 提醒必须按问题类型聚合、统计 occurrence 数并只保留少量代表位置，不能把每个 run 展开成重复长列表。
- 表格缩进和单元格垂直对齐属于默认契约：QA 检测到偏离时输出 warning，Agent 默认修复；存在长文本单元格、外部模板或其他明确版式理由时，可以记录理由并保留例外。warning 不改变 `passed_all_checks`。
- `lint_doc_markdown.py` 和 `run_docx_qa.py` 会在原 JSON / Markdown 报告旁生成 `.agent_reminder.json` 与 `.agent_reminder.md`。Agent 必须先读 reminder 的 `decision`、`groups`、`suggested_fix`、`sample_locations` 和 `full_report_ref`，只有需要完整证据时再打开 full report。
- 没有视觉复核或结构核对的 `.docx` 不算完成。

## 资源路由

### 轻量模式

- 默认先读取 `references/lightweight_mode.md`。
- 这份文档已经包含默认字体组合、标题梯度、caption 规则和最小 workspace。
- 只有当轻量模式已经不能覆盖需求时，才升级到精细模式文档。

### 精细模式

**核心文档**
- 需要统一定义对象、版式规范和 references 分层时，读取 `references/principles.md`。
- 需要执行 `docx -> markdown -> docx` 的协作流程、Markdown 语义约定和 workspace 组织时，读取 `references/doc_workflow.md`。
- 需要确定默认字体组合、字号梯度、段前段后、表题图题表注规则时，读取 `references/typography_profiles.md`。
- 需要明确实现层的技术边界、OOXML 字体槽位和失败条件时，读取 `references/technical_support.md`。

**专项文档**
- 需要在 `python-docx`、Pandoc、OOXML patch 等构建路线之间做选择时，读取 `references/build_routes.md`。
- 需要接 Office 原生图表或插图时，读取 `references/office_chart_support.md`。
- 需要接 Python 绘图资产时，读取 `references/python_figure_support.md`。
- 需要执行交付前质量 gate 时，读取 `references/quality_gates.md`。
- 需要参考一个已落地的宿主工作区实践时，读取 `references/local_pipeline_case_study.md`。
- 需要套用咨询报告或品牌近似风格 preset 时，读取 `references/preset_style_guides.md`，并让 preset 和默认中文正式文档规则显式衔接。

## 质量标准

- `cn_song_times` 默认正文必须满足 `中文宋体 + 英文 Times New Roman + 小四 12pt + 首行缩进 2 字符 + 1.5 倍行距 + 段前段后 0.5 行`。
- 标题字号必须随层级单调递减，不能出现二级标题比一级标题更大。
- 字号默认服从 active `style_profile` 并使用 `0.5pt` 网格；非半点小数、局部覆盖和过多临时档位必须进入聚合 warning，模板或 preset 例外应先写入 profile。
- 字号 reminder 必须显示 active profile 的默认推荐值；例如中文 `cn_song_times.body` 推荐 `12pt`，英文 `teal_consulting_report.body` 推荐 `9pt`，英文 `red_private_equity_report.body` 推荐 `10pt`。中文任务中的英文单词仍使用中文 profile 的字号 token。
- 表格正文默认使用 `五号 10.5pt`，确有密度压力时才降到 `小五 9pt`；单元格段落默认无特殊缩进，内容默认上下居中，表头水平居中、左侧索引列左对齐、右侧数值列右对齐。
- `cn_song_times` 默认表题在表上方且加粗，图题在图下方，表注在表下方。其他 preset 或 style profile 可以显式覆盖 `figure_title` 的位置，但必须在 profile 和 QA 中写清楚。
- 轻量模式默认不附带 review 记录；精细模式默认必须带 `validation_bundle`，并且让 QA 跟随 active `style_profile` 与 `asset_manifest`（若存在）执行。
- 没有显式设置 `ascii/hAnsi/eastAsia/cs` 字体槽位的构建结果，不应被当作“格式已锁定”。
- 最终交付 DOCX 必须放在 workspace 根目录的 `final/` 下；`build/` 和 `temp/` 只放可重建中间物、候选稿和验证证据。

## 典型宿主命令

如果宿主工作区已经具备自己的 `doc_pipeline.py`，常见命令会是：

```bash
python scripts/doc_pipeline.py docx-to-md
python scripts/doc_pipeline.py md-to-docx
python scripts/doc_pipeline.py rebuild-all
```

如果宿主工作区还没有自己的实现，这个 skill 现在自带一套参考脚本：

```bash
python scripts/init_doc_workspace.py <workspace-dir> --mode refined --doc-slug <doc-slug>
python scripts/check_word_environment.py
python scripts/lint_doc_markdown.py --meta markdown/<doc-slug>/meta.json
python scripts/build_docx.py --meta markdown/<doc-slug>/meta.json
python scripts/export_docx_preview.py --meta markdown/<doc-slug>/meta.json
python scripts/run_docx_qa.py --meta markdown/<doc-slug>/meta.json
```

这套脚本的职责边界很明确：
- `init_doc_workspace.py` 负责初始化轻量或精细 workspace
- `check_word_environment.py` 负责检查 `python-docx`、LibreOffice、Poppler 和字体探测能力
- `lint_doc_markdown.py` 负责在 build 前检查标题层级、caption 语义、图片路径和 `asset_manifest`
- `build_docx.py` 负责按 active `style_profile` 生成 `.docx`
- `export_docx_preview.py` 负责导出 PDF 和逐页 PNG
- `run_docx_qa.py` 负责执行字体槽位、段落契约、表格对齐、section 栏数和 asset 路线 QA
- `scripts/agent_qc_reminders/` 是随本 skill 分发的本地提醒 runtime，负责生成 `.agent_reminder.json/.md`；脚本不得依赖仓库根目录存在同名共享包。

## 额外说明

- 这个 skill 当前把核心价值放在 **文档体系、版式规范和路线选择** 上，不假装某一个固定脚本已经覆盖所有 Word 特性。
- 如果宿主脚本没有显式支持字体 profile、caption 语义或 Office 原生图表，不应静默宣称“已经支持”，而应先暴露能力边界。
