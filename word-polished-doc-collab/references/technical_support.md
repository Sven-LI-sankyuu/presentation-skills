# Technical Support

**这份文档的定位。** 本文定义 `word-polished-doc-collab` 的技术支持体系，回答“Markdown、DOCX、OOXML、Python 资产和未来 Office 原生对象应如何落地”，并明确哪些能力可以自动化，哪些能力必须显式暴露边界。

## 技术分层

**抽取层负责把 Word 变成稳定语义。** 常见实现会使用 `python-docx`、`zipfile` 和 `OOXML XML` 读取段落、表格、图片和关系文件，并按真实顺序输出 Markdown。

**构建层负责把 Markdown 变成结构化 Word。** 常见实现会用 Markdown parser 生成中间 HTML 或 AST，再用 `python-docx` 写回段落、标题、列表、表格和图片。

**样式层负责把 role 映射成 Word 样式与 run 属性。** 这里必须显式处理字体槽位、字号、首行缩进、段前段后、行距、加粗、对齐、caption 位置和表格密度。

**补丁层负责处理 `python-docx` 难以精确表达的部分。** 如果需要分节、域、复杂编号、原生 chart、样式槽位细修或某些兼容性 patch，应进入 OOXML patch 层，而不是假装高层 API 已经做到了。

## 当前推荐库栈

**普通文本型流水线优先使用 Python。** 一个稳妥组合通常是：
- `python-docx`
- `markdown`
- `beautifulsoup4`
- `zipfile` / `xml.etree.ElementTree`

**这个组合适合你当前工作区里的主需求。** 它已经足以支持标题、正文、列表、表格、图片和统一样式回写，也适合做 `docx -> markdown -> docx` 的批量整理。

## 必须显式处理的实现细节

**字体要按脚本和 OOXML 双重确认。** 只设置 `run.font.name` 不够，因为中文往往仍会走 East Asia 槽位。构建器至少要同时设定拉丁和东亚字体。

**Caption 不能只靠字面前缀猜。** 如果构建器既不识别 `表 3 ...`、`图 2 ...`、`Exhibit 1 ...` 这类编号题注样式，也不结合它们与表格、图片的相对位置和 active `caption_policy`，就只能胡乱猜说明文字，结果不可维护。

**表格字体要独立设置。** Word 表格里的 run 很容易沿用正文默认值，因此表格正文和表头必须单独落 `10.5pt` 或 `9pt`。

**表格段落缩进要显式归零。** 构建器应对单元格内每个段落显式设置 `first_line_indent=0`、`left_indent=0` 和 `right_indent=0`；负的 `first_line_indent` 代表悬挂缩进，同样属于默认应归零的特殊缩进。Word 还可能用 `w:firstLineChars="200"` 表达首行缩进 `2` 字符，因此构建器与 QA 必须同时处理 point 属性和 `firstLineChars`、`hangingChars`、`leftChars`、`rightChars` 字符单位属性，并沿段落样式继承链解析有效值。

**表格单元格要显式上下居中。** 构建器应在 cell 级设置 `vertical_alignment=center`，QA 对缺省、靠上、靠下等偏离输出 warning。这个属性与 paragraph 级水平对齐互不替代。

**正文首行缩进要独立设置。** 中文正式文档正文默认应有 `2` 字符首行缩进，但标题、表题、图题、表注、列表和表格正文都不应机械继承这条规则。

**表格对齐要按列角色设置。** 表头、左侧索引列、普通文本列和数值列不应使用同一种对齐策略。构建器至少要能稳定落地“表头居中、索引左对齐、数值右对齐”。

**图片要做存在性检查。** Markdown 里引用的图片路径不存在时，必须直接失败。空白图片占位是错误交付。

**精细模式资产要显式登记。** 只要文档开始混用 Office 原生对象、Python figure、图注、来源说明或 preset caption 规则，就应引入 `asset_manifest`，不要继续靠隐式约定维持系统。

## 当前边界

**复杂 Word 特性不应假装已经稳定。** 脚注、尾注、修订记录、批注、浮动对象、复杂文本框、自动编号域、跨节页眉页脚，这些都不应被默认声明为“已支持”。

**当任务进入这些能力边界时，应切换路线。** 可以走 OOXML patch、保留原 Word 模板修改、或者明确要求人工介入，但不能静默丢失信息。

## 面向未来的扩展点

**Style profile 应配置化。** 当前很多宿主脚本把字体和字号写死在代码里。要把 skill 做成仓库级能力，推荐把 `style_profile`、标题梯度、caption 规则、首行缩进和表格对齐做成可读取配置。

**Caption 和 block role 应语义化。** 推荐在 Markdown parsing 后先得到 `block_role`，再决定 Word 样式，而不是边遍历边临时判断。编号题注样式、相对位置和 active `caption_policy` 应成为正式识别条件。

**文档级验证应脚本化。** 当前 `run_docx_qa.py` 已覆盖字体槽位、段落契约、表格字号与水平对齐、表格缩进、单元格垂直对齐、caption 顺序、section 和资产声明，并对字号及表格默认契约偏离输出聚合 advisory。图片裁切与复杂原生对象仍需结合 preview 和人工 visual review，不能只依赖“脚本没报错”。
