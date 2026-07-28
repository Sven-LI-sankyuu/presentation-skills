# Build Routes

**这份文档的定位。** 本文统一说明环境依赖、可用构建路线、预览导出 backend、diagram 路线和它们的选择标准。它是 `references/modules/technical_support.md` 之下的细化实现文档，替代原来分散的 requirements 与 technical routes 文档。

## 什么时候先读它

**当你已经知道这套 deck 要怎么组织，但还没决定用哪条实现路线时，先读这份文档。** 它回答的是“当前环境下最合适的技术路径是什么”。

## 总原则

**先过 workflow gate，再选择或执行 build route。** 新 deck 与重大重构在资产生产或 PPT 组装前运行 `python scripts/validate_workflow_gate.py --workspace-dir <workspace> --target build --require-workflow`。该命令失败时，不得以切换 backend、直接写脚本或生成占位 PPT 绕过大纲批准。

**路线是可选型的，不是写死的。** 新 skill 不应把某一条技术路线当成唯一正解，而应在环境、模板约束、可编辑性要求和后续维护成本之间做选择。

**PowerPoint 交互技术路线优先继承旧 skill。** 现有 `python-pptx`、真绑定 connector、解析 `pptx` XML 校验、PowerPoint -> PDF -> PNG 这些成熟经验应直接复用。

**其余部分按 deck-first 重设计。** workspace、planning、asset taxonomy 和验证闭环不应被旧复杂图思路绑住。

## 核心依赖

**`python-pptx` 是硬依赖。** 只要交付目标是可编辑 `pptx`，这层能力就必须存在。

**预览导出至少需要一条 PDF / PNG 路线。** 可选组合包括：
- `PowerPoint -> PDF -> pdftoppm`
- `PowerPoint -> PDF -> PyMuPDF`
- `LibreOffice -> PDF -> pdftoppm`
- `LibreOffice -> PDF -> PyMuPDF`

**Mermaid 不是硬依赖。** 只有 diagram 页需要快速草图时，它才是有价值的可选工具。

**GPT Image API 是可选资产 backend。** 它只服务 `image-generation` asset slot，依赖 `openai` SDK 和 `OPENAI_API_KEY` / `OPENAINEXT_API_KEY`。如果没有 API 权限，仍可走 `manual-web`，但状态必须停在 `pending_user_generation` 或 `blocked`，不能伪造已生成图片。

## 路线矩阵

| 路线 | 适合场景 | 关键依赖 | 验证重点 |
| --- | --- | --- | --- |
| 空白页直生 editable deck | 新建高质量 deck | `python-pptx` | 对象可编辑、预览稳定 |
| 模板改写 / `master-first` | 强模板约束且母版结构清晰 | `python-pptx` + 模板文件 | 模板元素不漂移 |
| 品牌重建 | 模板视觉要保留，但结构太脆 | `python-pptx` + 品牌资产 | 标题区与装饰层分离 |
| Diagram connector | 流程图、架构图、依赖图需持续维护 | `python-pptx` | connector 真绑定 |
| Diagram visual | 只需表达结构，不靠拖动维护 | `python-pptx` | 显式 `connectors=0` 或纯预览验证 |
| Office chart native | 趋势、比较、构成图会后要继续改数 | `python-pptx chart` API | 图表可编辑、预览稳定 |
| Python figure image | 热力图、排序图、研究图表达能力优先 | `matplotlib` / `seaborn` / `pandas` | 300 DPI、比例稳定、预览清晰 |
| Image generation API | 强风格 hero、场景图、截图再设计 | `openai` SDK + API key | prompt、参数、输出文件、图片内部事实复核 |
| PowerPoint 预览导出 | 本机高保真 review | PowerPoint + PDF 渲染工具 | 页数一致、PNG 落盘 |
| LibreOffice 预览导出 | Linux / CI / 无 Office 环境 | LibreOffice + PDF 渲染工具 | 页数一致、重点页人工复核 |

## 如何选生成路线

**先做模板取证，再谈路线。** 只要用户给了参考 `pptx`，就先看预览页族、layout / master 结构、共享元素归属、真实文字和字号层级，再决定是继承还是重建。

**默认优先空白页直生。** 当任务是新建 deck，且没有强模板要求时，空白页直生最稳。

**无模板但有风格范式时先锁 profile 再直生。** 如果用户要求正式研报、学术答辩、产品发布会或其他明确文体，但没有给可继承的 `pptx`，不要临时凭感觉画页面。应先在 `brief.md` 固化 `typography_profile`、`domain_profile`、可借鉴边界、禁止品牌元素和免责声明，再走空白页直生或品牌重建。

**有强模板约束时优先 `master-first / layout-first`。** 如果必须保留既有母版、页眉页脚、logo、装饰角或固定感谢页，默认应保留模板的 master 和 layout，只替换页面内容。

