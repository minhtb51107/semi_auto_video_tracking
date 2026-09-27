import json
from contextlib import redirect_stdout
import io
from pathlib import Path
import sys
import unittest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "tools"))
sys.path.insert(0, str(PROJECT_ROOT / "tests"))

from run_cvat_pipeline import main, run
from test_run_cvat_pipeline import FakeCVAT, CounterTracker, args, test_workspace
from workspace_lifecycle import (WorkspaceError, cleanup_frames, cleanup_run,
                                 validate_completed_workspace, workspace_status)


def completed(root):
    api = FakeCVAT()
    run(args(root, "all"), api, CounterTracker())
    return Path(root) / "runs" / "task_20_job_18"


class WorkspaceLifecycleTests(unittest.TestCase):
    def test_workspace_status_sizes_classification_and_eligibility(self):
        with test_workspace() as tmp:
            workspace = completed(tmp)
            status = workspace_status(workspace)
            self.assertEqual(status["pipeline_status"], "COMPLETE")
            self.assertTrue(status["cleanup_eligibility"]["eligible"])
            self.assertGreater(status["total_bytes"], status["sizes"]["mot_bytes"])
            self.assertGreater(status["sizes"]["frames_bytes"], 0)
            self.assertIn("SAFE_TO_DELETE_AFTER_VERIFY", status["artifact_classification"]["frames"])

    def test_workspace_status_cli_is_read_only(self):
        with test_workspace() as tmp:
            workspace = completed(tmp)
            before = sorted((str(p.relative_to(workspace)), p.stat().st_size) for p in workspace.rglob("*") if p.is_file())
            output = io.StringIO()
            with redirect_stdout(output):
                code = main(["--task-id", "20", "--job-id", "18", "--output-root", str(Path(tmp)/"runs"), "--workspace-status"])
            after = sorted((str(p.relative_to(workspace)), p.stat().st_size) for p in workspace.rglob("*") if p.is_file())
            self.assertEqual(code, 0); self.assertEqual(before, after)
            self.assertEqual(json.loads(output.getvalue())["pipeline_status"], "COMPLETE")

    def test_cleanup_frames_preserves_audit_and_is_idempotent(self):
        with test_workspace() as tmp:
            workspace = completed(tmp)
            first = cleanup_frames(workspace)
            second = cleanup_frames(workspace)
            self.assertEqual((first["status"], first["removed_count"]), ("CLEANED", 5))
            self.assertEqual((second["status"], second["removed_count"]), ("ALREADY_CLEAN", 0))
            self.assertFalse(list((workspace / "frames").glob("*.jpg")))
            for name in ["metadata.json", "frames/manifest.json", "mot/predictions.txt",
                         "review_events.json", "cvat_push/predictions.json", "run_summary.json"]:
                self.assertTrue((workspace / name).is_file(), name)
            self.assertEqual(json.loads((workspace / "frames/manifest.json").read_text())["status"], "cleaned")
            self.assertTrue(validate_completed_workspace(workspace)["eligible"])

    def test_incomplete_or_hash_mismatch_cleanup_rejected(self):
        with test_workspace() as tmp:
            workspace = completed(tmp)
            summary_path = workspace / "run_summary.json"
            summary = json.loads(summary_path.read_text()); summary["status"] = "FAILED"
            summary_path.write_text(json.dumps(summary))
            with self.assertRaisesRegex(WorkspaceError, "run_not_complete"):
                cleanup_frames(workspace)
        with test_workspace() as tmp:
            workspace = completed(tmp)
            with (workspace / "mot/predictions.txt").open("a") as stream: stream.write("\n")
            with self.assertRaisesRegex(WorkspaceError, "mot_hash_mismatch"):
                cleanup_frames(workspace)

    def test_cleanup_run_preview_confirmation_and_minimal_manifest(self):
        with test_workspace() as tmp:
            workspace = completed(tmp)
            before = sorted(str(p.relative_to(workspace)) for p in workspace.rglob("*") if p.is_file())
            preview = cleanup_run(workspace)
            after_preview = sorted(str(p.relative_to(workspace)) for p in workspace.rglob("*") if p.is_file())
            self.assertEqual(preview["status"], "PREVIEW")
            self.assertEqual(before, after_preview)
            with self.assertRaisesRegex(WorkspaceError, "Confirmation"):
                cleanup_run(workspace, "wrong_workspace")
            result = cleanup_run(workspace, workspace.name)
            self.assertEqual(result["status"], "CLEANED")
            audit = json.loads((workspace / "minimal_audit_manifest.json").read_text())
            for key in ("task", "job", "model_sha256", "tracker_sha256", "mot_sha256",
                        "result_summary", "cvat_mapping_summary", "removed_files", "released_bytes"):
                self.assertIn(key, audit)
            remaining=[str(path.relative_to(workspace)) for path in workspace.rglob("*") if path.is_file()]
            self.assertEqual(remaining,["minimal_audit_manifest.json"])
            self.assertEqual(cleanup_run(workspace,workspace.name)["status"],"ALREADY_CLEAN")


if __name__ == "__main__":
    unittest.main()
