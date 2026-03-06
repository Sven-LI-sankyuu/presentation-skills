---
name: ppt-complex-diagram-collab
description: Use when collaborating with humans to produce publication-grade complex diagrams in editable PPT, especially for system architecture, dataflow, and user-journey visuals that require shape-level connector validation and reproducible outputs.
---

# PPT Complex Diagram Collab

## 概览
把“业务讲清楚 + 图可复用 + 论文可交付”作为同一个任务完成。
优先交付图包（planning + mermaid + editable PPT + 校验结果），不要只交单张图。

## 工作流
按下面顺序执行，避免返工。

1. **先确认环境基线**
- 先读取 [references/tested_environment.md](references/tested_environment.md)。
- 至少确认 Python、`python-pptx`、Node/npm、mermaid-cli 可用。
- 不强制新建 conda 环境：如果现有环境能安装并稳定运行所需包，直接复用即可；需要隔离再新建临时环境。
- 如果当前环境和基线差异较大，先记录差异再开始出图，避免“图能生成但不可复现”。

2. **先锁定交付规格**
- 明确主图用途：论文主图、答辩图、工程文档图。
- 明确输出形态：`*.md`（含 mermaid）、`*.mmd`（可选）、`*.pptx`（可编辑）。
- 明确可编辑定义：
  - 如果使用 connector：拖动节点时连线仍然绑定，不是“视觉上像连着”；
  - 如果不使用 connector（分层架构图常见）：用箭头/卡片表达层级递进，此时连线校验期望 `connectors=0`。
- 先选视觉语法（分层架构图 vs 数据流/因果图），避免把两张图硬塞一张图。
  - 参考：[references/visual_style_and_edge_policy.md](references/visual_style_and_edge_policy.md)。

3. **拆分图集而不是硬塞一张图**
- 先给图清单：总览分层图 + 关键执行链路图 + 用户视角流程图。
- 给每张图编号（如 Fig00~Fig09）并定义“读者问题 -> 图回答什么”。
- 使用 [references/figure_planning_template.md](references/figure_planning_template.md) 组织范围和边界。

4. **先做可讨论版本（mermaid）**
- 在一个文档里集中维护图集与解释，保证评审快。
- 保持节点命名稳定，避免后续 PPT 版无法对齐。
- 用脚本批量渲染 SVG/PDF/PNG，确保论文与汇报都能复用。

5. **再做可编辑版本（PPT）**
- 用 `python-pptx` 直接画 shape（必要时才画 connector），不要仅插入 PNG。
- 分层架构图（Fig00）推荐默认用 **Layer Card + 递进箭头**，避免 hairball；数据流图（Fig01）再用 connector。
- 如果使用 connector：
  - 连接线必须使用 `begin_connect()`/`end_connect()` 粘连到具体 shape；
  - 优先连接“业务节点框”，不要连接 lane/cluster 外框；
  - 控制 edge budget（参考视觉/连线策略文档）。
- 如果不使用 connector：
  - 箭头应表达“层级递进/主方向”，不要用长 chevron 文案当装饰；
  - 仍然建议运行连线校验，确认 `connectors=0`。

6. **强制做连线校验**
- 运行 `scripts/check_pptx_connectors.py` 校验：
  - 每条 connector 同时存在 `stCxn` 和 `endCxn`；
  - 连接的 shape id 必须可解析到文本节点；
  - 不允许粘到被禁止前缀（如 `Lane `）节点。
- 可选：如果这张图预期必须存在 connector，用 `--min-connectors` 防止“意外生成了 0 条连线”。
- 用 [references/ppt_connector_debug.md](references/ppt_connector_debug.md) 做人工复核。

7. **迭代时只改关键差异**
- 用户反馈“线条拖动会散”时，先定位具体哪条边，不做大重画。
- 优先修连接点索引映射和目标 shape 绑定关系。
- 每次迭代后重新生成 PPT 并复跑校验脚本。

## 交付清单
一次完整交付至少包含：
- 图集说明文档（图编号、用途、约束）。
- mermaid 源和批量渲染脚本。
- 可编辑 `pptx` 生成脚本。
- 连线校验脚本输出（命令 + 结果）。
- 视觉方案与连线策略说明（建议作为附录或 `style_spec.md`），保证可复用与可复现。

## 快速命令
```bash
# 1) 生成可编辑 PPT（示例）
python <diagram_dir>/build_editable_pptx.py

# 2) 校验连线是否真绑定
python ppt-complex-diagram-collab/scripts/check_pptx_connectors.py \
  --pptx <diagram_dir>/pptx/<name>.pptx \
  --slide 10 \
  --forbid-prefix "Lane " \
  --min-connectors 1
```

## 资源使用规则
- 需要确认系统/工具环境时，读取 [references/tested_environment.md](references/tested_environment.md)。
- 需要规划图集范围时，读取 [references/figure_planning_template.md](references/figure_planning_template.md)。
- 需要诊断“拖动散线/连错对象”时，读取 [references/ppt_connector_debug.md](references/ppt_connector_debug.md)。
- 需要统一视觉方案/控制连线密度时，读取 [references/visual_style_and_edge_policy.md](references/visual_style_and_edge_policy.md)。
- 需要程序化验收时，运行 `scripts/check_pptx_connectors.py`。
