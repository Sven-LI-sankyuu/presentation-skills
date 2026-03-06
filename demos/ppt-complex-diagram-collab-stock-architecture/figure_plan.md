# 图集规划（复杂股票分析框架）

## 图集目标
- 让读者在 30 秒内理解：从数据到交易再到反馈的全链路闭环。
- 让研究员/PM/风控看到各自关注点与交互界面。
- 让工程实现者能直接映射到模块边界与接口职责。

## Fig00 总览分层图（本 demo 已实现）
- 读者问题：系统整体如何分层，谁依赖谁？
- 回答内容：
  - L1 数据域（Data Acquisition & Quality）
  - L2 研究域（Representation & Signal Factory）
  - L3 决策域（Portfolio Construction & Risk）
  - L4 执行域（Execution & Post-trade Attribution）
  - 横向治理与协作（Model Registry、Governance、Human-in-the-loop）

## Fig01 关键执行链路图（建议扩展）
- 读者问题：每天盘前到收盘的关键链路怎么走？
- 回答内容：盘前数据刷新 -> 信号计算 -> 约束求解 -> 交易执行 -> 归因回写。

## Fig02 用户视角流程图（建议扩展）
- 读者问题：研究员、PM、风控在一天中如何协同？
- 回答内容：
  - 研究员发布新特征和实验报告
  - PM 查看组合变动与容量占用
  - 风控审批豁免与触发降杠杆

## 边界与假设
- 这是展示型复杂架构，不追求生产级接口细节。
- 节点命名保持稳定，便于后续 Mermaid 与 PPT 一一映射。
- connector 一律连接业务节点，不连接 Lane 外框。
