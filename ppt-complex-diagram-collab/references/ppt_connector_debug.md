# PPT 连线调试清单（可编辑图）

## 快速判定
1. 拖动节点后，线端点是否跟着节点移动。
2. 线是否绑定到正确节点，而不是绑定到 lane/cluster 外框。
3. 同一条线是否同时存在起点与终点连接（不是仅一端粘连）。

## 常见故障与修复
- 症状：拖动节点后线条断开漂移。
  - 排查：是否调用了 `begin_connect()` 与 `end_connect()`。
  - 修复：统一通过封装函数创建 glued connector。

- 症状：看起来连上了，但拖动后连错对象。
  - 排查：是否连接到了大框（Lane/Cluster）而非业务节点框。
  - 修复：保存并显式传递目标小框 shape 变量。

- 症状：部分方向连线异常（左右反了）。
  - 排查：连接点索引映射是否正确。
  - 建议映射：`top=0,left=1,bottom=2,right=3`。

## 回归检查
- 运行脚本检查：
```bash
python presentation-skills/ppt-complex-diagram-collab/scripts/check_pptx_connectors.py \
  --pptx <path/to/file.pptx> \
  --slide <N> \
  --forbid-prefix "Lane "
```
- 人工抽检：至少拖动主图中的 5 个核心节点（含跨泳道连线）。
