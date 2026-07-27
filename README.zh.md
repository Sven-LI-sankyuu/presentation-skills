<div align="center">
  <table>
    <tr>
      <td style="vertical-align: middle;">
        <img src="assets/presentation-skills-logo.svg" alt="presentation-skills logo" width="120" />
      </td>
      <td align="left" style="padding-left: 24px;">
        <h1 style="margin: 0 0 8px;">presentation-skills</h1>
        <p style="margin: 0 0 12px;">
          <strong>面向真实办公交付的 Agent presentation skills</strong><br/>
          生成可编辑 PowerPoint、正式 Word 文档与可发布 demo 视频，<br>并把页面叙事、中文排版、原生表格 / 图表和质量检查放进同一条工作流。
        </p>
        <p style="margin: 0 0 12px;">
          <a href="https://github.com/Sven-LI-sankyuu/presentation-skills/releases/latest">
            <img src="https://img.shields.io/badge/release-skill%20zips-2ea44f?style=flat-square" alt="skill zip releases" />
          </a>
          <img src="https://img.shields.io/badge/skills-4%20packaged-2b579a?style=flat-square" alt="4 packaged skills" />
          <img src="https://img.shields.io/badge/output-editable%20Office-d2492a?style=flat-square" alt="editable Office output" />
          <img src="https://img.shields.io/badge/QC-table%20%2B%20typography-6f42c1?style=flat-square" alt="table and typography QC" />
          <img src="https://img.shields.io/badge/review-render%20preview-brightgreen?style=flat-square" alt="render preview review" />
        </p>
        <p style="margin: 0;">
          <a href="README.md">🇬🇧 English README</a>
        </p>
      </td>
    </tr>
  </table>
</div>

<table>
  <tr>
    <td width="25%">
      <strong>📋 贴近真实办公场景</strong><br/>
      覆盖研报、管理汇报、技术方案、答辩、产品演示、演讲分享和模板化商业材料，并区分阅读型 deck 与演讲型 deck。
    </td>
    <td width="25%">
      <strong>✏️ 保留 Office 可编辑性</strong><br/>
      优先使用 PowerPoint / Word 原生文本、形状、表格、图表和必要 connector，方便会后继续改文字、改数字和调版式。
    </td>
    <td width="25%">
      <strong>📄 公文级中文排版细节</strong><br/>
      支持宋体 / 黑体、Times New Roman、小四正文、1.5 倍行距、段前段后 0.5 行、五号表格和财务数值右对齐等办公规则。
    </td>
    <td width="25%">
      <strong>🔍 质量检查减少返工</strong><br/>
      检查文本溢出、对象遮挡、字号漂移、表格上下居中、表格特殊缩进、整页截图背景和预览图边界风险。
    </td>
  </tr>
</table>

<br/>

## 产品逻辑：用真实办公经验约束模型输出

模型能力的提升会让模型在直接使用代码工具操作ppt和word等载体的时候越来越得心应手, 但是PPT, word, 乃至网页视频录制, 更多的是一个产品问题. 模型的推理能力和代码能力的提高并不会让他们自然地掌握人类在办公中的PPT需求, 例如特定的字体和行距等排版信息, 和更细致的文本写作逻辑规范等. 本skill的主创有在大型券商和私募投资基金等机构的工作经验, 将这些经验和逻辑, 以规范和质检的形式固化, 以约束模型产生更符合实际工作需求的PPT, word和视频交付物. 这就是这个skill的核心价值.

| Skill | 适合场景 | Demo 亮点 |
| --- | --- | --- |
| `ppt-polished-deck-collab` | 可编辑研报、executive deck、策略汇报、技术说明、演讲分享、模板化商业材料 | 两套 Apple 财报分析 deck 使用相近主题，却呈现正式研报版与艺术化 editorial ink 原生 PPTX 版两种完全不同表达 |
| `word-polished-doc-collab` | 正式报告、董事会附件、研究附录、制度文档、咨询风格 Word 交付 | 中文轻量正式报告 + 英文精细咨询报告，包含 preview 和 QA bundle |
| `web-demo-video-synthesis` | 产品 walkthrough、网页 demo、带旁白解释视频、可发布短视频 | 网页、配音、字幕、录屏和最终 MP4 的端到端流水线 |
| `xhs-markdown-card-collab` | 从 Markdown 生成可发布的小红书图文卡片、研究/招聘帖子、结构化笔记型内容 | 导出的虚构 demo 成品，包含 PNG 卡片、预览 HTML、metadata JSON，以及在锁定字号合同下的主题变化示例 |

