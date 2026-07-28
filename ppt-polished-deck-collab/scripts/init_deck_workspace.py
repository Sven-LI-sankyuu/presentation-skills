#!/usr/bin/env python3
"""初始化 `ppt-polished-deck-collab` 标准 deck workspace。

定位与作用
----------
这个脚本只负责创建稳定目录结构，并写入 `brief.md` 与 `deck_narrative.md`
两份主文档模板。PPT 生成、素材下载和页面内容判断由后续 workflow 完成。

大致流程
----------
1. 创建 data、assets、build、validation 和 final 目录；
2. 创建图片 prompt / generated、预览、质量 gate 等常用子目录；
3. 写入带 workflow gate 与完整 `theme_tokens` 的 `brief.md` 与 `deck_narrative.md` 模板；
4. 默认不覆盖已有文件，除非显式传入 `--force`。
"""

from __future__ import annotations

import argparse
import textwrap
from pathlib import Path


WORKSPACE_DIRS = (
    "data",
    "assets/diagrams",
    "assets/charts",
    "assets/icons",
    "assets/images/prompts",
    "assets/images/generated",
    "assets/images/raw",
    "assets/tables",
    "build/generated",
    "build/pptx",
    "build/probes",
    "build/rendered/ppt_preview",
    "build/rendered/style_preview",
    "validation/package_preflight",
    "validation/structure_precheck",
    "validation/render_review",
    "validation/visual",
    "validation/workflow",
    "final",
)


def parse_args() -> argparse.Namespace:
    """解析命令行参数。"""
    parser = argparse.ArgumentParser(description="初始化 polished deck workspace")
    parser.add_argument("--workspace-dir", required=True, type=Path, help="要创建或补齐的 workspace 目录")
    parser.add_argument("--title", default="Untitled Deck", help="deck 标题")
    parser.add_argument("--audience", default="", help="目标读者，可后续在 brief.md 中细化")
    parser.add_argument("--scenario", default="", help="主使用场景，可后续在 brief.md 中细化")
    parser.add_argument("--objective", default="", help="目标动作或理解目标，可后续在 brief.md 中细化")
    parser.add_argument("--force", action="store_true", help="覆盖已有 brief.md 和 deck_narrative.md")
    return parser.parse_args()


def brief_template(title: str, audience: str, scenario: str, objective: str) -> str:
    """生成 `brief.md` 模板内容。"""
    return textwrap.dedent(
        f"""\
        # {title}

        ## 任务定义
        - 目标读者：{audience}
        - 主使用场景：{scenario}
        - 目标动作：{objective}
        - 是否需要无人讲解也能读懂：
        - 参考模板文件：
        - 模板 / 品牌约束：
        - 交付物要求：最终可编辑 PPTX 放入 `final/`，并提供逐页预览图、验证记录。
        - 验证要求：package preflight、structure precheck、preview export、render review、visual review。

        ## Deck Contract
        - source_context：no_template
        - delivery_context：hybrid_review_deck
        - communication_profile：business_report
        - visual_profile：corporate_clear
        - density_profile：balanced_brief
        - editability_profile：fully_editable
        - typography / table policy：见 `deck_narrative.md` frontmatter 的 `theme_tokens`。

        ## Five-Stage Workflow Status
        - 当前阶段：提问
        - 流程状态：questioning
        - 大纲版本：
        - 大纲反馈：
        - 大纲批准记录：
        - 初稿评价摘要：
        - 修正记录与重新验证证据：

        ## Grill-Me Intake Summary
        - 当前提问阶段：scope
        - 已确认事项：
        - Agent 推导及依据：
        - 采用的推荐默认：
        - 高影响选择及下游变化：
        - NON-FINAL STYLE PREVIEW 文件与反馈：
        - 未决项 / 阻塞项：

        ## 模板取证
        - 页面系统判断：
        - 关键母版 / layout 元素：
        - 字号系统：
        - 计划采用的构建路线：
        - 最小 PoC 结论：

        ## 风格与边界
        - 风格参考：
        - typography_profile：zh_formal
        - domain_profile：
        - visual_theme_preset：
        - 允许使用的素材：
        - 禁止使用的品牌元素：
        - 免责声明 / 风险边界：
        - 不允许发生的错误：

        ## Production Outline
        - 大纲版本：
        - 当前状态：outline_ready / awaiting_outline_feedback / outline_approved
        - 用户反馈与对应修订：
        - 明确批准记录：
        - 全局基调：
        - 章节结构：
        - 每页角色和读者问题：
        - 页面可见文案方向：
        - 资产 / 配图 / 图表需求：
        - layout 与节奏安排：

        ## Anti-AI-Slop Prompt Intake
        - 先读 prompt，再开始设计或写代码：
        - 卡片使用理由：
        - 背景实现方式：
        - 圆角 / 色条 / 阴影 / 渐变使用理由：
        - 矩形、节点、panel、卡片内部文字是否直接写入对应 shape：
        """
    )


