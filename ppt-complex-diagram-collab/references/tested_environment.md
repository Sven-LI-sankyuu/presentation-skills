# 已验证环境（System / Tooling Baseline）

## 1. 系统环境（本次验证）
- OS: macOS 15.4.1 (`sw_vers`)
- Kernel/Arch: Darwin 24.4.0, `arm64` (`uname -a`)

## 2. Python 环境
- Conda: `24.9.2`
- Python: `3.12.2`
- Python path: `/opt/anaconda3/envs/prts/bin/python`
- `python-pptx`: `1.0.2`

## 3. 前端/渲染工具环境
- Node.js: `v23.11.0`
- npm: `10.9.2`
- Mermaid CLI (`@mermaid-js/mermaid-cli`): `11.12.0`

## 4. 环境准备命令（推荐）
优先复用已有环境。只有在需要隔离依赖时，才新建临时 conda 环境。

```bash
# 可选：新建并激活临时环境（示例名：acp-diagram-tmp）
conda create -n acp-diagram-tmp python=3.12 -y
conda activate acp-diagram-tmp

# 必需 Python 包
pip install python-pptx

# 可选：用于 mermaid 渲染（不使用可跳过）
npm install -g @mermaid-js/mermaid-cli
```

## 5. 本次通过的验证命令
```bash
# 技能结构校验
python /Users/svenli/.codex/skills/.system/skill-creator/scripts/quick_validate.py \
  /Users/svenli/FilesOnNut/0ProjectsOnNut/ForProfYuan/FrameBasedInvestment/presentation-skills/ppt-complex-diagram-collab

# Fig09 连线校验（示例）
python /Users/svenli/FilesOnNut/0ProjectsOnNut/ForProfYuan/FrameBasedInvestment/presentation-skills/ppt-complex-diagram-collab/scripts/check_pptx_connectors.py \
  --pptx /Users/svenli/FilesOnNut/0ProjectsOnNut/ForProfYuan/FrameBasedInvestment/AutoCausePanel/docs/presentation/system_architecture_v0.2/pptx/AutoCausePanel_system_architecture_figures_editable_v0.2.pptx \
  --slide 10 \
  --json-out /Users/svenli/FilesOnNut/0ProjectsOnNut/ForProfYuan/FrameBasedInvestment/temp/check_pptx_connectors_fig09.json
```

## 6. 维护规则
- 每次在新机器或新环境跑通后，更新本文件版本信息与验证命令。
- 如果只是小版本漂移（例如 Node minor），可追加“兼容性观察”；
  如果主版本变化（例如 Python 3.12 -> 3.13），必须重新跑连线校验并记录结果。
