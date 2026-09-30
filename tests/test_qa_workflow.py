import copy
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "tests"))

from motlib import Det
from cvat_integration import reconcile
from qa_workflow import (compact_review_state, deterministic_qa_samples,
                         final_validate, release_decision)
from review_priority import load_policy, prioritize_events, select_events
from review_tracks import analyze, load_config
from review_tracks_v2 import duplicate_flags, validate_config, DEFAULT_V2
from run_cvat_pipeline import fetch_live_snapshot, issue_plan, run, validate_target
from test_run_cvat_pipeline import FakeCVAT, args, test_workspace
from run_golden_qa import run_manifest


def mapping(count=10):
    return [{"mot_frame": i, "cvat_frame": i-1, "width": 100, "height": 50,
             "remote_name": f"{i}.jpg", "local_name": f"{i:06d}.jpg"}
            for i in range(1, count+1)]


def event(event_id, track, start, end, reasons, flags):
    return {"event_id": event_id, "track_id": track, "related_track_ids": [],
            "class_id": 2, "related_class_ids": [], "start_frame": start,
            "end_frame": end, "anchor_frame": end, "reasons": reasons,
            "raw_flag_ids": flags, "context_start": max(1, start-1),
            "context_end": min(10, end+1)}


class PriorityAndQAWorkflowTests(unittest.TestCase):
    def setUp(self):
        self.policy = load_policy()
        self.events = {"schema_version": 2, "events": [
            event("E000001", 1, 2, 8, ["track_gap", "track_reappeared"], ["F1", "F2"]),
            event("E000002", 2, 5, 6, ["low_consecutive_iou"], ["F3"]),
        ]}
        self.flags = {"flags": [
            {"raw_flag_id": "F1", "reason": "track_gap", "observed_value": 5},
            {"raw_flag_id": "F2", "reason": "track_reappeared", "observed_value": 5},
            {"raw_flag_id": "F3", "reason": "low_consecutive_iou", "observed_value": .05},
        ]}
        self.rows = [(2, 1, 20, 10, 20, 10, .8), (8, 1, 30, 10, 20, 10, .7),
                     (5, 2, 40, 10, 20, 10, .9)]

    def test_priority_is_deterministic_ordered_and_explainable(self):
        first = prioritize_events(self.events, self.flags, self.rows, mapping(), self.policy)
        second = prioritize_events(copy.deepcopy(self.events), copy.deepcopy(self.flags), list(reversed(self.rows)), mapping(), self.policy)
        self.assertEqual(first, second)
        self.assertEqual([x["event_id"] for x in first["events"]], ["E000001", "E000002"])
        self.assertGreater(first["events"][0]["priority_score"], first["events"][1]["priority_score"])
        self.assertIn(first["events"][0]["severity"], ("CRITICAL", "HIGH", "MEDIUM", "LOW"))
        self.assertTrue(first["events"][0]["priority_reasons"])
        self.assertEqual(first["events"][0]["reasons"], self.events["events"][0]["reasons"])

    def test_priority_filtering_preserves_event_identity_and_default_scope(self):
        value = prioritize_events(self.events, self.flags, self.rows, mapping(), self.policy)
        default = select_events(value)
        self.assertEqual({x["event_id"] for x in default["events"]}, {"E000001", "E000002"})
        top = select_events(value, max_events=1)
        self.assertEqual([x["event_id"] for x in top["events"]], ["E000001"])
        high = select_events(value, min_severity="HIGH")
        self.assertTrue(all(x["severity"] in ("CRITICAL", "HIGH") for x in high["events"]))
        self.assertEqual(self.events["events"][0]["event_id"], "E000001")

    def test_class_aware_duplicate_and_fragmentation_keep_legacy_fallback(self):
        config = validate_config(__import__("json").loads(DEFAULT_V2.read_text()))
        cross = [d for frame in (1, 2, 3) for d in (
            Det(frame, 1, 0, 0, 50, 30, .9, 0),
            Det(frame, 2, 0, 0, 50, 30, .9, 2))]
        same = [Det(d.frame, d.track_id, d.x, d.y, d.w, d.h, d.conf, 2) for d in cross]
        legacy = [Det(d.frame, d.track_id, d.x, d.y, d.w, d.h) for d in cross]
        self.assertEqual(duplicate_flags(cross, config), [])
        self.assertEqual(len(duplicate_flags(same, config)), 1)
        self.assertEqual(len(duplicate_flags(legacy, config)), 1)
        v1 = load_config()
        fragmented_cross = [Det(1, 1, 0, 0, 20, 20, 1, 0), Det(2, 2, 0, 0, 20, 20, 1, 2)]
        fragmented_legacy = [Det(1, 1, 0, 0, 20, 20), Det(2, 2, 0, 0, 20, 20)]
        self.assertFalse(any(x["reason"] == "possible_fragmentation" for x in analyze(fragmented_cross, v1)))
        self.assertTrue(any(x["reason"] == "possible_fragmentation" for x in analyze(fragmented_legacy, v1)))

    def test_random_qa_is_deterministic_unique_and_excludes_flag_context(self):
        events = {"events": [event("E1", 1, 3, 4, ["track_gap"], ["F1"])]}
        first = deterministic_qa_samples(events, self.rows, mapping(), 4, 42, 20, 18, "hash")
        second = deterministic_qa_samples(events, self.rows, mapping(), 4, 42, 20, 18, "hash")
        self.assertEqual(first, second)
        frames = [x["frame"] for x in first["samples"]]
        self.assertEqual(len(frames), len(set(frames)))
        self.assertFalse(set(frames) & {2, 3, 4, 5})
        changed = deterministic_qa_samples(events, self.rows, mapping(), 4, 43, 20, 18, "hash")
        self.assertNotEqual(frames, [x["frame"] for x in changed["samples"]])

    def test_random_qa_small_job_returns_available_without_duplicates(self):
        events = {"events": [event("E1", 1, 1, 8, ["track_gap"], ["F1"])]}
        value = deterministic_qa_samples(events, [], mapping(), 20, 42, 1, 1, "hash")
        self.assertEqual(value["generated"], 1)
        self.assertEqual(value["samples"][0]["frame"], 10)

    def validation_fixture(self, resolved_review=False, resolved_qa=False, invalid=False):
        snap = {"job": {"start_frame": 0, "stop_frame": 2},
                "labels": [{"id": 10, "name": "vehicle", "type": "rectangle"}],
                "mapping": mapping(3)}
        points = [10, 10, 20, 20] if not invalid else [20, 10, 10, 20]
        annotations = {"tracks": [{"id": 100, "label_id": 10,
                                     "shapes": [{"frame": 0, "points": points, "outside": False}]}]}
        review_item = {"marker": "SATV2|x|E1", "metadata": {"type": "REVIEW_EVENT", "severity": "HIGH"}}
        qa_item = {"marker": "QA-SAMPLE|x|Q1", "metadata": {"type": "RANDOM_QA", "severity": "LOW"}}
        plan = {"items": [review_item, qa_item], "qa_items": [qa_item]}
        issues = [{"id": 1, "resolved": resolved_review}, {"id": 2, "resolved": resolved_qa}]
        comments = [{"issue": 1, "message": "SATV2|x|E1\ntext"},
                    {"issue": 2, "message": "QA-SAMPLE|x|Q1\ntext"}]
        labels = {"supported": [{"cvat_label_id": 10}]}
        return snap, annotations, labels, plan, issues, comments

    def test_final_validation_and_release_policy(self):
        values = self.validation_fixture()
        validation = final_validate(values[0], values[1], values[2], values[3],
                                    {"items": values[3]["qa_items"]}, values[4], values[5])
        self.assertEqual(validation["structural_checks"], "PASS")
        self.assertEqual(validation["review_events"], 1)
        self.assertEqual(validation["unresolved_by_severity"]["HIGH"], 1)
        self.assertEqual(release_decision(validation, self.policy)["status"], "REVIEW_REQUIRED")
        values = self.validation_fixture(True, True)
        done = final_validate(values[0], values[1], values[2], values[3],
                              {"items": values[3]["qa_items"]}, values[4], values[5])
        self.assertEqual(release_decision(done, self.policy)["status"], "READY_FOR_EXPORT")
        values = self.validation_fixture(True, True, True)
        bad = final_validate(values[0], values[1], values[2], values[3],
                             {"items": values[3]["qa_items"]}, values[4], values[5])
        self.assertEqual(release_decision(bad, self.policy)["status"], "BLOCKED")

    def test_review_state_is_compact(self):
        values = self.validation_fixture(True, True)
        validation = final_validate(values[0], values[1], values[2], values[3],
                                    {"items": values[3]["qa_items"]}, values[4], values[5])
        state = compact_review_state(1, 2, values[3], {"items": values[3]["qa_items"]}, validation)
        self.assertEqual((state["review_events_generated"], state["qa_samples_generated"]), (1, 1))
        self.assertEqual((state["issues_resolved"], state["qa_samples_completed"]), (1, 1))

    def test_issue_plan_exposes_priority_and_distinct_random_qa(self):
        api = FakeCVAT(frames=10)
        snapshot, _ = fetch_live_snapshot(api, 20, 18)
        frame_mapping = validate_target(snapshot, 20, 18)
        prioritized = prioritize_events(self.events, self.flags, self.rows, frame_mapping, self.policy)
        qa = deterministic_qa_samples({"events": []}, self.rows, frame_mapping, 1, 42, 20, 18, "hash")
        selected = select_events(prioritized)
        plan = issue_plan(selected, snapshot, frame_mapping, api.url, self.rows,
                          {"external_to_cvat_track": {"1": 1001, "2": 1002}}, qa)
        review = next(x for x in plan["items"] if x["metadata"]["type"] == "REVIEW_EVENT")
        sample = next(x for x in plan["items"] if x["metadata"]["type"] == "RANDOM_QA")
        self.assertIn(f"Severity: {review['metadata']['severity']}", review["payload"]["message"])
        self.assertIn("Priority score:", review["payload"]["message"])
        self.assertTrue(review["metadata"]["priority_reasons"])
        self.assertTrue(sample["marker"].startswith("QA-SAMPLE|"))
        self.assertIn("Random non-flagged QA sample", sample["payload"]["message"])
        self.assertEqual(sample["metadata"]["severity"], "LOW")

        issues, comments, prior = [], [], {}
        for index, item in enumerate(plan["items"], 1):
            issues.append({"id": index, "job": 18, "frame": item["payload"]["frame"],
                           "position": item["payload"]["position"], "resolved": False})
            comments.append({"id": index, "issue": index, "message": item["payload"]["message"]})
            prior[item["event_id"]] = index
        actions = reconcile(plan, issues, comments, prior)
        self.assertTrue(all(x["action"] == "SKIP_EXISTING" for x in actions))

    def test_final_validate_and_release_stages_never_mutate_annotations(self):
        api = FakeCVAT(frames=3)
        with test_workspace() as tmp:
            workspace = Path(tmp)/"runs"/"task_20_job_18"
            workspace.mkdir(parents=True)
            (workspace/"review_state.json").write_text(json.dumps({
                "issues_created": 4, "issues_skipped": 0, "raw_flags": 6,
                "aggregated_events": 4, "selected_events": 4,
            }), encoding="utf-8")
            for stage, expected in (("final-validate", "FINAL_VALIDATION_PASS"),
                                    ("release-check", "READY_FOR_EXPORT")):
                value = args(tmp, stage)
                value.label_config = ROOT/"configs/label_mappings.json"
                value.labels = None; value.all_jobs = False
                result = run(value, api)
                self.assertEqual(result["status"], expected)
                self.assertTrue(result["read_only"])
                self.assertEqual(result["review_state"]["issues_created"], 4)
            self.assertEqual(api.annotation_patches, 0)

    def test_golden_manifest_behavior_runner(self):
        value = run_manifest()
        self.assertEqual(value["status"], "PASS")
        self.assertTrue(all(x["automated_ground_truth"] is False for x in value["cases"]))


if __name__ == "__main__":
    unittest.main()
