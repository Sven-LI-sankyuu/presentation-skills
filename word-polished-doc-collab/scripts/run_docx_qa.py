#!/usr/bin/env python3
"""执行 `word-polished-doc-collab` 的 DOCX 自动 QA。

定位与作用
----------
这个脚本把字体槽位、字号与表格缩进提醒、段落契约、表格对齐、caption 顺序、section 栏数和
`asset_manifest` 一致性收敛成一个可追溯的 QA bundle。它不替代人工视觉判断，
但能把那些本应脚本检查的问题尽量在交付前锁死。
"""

from __future__ import annotations

import argparse
from pathlib import Path

from word_skill_tools import build_agent_reminder
from word_skill_tools import guess_qa_dir
from word_skill_tools import load_meta
from word_skill_tools import report_to_markdown
from word_skill_tools import resolve_standard_context
from word_skill_tools import run_docx_qa
from word_skill_tools import sidecar_path
from word_skill_tools import word_qa_report_to_observations
from word_skill_tools import write_agent_reminder
from word_skill_tools import write_json


def parse_args() -> argparse.Namespace:
    """解析命令行参数。"""

    parser = argparse.ArgumentParser(description="执行 DOCX 自动 QA，并输出 JSON / Markdown 报告")
    parser.add_argument("--meta", type=Path, help="可选：标准 refined workspace 中的 meta.json")
    parser.add_argument("--markdown", type=Path, help="可选：直接指定 Markdown 文件")
    parser.add_argument("--docx", type=Path, help="可选：直接指定输入 DOCX")
    parser.add_argument("--style-profile", help="可选：显式指定 style profile")
    parser.add_argument("--workflow-mode", choices=["lightweight", "refined"], help="可选：显式指定 workflow mode")
    parser.add_argument("--asset-manifest", type=Path, help="可选：显式指定 asset_manifest.json")
    parser.add_argument("--visual-review", type=Path, help="可选：显式指定 visual_review.md")
    parser.add_argument("--json-out", type=Path, help="可选：写出 JSON 报告")
    parser.add_argument("--md-out", type=Path, help="可选：写出 Markdown 报告")
    parser.add_argument(
        "--allow-missing-visual-review",
        action="store_true",
        help="如果当前只想做自动检查，可以允许 visual review 缺位",
    )
    return parser.parse_args()


def main() -> int:
    """执行 QA 并写出报告。"""

    args = parse_args()
    markdown_path, docx_path, profile_name, workflow_mode, meta_path, asset_manifest_path, visual_review_path = resolve_inputs(args)

    report = run_docx_qa(
        markdown_path=markdown_path,
        docx_path=docx_path,
        profile_name=profile_name,
        workflow_mode=workflow_mode,
        meta_path=meta_path,
        asset_manifest_path=asset_manifest_path,
        visual_review_path=visual_review_path,
        require_visual_review=not args.allow_missing_visual_review,
    )

    qa_dir = guess_qa_dir(docx_path)
    json_out = args.json_out or qa_dir / "qa_report.json"
    md_out = args.md_out or qa_dir / "qa_report.md"
    write_json(json_out, report)
    md_out.write_text(report_to_markdown("DOCX QA Report", report) + "\n", encoding="utf-8")
    observations = word_qa_report_to_observations(
        report,
        skill="word-polished-doc-collab",
        gate="docx_qa",
        artifact_path=docx_path,
    )
    reminder = build_agent_reminder(
        observations,
        source={"skill": "word-polished-doc-collab", "gate": "docx_qa"},
        artifact={"path": str(docx_path.resolve())},
        full_report_ref=str(json_out),
        target_milestone="final",
    )
    agent_json_out = sidecar_path(json_out, ".json")
    agent_md_out = sidecar_path(md_out, ".md")
    write_agent_reminder(json_path=agent_json_out, md_path=agent_md_out, reminder=reminder)

    print(f"[INFO] style_profile={profile_name} workflow_mode={workflow_mode}")
    print(f"[INFO] json_report={json_out}")
    print(f"[INFO] markdown_report={md_out}")
    print(f"[INFO] agent_reminder_json={agent_json_out}")
    print(f"[INFO] agent_reminder_markdown={agent_md_out}")
    print(f"[INFO] agent_reminder_decision={reminder['decision']['state']}")
    warning_count = report["advisory_summary"]["warning"]
    print(f"[INFO] advisory_warnings={warning_count}")

    if report["passed_all_checks"]:
        if warning_count:
            print(f"[WARN] DOCX QA 硬检查通过，但有 {warning_count} 个默认契约 warning；请修复或记录保留理由")
            return 0
        print("[OK] DOCX QA 全部通过")
        return 0

    failed_checks = [name for name, result in report["checks"].items() if not result["passed"]]
    print(f"[FAIL] DOCX QA 未通过，失败检查：{', '.join(failed_checks)}")
    return 1


def resolve_inputs(args: argparse.Namespace) -> tuple[Path, Path, str, str, Path | None, Path | None, Path | None]:
    """解析 QA 所需输入上下文。"""

    if args.meta is None and (args.markdown is None or args.docx is None):
        raise SystemExit("未提供 `--meta` 时，必须同时提供 `--markdown` 与 `--docx`。")

    markdown_path = args.markdown.resolve() if args.markdown else None
    docx_path = args.docx.resolve() if args.docx else None
    asset_manifest_path = args.asset_manifest.resolve() if args.asset_manifest else None
    visual_review_path = args.visual_review.resolve() if args.visual_review else None
    profile_name = args.style_profile
    workflow_mode = args.workflow_mode
    meta_path = args.meta.resolve() if args.meta else None

    if meta_path is not None:
        context = resolve_standard_context(meta_path)
        meta = load_meta(meta_path)
        markdown_path = markdown_path or context["markdown_path"]
        docx_path = docx_path or context["output_docx"]
        asset_manifest_path = asset_manifest_path or context["asset_manifest_path"]
        visual_review_path = visual_review_path or context["visual_review_path"]
        profile_name = profile_name or str(meta.get("style_profile", "cn_song_times"))
        workflow_mode = workflow_mode or str(meta.get("workflow_mode", "refined"))

    if markdown_path is None or docx_path is None:
        raise SystemExit("无法解析 Markdown 或 DOCX 路径。")
    return (
        markdown_path,
        docx_path,
        profile_name or "cn_song_times",
        workflow_mode or "refined",
        meta_path,
        asset_manifest_path,
        visual_review_path,
    )


if __name__ == "__main__":
    raise SystemExit(main())
