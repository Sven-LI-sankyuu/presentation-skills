# ppt-complex-diagram-collab 股票复杂架构 Demo

这是一个纯测试/展示用 demo，目标是演示 `ppt-complex-diagram-collab` 如何把“复杂业务架构”做成：

1. 可讨论版本（Mermaid）
2. 可演示版本（PPTX，用箭头表达层级递进，不使用 connector 连线）
3. 可程序化验收（connector 校验：本 demo 预期 connectors=0）

## 场景设定

主题：**Frame-based Equity Intelligence & Execution Framework（基于框架的股票智能分析与执行闭环）**。

强调“看起来复杂”且结构清晰，包含：
- 多源数据摄取与质量控制
- 表征学习与信号工厂
- 组合构建与风险治理
- 执行与交易后归因反馈
- 研究员/PM/风控三角色协同

## 目录结构

- `figure_plan.md`：图集规划（Fig00~Fig02）
- `assets/stock_architecture.mmd`：Mermaid 源
- `build_editable_pptx.py`：生成可编辑 PPT
- `pptx/stock_architecture_complex_demo.pptx`：输出 PPT
- `outputs/connector_report.json`：连线结构化校验输出

## 快速运行

```bash
cd demos/ppt-complex-diagram-collab-stock-architecture
python build_editable_pptx.py
python ../../ppt-complex-diagram-collab/scripts/check_pptx_connectors.py \
  --pptx pptx/stock_architecture_complex_demo.pptx \
  --slide 1 \
  --forbid-prefix "Lane " \
  --json-out outputs/connector_report.json
```

如果输出 `[OK] 所有 connector 校验通过`，说明该图满足“结构可程序化验收（本 demo 预期 connectors=0）”要求。
