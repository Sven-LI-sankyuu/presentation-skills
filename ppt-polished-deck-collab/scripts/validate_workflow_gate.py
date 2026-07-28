#!/usr/bin/env python3
"""Validate the persisted Grill-Me workflow before outline, build, or final delivery."""

from __future__ import annotations

import argparse
import json
from datetime import date, datetime
from pathlib import Path
from typing import Any

import yaml


ALLOWED_STATES = {
    "questioning",
    "outline_ready",
    "awaiting_outline_feedback",
    "outline_approved",
    "executing",
    "reviewing",
    "revising",
    "final",
    "blocked",
    "stopped",
}
ALLOWED_APPROVAL_STATUSES = {"pending", "approved", "revoked"}
TARGET_STATES = {
    "intake": ALLOWED_STATES,
    "outline": {
        "outline_ready",
        "awaiting_outline_feedback",
        "outline_approved",
        "executing",
        "reviewing",
        "revising",
        "final",
    },
    "build": {"outline_approved", "executing", "revising"},
    "final": {"final"},
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate the five-stage deck workflow gate")
    parser.add_argument("--workspace-dir", required=True, type=Path)
    parser.add_argument("--target", choices=tuple(TARGET_STATES), default="build")
    parser.add_argument(
        "--require-workflow",
        action="store_true",
        help="Fail instead of warning when a legacy workspace has no workflow mapping",
    )
    parser.add_argument("--json-out", type=Path)
    return parser.parse_args()


def _is_non_empty_string(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _json_default(value: Any) -> str:
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    raise TypeError(f"Object of type {type(value).__name__} is not JSON serializable")


def load_frontmatter(path: Path) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8-sig")
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        raise ValueError("deck_narrative.md must start with YAML frontmatter")
    try:
        closing = next(index for index, line in enumerate(lines[1:], start=1) if line.strip() == "---")
    except StopIteration as exc:
        raise ValueError("deck_narrative.md frontmatter has no closing delimiter") from exc
    data = yaml.safe_load("\n".join(lines[1:closing])) or {}
    if not isinstance(data, dict):
        raise ValueError("deck_narrative.md frontmatter must be a mapping")
    return data


def validate_workflow(
    workflow: Any,
    *,
    target: str,
    require_workflow: bool,
) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []

    if workflow is None:
        message = "workflow mapping is missing; initialize or migrate the workspace before using the five-stage gate"
        (errors if require_workflow else warnings).append(message)
        return errors, warnings
    if not isinstance(workflow, dict):
        return ["workflow must be a mapping"], warnings

    version = workflow.get("version")
    if version != 1:
        errors.append("workflow.version must be 1")

    state = workflow.get("state")
    if not isinstance(state, str) or state not in ALLOWED_STATES:
        errors.append(f"workflow.state must be one of {sorted(ALLOWED_STATES)}")
        return errors, warnings
    if state not in TARGET_STATES[target]:
        errors.append(f"workflow.state={state!r} does not satisfy target={target!r}")

    outline_version = workflow.get("outline_version")
    if target in {"outline", "build", "final"} and not _is_non_empty_string(outline_version):
        errors.append(f"workflow.outline_version must be a non-empty string for target={target!r}")

    approval = workflow.get("approval")
    if not isinstance(approval, dict):
        errors.append("workflow.approval must be a mapping")
        return errors, warnings

    approval_status = approval.get("status")
    if not isinstance(approval_status, str) or approval_status not in ALLOWED_APPROVAL_STATUSES:
        errors.append(f"workflow.approval.status must be one of {sorted(ALLOWED_APPROVAL_STATUSES)}")

    if target in {"build", "final"}:
        if approval_status != "approved":
            errors.append("workflow.approval.status must be 'approved' before build")
        if approval.get("outline_version") != outline_version:
            errors.append("workflow.approval.outline_version must match workflow.outline_version")
        if not _is_non_empty_string(approval.get("evidence")):
            errors.append("workflow.approval.evidence must record the user's explicit approval")

    return errors, warnings


def evaluate_workspace(workspace_dir: Path, *, target: str, require_workflow: bool) -> dict[str, Any]:
    narrative_path = workspace_dir / "deck_narrative.md"
    errors: list[str] = []
    warnings: list[str] = []
    workflow: Any = None

    if not narrative_path.is_file():
        errors.append("deck_narrative.md is missing")
    else:
        try:
            frontmatter = load_frontmatter(narrative_path)
            workflow = frontmatter.get("workflow")
            workflow_errors, workflow_warnings = validate_workflow(
                workflow,
                target=target,
                require_workflow=require_workflow,
            )
            errors.extend(workflow_errors)
            warnings.extend(workflow_warnings)
        except (OSError, UnicodeError, ValueError, yaml.YAMLError) as exc:
            errors.append(str(exc))

    return {
        "workspace": str(workspace_dir),
        "target": target,
        "require_workflow": require_workflow,
        "workflow": workflow,
        "errors": errors,
        "warnings": warnings,
        "ok": not errors,
    }


def main() -> int:
    args = parse_args()
    workspace_dir = args.workspace_dir.resolve()
    result = evaluate_workspace(
        workspace_dir,
        target=args.target,
        require_workflow=args.require_workflow,
    )

    for warning in result["warnings"]:
        print(f"[WARN] {warning}")
    for error in result["errors"]:
        print(f"[ERROR] {error}")

    if args.json_out:
        args.json_out.parent.mkdir(parents=True, exist_ok=True)
        args.json_out.write_text(
            json.dumps(result, ensure_ascii=False, indent=2, default=_json_default),
            encoding="utf-8",
        )
        print(f"[INFO] wrote {args.json_out}")

    if result["errors"]:
        print(f"[FAIL] workflow gate rejected target={args.target}")
        return 1
    print(f"[OK] workflow gate passed target={args.target}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