<br/>

## 30 秒开始

可以直接把仓库链接发给 Agent，并要求它安装 PPT skill：

```text
请打开 https://github.com/Sven-LI-sankyuu/presentation-skills/ ，安装其中的 ppt-polished-deck-collab skill。
```

下载最新 skill zip：[GitHub Releases](https://github.com/Sven-LI-sankyuu/presentation-skills/releases/latest)

如果下载的是总包，解压到 Codex skills 目录：

```bash
mkdir -p ~/.codex/skills
unzip presentation-skills-all-skills-*.zip -d ~/.codex/skills
```

安装后直接对 Agent 说：

```text
请使用 ppt-polished-deck-collab，帮我把这份材料做成一套正式、可编辑、需要导出预览并完成 QC 的 PPT。
```

也可以把 `ppt-polished-deck-collab` 换成 `word-polished-doc-collab`、`web-demo-video-synthesis` 或 `xhs-markdown-card-collab`。

<br/>

## PowerPoint Decks

`ppt-polished-deck-collab` 覆盖的是多种 deck 类型，不是一套固定模板：

| 场景 | 可以产出什么 | Demo / 图片 / 证据 |
| --- | --- | --- |
| 正式财报 / 研报型 deck | Office 原生图表、原生表格、来源注、免责声明、稳定研报版心 | [Apple FY2025 财报点评](demos/apple-financial-report-review/README.md) |
| 艺术化分析 / keynote 分享 | 大号衬线标题、强视觉节奏、native shape chart、无 HTML 截图的风格迁移 | [Apple editorial ink native test](demos/apple-editorial-ink-native/README.md) |
| 策略汇报 / executive deck | 管理层问题、对比矩阵、决策逻辑、结构图和叙事节奏 | [PPT skill 专页](docs/ppt-polished-deck-collab.md) |
| 技术说明 / 架构解释 | dataflow、系统图、可绑定 connector、结构校验报告 | [PPT skill 专页](docs/ppt-polished-deck-collab.md) |
| 模板驱动商业材料 | 模板审计、母版 / layout 取证、必要时 branded rebuild | [PPT skill 专页](docs/ppt-polished-deck-collab.md) |

PPT skill 专页：[docs/ppt-polished-deck-collab.md](docs/ppt-polished-deck-collab.md)

## PPT Gallery

| 同一 Apple 主题，艺术化分享表达 | 同一 Apple 主题，正式研报表达 |
| --- | --- |
| [![Apple editorial ink native test contact sheet](assets/apple-editorial-ink-native_contact-sheet.png)](demos/apple-editorial-ink-native/README.md) | [![Apple FY2025 财报点评 contact sheet](assets/apple-financial-report-review_contact-sheet.png)](demos/apple-financial-report-review/README.md) |
| guizang “电子杂志 × 电子墨水”风格的 native PPTX 迁移测试：大字、深浅节奏、ghost number、shape chart，不使用 HTML 截图。 | 正式中文财报点评：Office 原生图表、原生表格、研报版心、来源注、免责声明和完整验证证据链。 |

**艺术化单页示例**

[![Apple editorial ink iPhone 与 Services 页面](demos/apple-editorial-ink-native/build/rendered/ppt_preview/slide_004.png)](demos/apple-editorial-ink-native/README.md)

这个单页更适合在 README 直接放大展示：iPhone 作为收入中枢，Services 作为稳定第二曲线，产品结构、趋势证据和深色 editorial 页面节奏都集中在一页里。

| 可复跑数据链路页 | 财务证据页 |
| --- | --- |
| [![Apple editorial ink data pipeline 页面](demos/apple-editorial-ink-native/build/rendered/ppt_preview/slide_008.png)](demos/apple-editorial-ink-native/README.md) | [![Apple FY2025 收入与净利润页](assets/apple-financial-report-review_revenue-page.png)](demos/apple-financial-report-review/README.md) |
| 从 SEC API、10-K HTML、抽取脚本到 native PPTX 的可复跑数据链路，展示自动化材料如何保留证据路径。 | 单页财务证据示例，展示图表、图题、单位、来源和核心判断如何组合。 |

## 其他交付物 Demo

[![Word 精细咨询报告 demo 跨栏页](assets/word-refined-industrial-service-transformation_spread.png)](demos/word-refined-industrial-service-transformation/README.md)

[![Web Demo Video Synthesis preview](demos/web-demo-video-synthesis-financial-agent/assets/preview_en.png)](demos/web-demo-video-synthesis-financial-agent/README.md)

## Prompt 示例

![Apple 财报点评 deck 的 prompt 示例](assets/ppt-prompt-example.jpg)

这个 prompt 示例明确了 workspace 位置、数据来源、参考风格、免责声明和 `ppt-polished-deck-collab` 技能路线。Apple demo 展示的是从这类任务输入到可复跑研报工作区的完整产物，而不是一次性生成的单个 PPT 文件。

## 最近更新

- `2026-05-13` 🎨 新增 Apple editorial-ink native PPTX demo 和 PPT skill 专页。
- `2026-05-10` 📊 将 Apple FY2025 财报点评设为正式 PPT 主 demo。
- `2026-05-10` 增加 PPT 中文正式材料排版与财务表格默认规则。
- `2026-05-05` 将 XHS 虚构 demo 升级为已渲染 PNG bundle。
- `2026-05-04` 新增 `xhs-markdown-card-collab`，支持 Markdown 转图文卡片。
- `2026-04-30` 新增两个 Word demo 工作区，包含 preview 和 QA 证据。
- `2026-04-29` 新增 `word-polished-doc-collab`，支持正式 DOCX workflow。
- `2026-04-22` 🛡️ 新增 PPT 文件、页面结构和预览效果三层检查。
- `2026-04-22` 收紧 PPT 模板路线，从模板审计走到最终交付。

## 这个仓库提供什么

### `ppt-polished-deck-collab`

`ppt-polished-deck-collab` 用来生产可编辑、高质量、高度自动化的 PowerPoint deck，覆盖商业和学术两类用途。它既可以从零构建一整套 deck，也可以基于用户提供的模板工作，还可以继承用户已有 `pptx` 的母版和版式，并在保留可编辑性的前提下修改现有文件。

它适用于策略汇报、技术说明、研究汇报、论文答辩、产品演示、运营复盘、管理层 deck 等需要最终产物仍然表现为“真正 PowerPoint 文件”的场景。

### `word-polished-doc-collab`

`word-polished-doc-collab` 用来把 Markdown、DOCX 和 Python 生成的文档资产组织成正式、统一、可复跑的 Word 交付流程。它关注中英文字体组合、标题梯度、段前段后、行距、表题图题表注位置和交付证据，让 `.docx` 不只是导出成功，而是能经得住审阅。

它适用于合同、制度、说明文档、研究附录、业务报告、董事会或投委会附件等需要正式 Word 交付、且后续还要持续维护内容源的场景。

### `web-demo-video-synthesis`

`web-demo-video-synthesis` 用来高度自动化地生产带配音、带字幕、可直接发布的视频。它可以把文章、帖子、产品 walkthrough、网页 demo 和技术介绍转成适合 TikTok、小红书、Bilibili 等平台发布的视频内容。

它适用于技术介绍、商业 demo、产品解释、营销式演示和其他强调可复现、可迭代、产出速度快的视频生产场景。

### `xhs-markdown-card-collab`

`xhs-markdown-card-collab` 用来把 Markdown 或轻度结构化文本稳定地转成可发布的小红书图文卡片。它的重点是显式封面元数据、中文可读性、浏览器分页、视觉 QA，以及在保持已验证字号范围稳定的前提下做出不趋同的页面风格。

它适用于招聘/招生帖子、研究笔记、结构化观点卡片、产品说明和其他需要在手机端持续滑读的社交内容，而不是只要“导出几张 PNG”就算完成的场景。

## Skill 详情

### `ppt-polished-deck-collab`

`ppt-polished-deck-collab` 的原理是先把用户要讲的内容拆成页面顺序、每页结论和需要的证据，再用程序生成真正可编辑的 `.pptx`。它适合从研究材料、商业汇报、技术说明或模板稿件出发，做出可以继续手工编辑的 PowerPoint，而不是把页面做成一张张截图。

常用技术：
- 用 `python-pptx` 生成文本、形状、表格和可编辑 PowerPoint 页面
- 根据内容选择 PowerPoint 原生图表、`matplotlib` / `seaborn` / `pandas` 图表或图片素材
- 用 PowerPoint 或 LibreOffice 导出逐页预览
- 在需要流程图、架构图时检查连接线、层级关系和后续可编辑性

典型工作流：
- 先确认读者、用途、页数、模板和风格边界
- 再整理页面大纲、每页主结论和图表素材
- 生成可编辑 PPT，并按需要继承模板或改写已有 PPT
- 导出逐页预览，检查文字溢出、图表模糊、元素错位和页面风格不一致
- 最后交付 PPT、PDF 或预览图，以及必要的检查记录

展示样例：
- 艺术化 native PPTX 风格迁移 demo：`demos/apple-editorial-ink-native/`
- 当前研报型 demo：`demos/apple-financial-report-review/`

关键输出：
- `demos/apple-editorial-ink-native/final/apple_editorial_ink_native_test.pptx`
- `demos/apple-editorial-ink-native/build/rendered/contact_sheet.png`
- `demos/apple-financial-report-review/final/apple_fy2025_financial_report_review.pptx`
- `demos/apple-financial-report-review/final/apple_fy2025_financial_report_review.pdf`
- `demos/apple-financial-report-review/build/rendered/contact_sheet.png`

[![Apple FY2025 收入与净利润页](assets/apple-financial-report-review_revenue-page.png)](demos/apple-financial-report-review/README.md)

### `word-polished-doc-collab`

`word-polished-doc-collab` 的原理是先把 Markdown 或旧 Word 稿整理成稳定的标题、正文、表格和图片结构，再按统一字体、字号、行距和题注规则生成正式 `.docx`。它关注的是让 Word 文件能经得住审阅和后续维护，而不是只把内容临时导出成一个文件。

常用技术：
- 用 `python-docx` 生成和修改 Word 文档
- 必要时直接处理 OOXML，精确控制中文、英文和复杂脚本字体槽位
- 用 Word 或 LibreOffice 导出 PDF 与页面预览
- 用 `matplotlib` / `pandas` 等工具生成需要插入文档的图表

典型工作流：
- 先确认文档用途、来源稿件和目标版式
- 再把正文、标题、列表、表格、图片和题注整理成清楚结构
- 生成 `.docx`，并按中文正式文档或英文咨询报告等场景设置字体和段落
- 导出预览，检查字体、标题层级、行距、表图位置、页眉页脚和整体版式
- 对正式报告保留预览和检查记录，方便继续修改和复核

主展示 demo：
- `demos/word-lightweight-industrial-operations-brief/`
- `demos/word-refined-industrial-service-transformation/`

关键输出：
- `demos/word-lightweight-industrial-operations-brief/out/industrial_operations_brief.docx`
- `demos/word-lightweight-industrial-operations-brief/out/preview/industrial_operations_brief.pdf`
- `demos/word-refined-industrial-service-transformation/build/docx/industrial_service_transformation.docx`
- `demos/word-refined-industrial-service-transformation/temp/qa/qa_report.md`

### `web-demo-video-synthesis`

`web-demo-video-synthesis` 的原理是先把讲解词拆成短段，生成分段配音，再用一张时间表控制网页录屏、字幕和音视频合成。它保留配音、字幕、录屏和最终 MP4 的中间产物，所以改文案、改字幕或重录画面时可以局部重跑。

常用技术：
- 用 TTS API 或 macOS `say` 生成分段音频
- 用 Playwright 控制浏览器录屏
- 用 `ffmpeg` 合成视频、音频和字幕
- 用字幕文件和分辨率参数控制横屏、竖屏和平台安全区

典型工作流：
- 准备讲解词和网页 demo
- 生成分段配音并确认每段时长
- 按时间表录制网页画面
- 生成字幕
- 混合音频、画面和字幕，导出 MP4
- 检查音画同步、字幕位置、画面清晰度和关键内容是否被裁切

主展示 demo：
- `demos/web-demo-video-synthesis-financial-agent/`

公开视频：
- Bilibili: https://www.bilibili.com/video/BV1j6NwzaEDZ/

### `xhs-markdown-card-collab`

`xhs-markdown-card-collab` 的原理是先把 Markdown 内容整理成适合手机滑读的标题、列表和重点句，再用浏览器真实排版生成一张张竖版图片。它适合把研究笔记、招聘信息、产品说明和结构化观点做成可发布的小红书图文，而不是普通网页截图。

常用技术：
- 用 Markdown 和 YAML front matter 表达正文、封面标题、机构名、标签和高亮信息
- 用 HTML / CSS 做真实浏览器排版
- 用 Playwright 或类似浏览器自动化工具导出 PNG
- 用主题色、版心、装饰元素和信息组织做风格变化

典型工作流：
- 先整理正文结构，保留原文语义，只补必要标题、列表和重点标记
- 再明确封面信息和页面尺寸，默认面向手机纵向阅读
- 生成逐页 PNG 和预览页面
- 检查封面信息量、分页、空白、长文字换行、标题孤立和手机端可读性

## 仓库结构

- `ppt-polished-deck-collab/`：当前主线 polished deck skill
- `word-polished-doc-collab/`：当前主线 Word 文档协作 skill
- `web-demo-video-synthesis/`：当前主线 web demo 视频合成 skill
- `xhs-markdown-card-collab/`：当前主线小红书 Markdown 图文卡片 skill
- `demos/`：正式注册的 demo 工作空间
- `old/`：归档技能和历史 demo
- `assets/`：根 README 使用的预览图资产

## Demos

- 正式 polished deck demo：`demos/apple-editorial-ink-native/`
- 正式 polished deck demo：`demos/apple-financial-report-review/`
- 正式 Word 轻量 demo：`demos/word-lightweight-industrial-operations-brief/`
- 正式 Word 精细 demo：`demos/word-refined-industrial-service-transformation/`
- 正式 web demo synthesis demo：`demos/web-demo-video-synthesis-financial-agent/`
- 正式 XHS 招募型 demo：`demos/xhs-fictional-north-quay-lab-recruiting/`
- 正式 XHS 研究摘要型 demo：`demos/xhs-fictional-grid-storage-research-note/`
- 正式 XHS 产品说明型 demo：`demos/xhs-fictional-orbitops-product-explainer/`
- 正式 XHS 周报快评型 demo：`demos/xhs-fictional-ridership-weekly-brief/`
- 归档复杂图 demo：`old/demos/ppt-complex-diagram-collab-stock-architecture/`
- 归档 polished deck demo：`old/demos/ppt-polished-deck-collab-ai-market-intelligence/`

## XHS Demo 组

`xhs-markdown-card-collab` 现在在 `demos/` 下补了四组完全虚构但**已经导出成品**的样例，用来解释这个 skill 的 workflow 和风格变化方向，不依赖任何真实招生、研究或产品文案：

- `demos/xhs-fictional-north-quay-lab-recruiting/`：机构招募 / 招生型，正式成品主题为 `lumen`
- `demos/xhs-fictional-grid-storage-research-note/`：研究摘要 / 框架笔记型，正式成品主题为 `ink`
- `demos/xhs-fictional-orbitops-product-explainer/`：产品说明 / 能力解释型，正式成品主题为 `clay`
- `demos/xhs-fictional-ridership-weekly-brief/`：周报快评 / 数据摘要型，正式成品主题为 `ink`
