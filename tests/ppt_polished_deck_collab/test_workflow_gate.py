from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime
from pathlib import Path

import yaml


REPO_ROOT = Path(__file__).resolve().parents[2]
SKILL_ROOT = REPO_ROOT / "ppt-polished-deck-collab"
SCRIPTS_DIR = SKILL_ROOT / "scripts"


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


workflow_gate = load_module("validate_workflow_gate", SCRIPTS_DIR / "validate_workflow_gate.py")
workspace_init = load_module("init_deck_workspace", SCRIPTS_DIR / "init_deck_workspace.py")


def write_narrative(workspace: Path, workflow: dict | None) -> None:
    frontmatter: dict = {"deck": {"title": "Test Deck"}}
    if workflow is not None:
        frontmatter["workflow"] = workflow
    content = "---\n" + yaml.safe_dump(frontmatter, sort_keys=False) + "---\n\n# Test Deck\n"
    (workspace / "deck_narrative.md").write_text(content, encoding="utf-8")


def workflow(
    *,
    state: str = "questioning",
    outline_version: str | None = None,
    approval_status: str = "pending",
    approval_version: str | None = None,
    evidence: str | None = None,
) -> dict:
    return {
        "version": 1,
        "state": state,
        "outline_version": outline_version,
        "approval": {
            "status": approval_status,
            "outline_version": approval_version,
            "evidence": evidence,
            "approved_at": None,
        },
    }


class WorkflowGateTests(unittest.TestCase):
    def evaluate(self, value: dict | None, *, target: str = "build", required: bool = True):
        with tempfile.TemporaryDirectory() as temp_dir:
            workspace = Path(temp_dir)
            write_narrative(workspace, value)
            return workflow_gate.evaluate_workspace(
                workspace,
                target=target,
                require_workflow=required,
            )

    def test_legacy_workspace_warns_by_default(self):
        result = self.evaluate(None, target="intake", required=False)
        self.assertTrue(result["ok"])
        self.assertTrue(result["warnings"])

    def test_new_workspace_requires_workflow(self):
        result = self.evaluate(None, target="build", required=True)
        self.assertFalse(result["ok"])
        self.assertIn("workflow mapping is missing", result["errors"][0])

    def test_questioning_state_cannot_build(self):
        result = self.evaluate(workflow())
        self.assertFalse(result["ok"])
        self.assertTrue(any("does not satisfy" in error for error in result["errors"]))

    def test_unhashable_state_and_approval_status_return_errors(self):
        malformed_state = workflow()
        malformed_state["state"] = ["questioning"]
        state_result = self.evaluate(malformed_state, target="intake")
        self.assertFalse(state_result["ok"])
        self.assertTrue(any("workflow.state" in error for error in state_result["errors"]))

        malformed_approval = workflow(
            state="outline_approved",
            outline_version="v1",
            approval_status="approved",
            approval_version="v1",
            evidence="Approved v1",
        )
        malformed_approval["approval"]["status"] = {"approved": True}
        approval_result = self.evaluate(malformed_approval)
        self.assertFalse(approval_result["ok"])
        self.assertTrue(any("approval.status" in error for error in approval_result["errors"]))

    def test_approval_requires_current_outline_version(self):
        result = self.evaluate(
            workflow(
                state="outline_approved",
                outline_version="v2",
                approval_status="approved",
                approval_version="v1",
                evidence="Approved v1",
            )
        )
        self.assertFalse(result["ok"])
        self.assertTrue(any("must match" in error for error in result["errors"]))

    def test_approval_requires_evidence(self):
        result = self.evaluate(
            workflow(
                state="outline_approved",
                outline_version="v1",
                approval_status="approved",
                approval_version="v1",
            )
        )
        self.assertFalse(result["ok"])
        self.assertTrue(any("evidence" in error for error in result["errors"]))

    def test_current_explicit_approval_passes_build_gate(self):
        result = self.evaluate(
            workflow(
                state="outline_approved",
                outline_version="v1",
                approval_status="approved",
                approval_version="v1",
                evidence="User: approve this complete v1 outline",
            )
        )
        self.assertTrue(result["ok"], result["errors"])

    def test_reviewing_and_final_must_transition_before_rebuild(self):
        for state in ("reviewing", "final"):
            with self.subTest(state=state):
                result = self.evaluate(
                    workflow(
                        state=state,
                        outline_version="v1",
                        approval_status="approved",
                        approval_version="v1",
                        evidence="Approved v1",
                    )
                )
                self.assertFalse(result["ok"])
                self.assertTrue(any("does not satisfy" in error for error in result["errors"]))

    def test_revising_state_can_rebuild_the_approved_outline(self):
        result = self.evaluate(
            workflow(
                state="revising",
                outline_version="v1",
                approval_status="approved",
                approval_version="v1",
                evidence="Approved v1",
            )
        )
        self.assertTrue(result["ok"], result["errors"])

    def test_json_report_serializes_yaml_timestamp(self):
        value = workflow(
            state="outline_approved",
            outline_version="v1",
            approval_status="approved",
            approval_version="v1",
            evidence="Approved v1",
        )
        approved_at = datetime.fromisoformat("2026-07-28T15:30:00+09:00")
        value["approval"]["approved_at"] = approved_at

        with tempfile.TemporaryDirectory() as temp_dir:
            workspace = Path(temp_dir)
            write_narrative(workspace, value)
            report_path = workspace / "workflow.json"
            completed = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPTS_DIR / "validate_workflow_gate.py"),
                    "--workspace-dir",
                    str(workspace),
                    "--target",
                    "build",
                    "--require-workflow",
                    "--json-out",
                    str(report_path),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            report = json.loads(report_path.read_text(encoding="utf-8"))

        self.assertEqual(completed.returncode, 0, completed.stderr or completed.stdout)
        self.assertEqual(report["workflow"]["approval"]["approved_at"], approved_at.isoformat())

    def test_final_target_requires_final_state(self):
        approved = workflow(
            state="reviewing",
            outline_version="v1",
            approval_status="approved",
            approval_version="v1",
            evidence="Approved",
        )
        self.assertFalse(self.evaluate(approved, target="final")["ok"])
        approved["state"] = "final"
        self.assertTrue(self.evaluate(approved, target="final")["ok"])

    def test_workspace_template_contains_parseable_workflow(self):
        narrative = workspace_init.narrative_template("Deck", "Board", "Review", "Approve")
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "deck_narrative.md"
            path.write_text(narrative, encoding="utf-8")
            frontmatter = workflow_gate.load_frontmatter(path)
        self.assertEqual(frontmatter["workflow"]["state"], "questioning")
        self.assertEqual(frontmatter["workflow"]["approval"]["status"], "pending")

    def test_behavior_eval_manifest_is_well_formed(self):
        manifest_path = Path(__file__).with_name("grill_me_eval_cases.yaml")
        manifest = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
        cases = manifest["cases"]
        case_ids = [case["id"] for case in cases]
        self.assertEqual(len(case_ids), len(set(case_ids)))
        self.assertGreaterEqual(len(cases), 5)
        for case in cases:
            self.assertTrue(case["prompt"].strip())
            self.assertGreaterEqual(len(case["expected"]), 2)


if __name__ == "__main__":
    unittest.main()