**模板太脆时再切品牌重建。** 当模板结构复杂到难以稳定修改、layout 页族不清晰或继承关系不可控，但品牌视觉还想保留时，可以抽出背景、颜色与标识，在空白页上重建。

**品牌重建要明确告知边界。** 这条路线的产物是“同家族重建”，不是对原模板结构的直接继承。不要把重建结果伪装成模板改写。

**不要误判 `Blank` layout。** 在 PowerPoint 里，`Blank` 往往只是没有正文占位框，不等于没有母版元素。logo、页码、页脚和装饰角仍可能自动继承。

## 如何选 diagram 路线

**后续要拖动维护就走 connector。** 这类页必须使用真绑定 connector，并执行结构校验。

**只做解释性结构图就走 visual。** 对 management page、board memo 或 research note 里的轻结构图，纯视觉箭头通常更合理。

**Mermaid 是草稿层，不是主交付。** 它适合 diagram 页讨论，但不应要求所有页面都有 Mermaid 源。

## 如何选 chart 路线

**会后继续改数就走 Office native chart。** 经营页、周报、项目评审页里的趋势和比较图，优先保留为可编辑 chart。

**表达能力优先就走 Python figure。** 热力图、密集排序图、研究型证据图和复杂时间条图，应优先生成高 DPI 图片后插入 PPT。

**不要把 editable 当成唯一目标。** 当原生 chart 会明显损伤表达质量时，Python figure 是更合理的路线。

## 如何选 image-generation 路线

**先判断图片是不是事实证据。** 如果图片需要承载真实财务数字、实验结论、真实 UI 文本或可追责图表，应改用 Office chart、Python figure、原生表格或真实截图。`image-generation` 只处理氛围、主视觉、截图再设计和概念视觉。

**有 API 权限时优先 `gpt-image-api`。** 使用 `scripts/generate_image_asset.py` 生成单个 slot 的图片和 metadata；配置从 `OPENAI_API_KEY` / `OPENAI_BASE_URL` 或 `OPENAINEXT_API_KEY` / `OPENAINEXT_API_BASE` 读取。

**没有 API 权限时走 `manual-web`。** agent 只写 prompt 文档和 slot 记录，等待用户把图片放回 workspace。此时状态应为 `pending_user_generation`，不能把未生成图片标记成 `generated`。

**生成后仍需 preview 复核。** API 返回成功只说明图片文件存在，不说明它适合 PPT 页面。插入 PPT 后仍要检查安全区、裁切、对比度、图内文字、页面 chrome 和 deck profile 一致性。

## 如何选预览 backend

**本机有 PowerPoint 时优先 PowerPoint。** 这是更接近最终显示效果的高保真路线。

**无 PowerPoint 时优先 LibreOffice。** 它更适合服务器、CI 和无 GUI Office 环境。

**PDF 到 PNG 优先 `pdftoppm`。** 如果环境没有 `pdftoppm`，再回退到 `PyMuPDF`。

**页数一致是硬约束。** 不论走哪条 backend，导出的图片页数都必须和 `pptx` slide 数一致，否则应正确失败。

## 环境检查

**先跑环境检查，再选路线。** 默认使用：

```bash
python scripts/check_environment.py
```

环境检查会报告 `image_generation_api` 是否具备最低条件。这个检查只看 `openai` SDK 与环境变量或 `.env` 中是否存在必要 key，不做联网探测，也不输出密钥。

**如果明确要求某个 preview backend，可强制检查。**

```bash
python scripts/check_environment.py --require-backend powerpoint
python scripts/check_environment.py --require-backend libreoffice
```

## macOS 权限注意

**PowerPoint backend 在 macOS 上可能需要人工点击确认。** 第一次通过 `osascript` 或 Python 调用 PowerPoint 导出预览时，系统可能弹出权限确认框，要求当前终端或宿主应用获准控制 `Microsoft PowerPoint`。

**这不是脚本 bug，而是系统权限模型。** 如果用户没有点击允许，后续脚本即使路径和参数都正确，也可能因为 Automation 权限不足而失败。

**排查顺序如下。**
- 先看运行时是否弹出过系统权限对话框，并确认是否被人工拒绝过。
- 再检查 `System Settings -> Privacy & Security -> Automation`，确认当前终端、Python 宿主或当前 agent 所在宿主应用被允许控制 `Microsoft PowerPoint`。
- 如果脚本在不同宿主里运行过，例如 Terminal、iTerm、IDE 或其他 agent App，要分别检查这些宿主的权限状态。

**常见症状。** PowerPoint 预览导出在环境检查通过的前提下仍报 AppleScript 或 automation 相关错误，这时应优先怀疑权限而不是内容本身。