def narrative_template(title: str, audience: str, scenario: str, objective: str) -> str:
    """生成 `deck_narrative.md` 模板内容。"""
    return textwrap.dedent(
        f"""\
        ---
        deck:
          title: "{title}"
          audience: "{audience}"
          scenario: "{scenario}"
          objective: "{objective}"
          source_context: "no_template"
          delivery_context: "hybrid_review_deck"
          communication_profile: "business_report"
          visual_profile: "corporate_clear"
          density_profile: "balanced_brief"
          editability_profile: "fully_editable"
          template_file: null
          personalization:
            speaker_or_brand_voice: null
            desired_impression: null
            must_emphasize: []
            must_avoid: []
            visual_likes: []
            visual_dislikes: []
          theme_tokens:
            typography_profile: "zh_formal"
            domain_profile: null
            visual_theme_preset: null
            page_width_in: 13.333
            page_height_in: 7.5
            hero_title_font_pt: 40
            section_title_font_pt: 30
            page_title_font_pt: 24
            subtitle_font_pt: 16
            minor_title_font_pt: 14
            body_font_pt: 12
            label_font_pt: 10.5
            caption_font_pt: 9
            title_line_spacing_multiple: 1.0
            body_line_spacing_multiple: 1.5
            title_paragraph_space_lines: 0.5
            body_first_line_indent_chars: 2
            body_paragraph_space_lines: 0.5
            latin_font_name: "Times New Roman"
            east_asia_font_name: "宋体"
            table_font_pt: 10.5
            table_line_spacing_multiple: 1.0
            table_paragraph_space_lines: 0
            table_first_line_indent_chars: 0
            table_vertical_anchor: "middle"
            table_header_alignment: "center"
            table_index_alignment: "left"
            table_text_alignment: "left"
            table_numeric_alignment: "right"
            left_margin_in: 0.78
            right_margin_in: 12.55
        workflow:
          version: 1
          state: "questioning"
          outline_version: null
          approval:
            status: "pending"
            outline_version: null
            evidence: null
            approved_at: null
        ---

        # {title}

        ## Global Narrative
        - 这套 deck 的主判断：
        - 这套 deck 的论证主线：
        - 这套 deck 的主题词和禁区：

        ## Production Outline
        - 大纲版本：
        - 当前状态：outline_ready / awaiting_outline_feedback / outline_approved
        - 用户反馈与对应修订：
        - 明确批准记录：
        - 全局基调：
        - 章节结构：
        - 每页角色和读者问题：
        - 页面可见文案方向：
        - 资产 / 配图 / 图表需求：
        - layout 与节奏安排：
        - anti-AI-slop 约束：

        ### S01 | <slide title>
        ```yaml slide_spec
        title: "<slide title>"
        reader_question: "<what this page should answer>"
        page_task: "persuade"
        reading_mode: "decision"
        archetype: "decision-logic"
        asset_mode: "text-layout-native"
        validation_mode: "preview_only"
        key_message: "<single core message>"
        layout_recipe: "business-summary-grid"
        rhythm_role: "opener"
        required_assets: []
        asset_slots: []
        ```

        **Page Role.** 这页在整套 deck 中承担的结构职责。

        **On-slide Copy.** 最终 PPT 页面上可以直接出现的标题、结论句、正文 bullet、图注和来源提示。

        **Evidence / Asset Plan.** 这页需要的证据、数据、图片、图表、diagram、表格或 icon。

        **Layout Notes.** 版式、密度、节奏角色、字体层级和可编辑对象策略。

        **Anti-slop Notes.** 说明这页为何需要或不需要卡片、背景、圆角、强调条、阴影、渐变和独立文本框。矩形、节点、panel 或卡片内部文字应直接写入该 shape；只有独立标题、注释、页脚或自由文本才使用单独文本框。

        **Speaker / Collaboration Notes.** 给讲者、合作者或 agent 的解释、取舍理由和口头过渡语，不直接进入页面可见文字。
        """
    )


def write_text(path: Path, content: str, *, force: bool) -> str:
    """写入文本文件，并返回写入状态。"""
    if path.exists() and not force:
        return "kept"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content.rstrip() + "\n", encoding="utf-8")
    return "written"


def main() -> int:
    """执行 workspace 初始化。"""
    args = parse_args()
    workspace_dir = args.workspace_dir.resolve()
    workspace_dir.mkdir(parents=True, exist_ok=True)

    for dirname in WORKSPACE_DIRS:
        (workspace_dir / dirname).mkdir(parents=True, exist_ok=True)

    brief_status = write_text(
        workspace_dir / "brief.md",
        brief_template(args.title, args.audience, args.scenario, args.objective),
        force=args.force,
    )
    narrative_status = write_text(
        workspace_dir / "deck_narrative.md",
        narrative_template(args.title, args.audience, args.scenario, args.objective),
        force=args.force,
    )

    print(f"[OK] workspace={workspace_dir}")
    print(f"[INFO] brief.md={brief_status}")
    print(f"[INFO] deck_narrative.md={narrative_status}")
    print("[NEXT] 按 questioning -> outline -> feedback -> execution -> evaluation_and_revision 推进；大纲未明确批准前不得完整 build")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
