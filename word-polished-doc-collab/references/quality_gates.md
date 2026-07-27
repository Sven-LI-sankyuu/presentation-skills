# Quality Gates

**这份文档的定位。** 本文定义 `word-polished-doc-collab` 在最终交付前应经过的质量 gate，避免把“脚本没报错”误当成“文档已经合格”。

**这些 gate 是精细模式默认动作。** 轻量模式默认不跑这些 gate，只有用户明确要求自动 review 或任务已经升级到精细模式时才执行。

**这些 gate 必须跟随 active `workflow_mode`、`style_profile` 和 `asset_manifest`。** 不允许一边选择英文咨询或投资类 preset，一边还用默认中文正式文档的固定题注位置去误判。

**推荐把 gate 显式分成 build 前和 build 后两段。** `lint_doc_markdown.py` 负责 build 前的源语义 gate，`run_docx_qa.py` 负责 build 后的结构与版式 gate。不要跳过前者直接盯着 `.docx` 修结果。

## Gate 1: Source Integrity

**先检查源是否完整。** 至少确认：
- Markdown 文件存在且编码正常
- 轻量模式下，输入 Word 或 Markdown 与目标输出路径清楚
- 精细模式下 `meta.json` 可读
- 精细模式下如果存在复杂视觉资产，`asset_manifest.json` 可读
- 图片和生成图路径存在
- `style_profile` 已明确
- 表题、图题、表注没有缺位
- 需要图注或来源说明的资产没有缺位

## Gate 2: Style Contract

**再检查版式契约是否落地。** 至少确认：
- 正文、标题、表格和题注是否符合 active `style_profile`
- 字号是否落在 active `style_profile` 的 role 档位与 Word `0.5pt` 网格，是否存在 profile 外临时字号或过多碎片化档位
- `cn_song_times` 正文是否为 `小四 12pt + 首行缩进 2 字符 + 1.5 倍行距`
- 如果 active profile 要求正文不缩进，例如某些 preset，是否确实按 profile 覆盖
- 表格正文是否为 `10.5pt` 或 `9pt`
- 表题是否加粗
- 表格段前段后是否为 `0`
- 表格单元格段落的首行/悬挂/左右缩进是否为 `0`
- 表格单元格内容是否上下居中
- 表头是否居中、左侧索引列是否左对齐、右侧数值列是否右对齐
- 表题、图题、表注、图注和来源说明的位置与段距是否符合 active `caption_policy`

**字号提醒分 source 层和产物层。** `lint_doc_markdown.py` 会扫描 Markdown、meta、asset manifest 和 workspace scripts 中的显式字号 literal，用来捕捉 `Pt(9.6)`、`font_size: 11.3` 这类构建源问题；`run_docx_qa.py` 会扫描 DOCX 产物里的可见字号漂移。两层都进入统一 `.agent_reminder`，完整证据留在 JSON。

**字号提醒不默认阻断。** source/config literal、非半点配置、profile 外临时档位和字号碎片化进入 advisory；role/profile 的硬契约偏离仍由 `style_contract` 判定失败。也就是说，同一字号异常可以同时产生一个 `typography.font_size.*` advisory 和一个 `typography.paragraph.style_contract_drift` hard block，Agent 先修 hard block，再处理或记录字号 advisory。

**表格 warning 表示默认应修复的契约偏离。** 非零特殊缩进和未上下居中分别进入聚合 warning，且不改变 `passed_all_checks`。Agent 默认修复；长文本单元格、外部模板或其他明确业务理由可以作为例外，保留时必须在 handoff 或复核记录中说明理由。

## Gate 3: Font Slot Integrity

**再检查字体槽位。** 至少确认：
- 中文 run 的 East Asia 字体已设置
- 英文和数字的 `ascii/hAnsi` 字体已设置
- 需要无衬线英文时确实使用 `Arial`
- 需要楷体的段落没有被错误回退成宋体或默认系统字体

## Gate 4: Asset Integrity

**再检查资产路线是否落对。** 这一步在文档存在复杂视觉资产时执行，至少确认：
- `office_native_chart` 和 `office_native_illustration` 没有被错误扁平化成静态图片
- `python_figure` 资产能追溯到生成脚本或来源文件
- `asset_manifest` 中声明的 `caption_position`、`editable_required` 和实际导出结果一致

## Gate 5: Visual Review

**最后做人工视觉复核。** 至少确认：
- 标题层级清楚
- 页内分页自然
- 表格没有出界
- 图片没有被裁坏或拉伸
- 图题、表题、表注、图注和来源说明的相对位置正确

## 最低交付物

**精细模式的一次完整交付至少包含以下对象。**
- 可维护的 Markdown 源
- `final/*.docx` 最终交付文件
- 必要的图片、原生对象或生成图资产
- `style_profile` 说明，以及在存在复杂视觉资产时对应的 `asset_manifest`
- 一次复核记录或结论
