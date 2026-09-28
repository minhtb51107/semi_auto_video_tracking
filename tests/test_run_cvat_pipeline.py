import copy
from contextlib import contextmanager
from io import BytesIO
import json
from pathlib import Path
import sys
import unittest
import shutil
from types import SimpleNamespace
import uuid

from PIL import Image

PROJECT_ROOT = Path(__file__).resolve().parents[1]
TEST_TEMP = PROJECT_ROOT / ".runtime" / "pipeline_tests"
TEST_TEMP.mkdir(parents=True, exist_ok=True)
sys.path.insert(0, str(PROJECT_ROOT / "tools"))
from run_cvat_pipeline import (PipelineError, annotation_is_empty, cvat_track_payloads,
    ensure_frames, fetch_live_snapshot, issue_plan, push_predictions, read_mot_rows,
    push_issues, run, shape_count_audit, target_fingerprint, validate_target)


@contextmanager
def test_workspace():
    path = TEST_TEMP / ("case_" + uuid.uuid4().hex)
    path.mkdir(parents=True)
    try:
        yield str(path)
    finally:
        shutil.rmtree(path)


def jpeg_bytes(size=(100, 50)):
    stream = BytesIO()
    Image.new("RGB", size, "white").save(stream, "JPEG")
    return stream.getvalue()


class FakeCVAT:
    def __init__(self, frames=5):
        self.url = "http://localhost:8080"
        self.task = {"id": 20, "name": "fixture", "size": frames, "dimension": "2d",
                     "mode": "annotation", "project_id": None, "subset": "", "organization": None}
        self.job = {"id": 18, "task_id": 20, "start_frame": 0, "stop_frame": frames - 1,
                    "frame_count": frames, "type": "annotation", "dimension": "2d", "status": "annotation"}
        self.meta = {"size": frames, "start_frame": 0, "stop_frame": frames - 1,
                     "frame_filter": "", "deleted_frames": [], "included_frames": None,
                     "frames": [{"name": f"source_{i}.jpg", "width": 100, "height": 50} for i in range(frames)]}
        self.labels = [{"id": 158, "name": "vehicle", "type": "rectangle", "attributes": []}]
        self.annotations = {"version": 0, "tags": [], "shapes": [], "tracks": []}
        self.issues, self.comments, self.downloads, self.annotation_patches = [], [], 0, 0
        self.fail_download = False
        self.fail_at = None
        self.lose_annotation_response = False

    def request(self, method, path, payload=None):
        if method == "GET" and path == "/api/tasks/20": return copy.deepcopy(self.task)
        if method == "GET" and path == "/api/jobs/18": return copy.deepcopy(self.job)
        if method == "GET" and path == "/api/jobs/18/data/meta": return copy.deepcopy(self.meta)
        if method == "GET" and path == "/api/jobs/18/annotations": return copy.deepcopy(self.annotations)
        if method == "GET" and path == "/api/labels?task_id=20": return copy.deepcopy(self.labels)
        if method == "POST" and path == "/api/issues":
            issue = {"id": len(self.issues) + 1, "job": payload["job"], "frame": payload["frame"],
                     "position": payload["position"], "resolved": False}
            self.issues.append(issue)
            self.comments.append({"id": len(self.comments) + 1, "issue": issue["id"], "message": payload["message"]})
            return copy.deepcopy(issue)
        raise AssertionError((method, path))

    def listing(self, path, **params):
        return copy.deepcopy(self.issues if path == "/api/issues" else self.comments)

    def frame_bytes(self, job_id, cvat_frame):
        if self.fail_download: raise PipelineError("synthetic download failure")
        if self.fail_at == cvat_frame:
            self.fail_at = None
            raise PipelineError("synthetic interrupted download")
        self.downloads += 1
        return jpeg_bytes()

    def create_annotations(self, job_id, payload):
        self.annotation_patches += 1
        for track in copy.deepcopy(payload["tracks"]):
            track["id"] = 1000 + len(self.annotations["tracks"])
            for i, shape in enumerate(track["shapes"]): shape["id"] = 2000 + i
            self.annotations["tracks"].append(track)
        self.annotations["version"] += 1
        if self.lose_annotation_response:
            self.lose_annotation_response = False
            raise PipelineError("synthetic lost response after commit")
        return copy.deepcopy(self.annotations)


def args(root, stage="all", dry=False, allow=False):
    model = Path(root) / "model.pt"; model.write_bytes(b"model")
    tracker = Path(root) / "tracker.yaml"; tracker.write_text("tracker_type: bytetrack\n")
    return SimpleNamespace(task_id=20, job_id=18, stage=stage, dry_run=dry,
        allow_existing_annotations=allow, label_name="vehicle", model=str(model),
        tracker=str(tracker), conf=.25, iou=.7, imgsz=960, classes=[2,5,7],
        device=None, output_root=Path(root) / "runs")


class CounterTracker:
    def __init__(self): self.calls = 0
    def __call__(self, folder, model, tracker, conf, iou, imgsz, classes, device, verbose):
        self.calls += 1
        # A one-frame gap creates one Analyzer v2 event without any GT.
        return [(1, 7, 10, 10, 20, 10, .9), (3, 7, 11, 10, 20, 10, .8),
                (4, 8, 50, 10, 20, 10, .7)]


class PipelineTests(unittest.TestCase):
    def test_empty_task_metadata_and_frame_mapping(self):
        api = FakeCVAT(); snapshot, ann = fetch_live_snapshot(api, 20, 18)
        mapping = validate_target(snapshot, 20, 18)
        self.assertTrue(annotation_is_empty(ann)); self.assertEqual(len(mapping), 5)
        self.assertEqual((mapping[0]["mot_frame"], mapping[0]["cvat_frame"]), (1, 0))

    def test_nonzero_job_uses_job_local_frame_metadata_with_absolute_cvat_frames(self):
        api = FakeCVAT(frames=3)
        api.task["size"] = 6
        api.job.update(start_frame=3, stop_frame=5, frame_count=3)
        api.meta.update(start_frame=3, stop_frame=5)
        api.meta["frames"] = [
            {"name": f"source_{i}.jpg", "width": 100, "height": 50}
            for i in range(3, 6)
        ]
        snapshot, _ = fetch_live_snapshot(api, 20, 18)
        mapping = validate_target(snapshot, 20, 18)
        self.assertEqual([row["cvat_frame"] for row in mapping], [3, 4, 5])
        self.assertEqual([row["mot_frame"] for row in mapping], [1, 2, 3])
        self.assertEqual([row["remote_name"] for row in mapping],
                         ["source_3.jpg", "source_4.jpg", "source_5.jpg"])

    def test_task_job_mismatch_safe_failure(self):
        api = FakeCVAT(); api.job["task_id"] = 99
        with self.assertRaisesRegex(PipelineError, "mismatch"):
            fetch_live_snapshot(api, 20, 18)

    def test_target_hash_ignores_workflow_status_but_covers_frames(self):
        api=FakeCVAT(); snapshot,_=fetch_live_snapshot(api,20,18); original=target_fingerprint(snapshot)
        snapshot["job"]["status"]="completed"; snapshot["task"]["updated_date"]="later"
        self.assertEqual(target_fingerprint(snapshot),original)
        snapshot["meta"]["frames"][0]["name"]="changed.jpg"
        self.assertNotEqual(target_fingerprint(snapshot),original)

    def test_unexpected_metadata_schema_safe_failure(self):
        api=FakeCVAT(); api.annotations=[]
        with self.assertRaisesRegex(PipelineError,"schema"):
            fetch_live_snapshot(api,20,18)

    def test_sampled_or_out_of_range_source_rejected(self):
        api = FakeCVAT(); snapshot, _ = fetch_live_snapshot(api, 20, 18)
        snapshot["meta"]["frame_filter"] = "step=2"
        with self.assertRaises(PipelineError): validate_target(snapshot, 20, 18)
        snapshot["meta"]["frame_filter"] = ""; snapshot["meta"]["frames"].pop()
        with self.assertRaises(PipelineError): validate_target(snapshot, 20, 18)

    def test_download_failure_does_not_create_manifest(self):
        api = FakeCVAT(); api.fail_download = True
        with test_workspace() as tmp:
            snapshot, _ = fetch_live_snapshot(api, 20, 18); mapping = validate_target(snapshot, 20, 18)
            with self.assertRaises(PipelineError): ensure_frames(api, Path(tmp), snapshot, mapping)
            self.assertFalse((Path(tmp)/"frames"/"manifest.json").exists())

    def test_interrupted_frame_fetch_resumes_from_checkpoint(self):
        api = FakeCVAT(); api.fail_at = 2
        with test_workspace() as tmp:
            snapshot, _ = fetch_live_snapshot(api, 20, 18); mapping = validate_target(snapshot, 20, 18)
            with self.assertRaisesRegex(PipelineError, "interrupted"):
                ensure_frames(api, Path(tmp), snapshot, mapping)
            partial = json.loads((Path(tmp)/"frames"/"manifest.json").read_text())
            self.assertEqual((partial["status"], len(partial["frames"])), ("downloading", 2))
            done = ensure_frames(api, Path(tmp), snapshot, mapping)
            self.assertEqual((done["status"], len(done["frames"]), api.downloads), ("complete", 5, 5))

    def test_track_payload_preserves_ids_and_explicit_gap(self):
        api = FakeCVAT(); snapshot, _ = fetch_live_snapshot(api, 20, 18); mapping = validate_target(snapshot, 20, 18)
        payload = cvat_track_payloads([(1,7,1,2,10,5,.9),(3,7,2,2,10,5,.8)], mapping, 158)[0]
        self.assertEqual(payload["external_track_id"], 7)
        self.assertEqual([(x["frame"],x["outside"]) for x in payload["track"]["shapes"]],
                         [(0,False),(1,True),(2,False),(3,True)])

    def test_prediction_push_and_rerun_are_idempotent(self):
        api = FakeCVAT()
        with test_workspace() as tmp:
            root=Path(tmp); mot=root/"p.txt"; mot.write_text("1,7,1,2,10,5,0.9,-1,-1,-1\n")
            snapshot, ann=fetch_live_snapshot(api,20,18); mapping=validate_target(snapshot,20,18)
            first=push_predictions(api,root,snapshot,ann,mot,mapping,api.labels[0],False)
            second=push_predictions(api,root,snapshot,api.annotations,mot,mapping,api.labels[0],False)
            self.assertEqual((first["created_tracks"],second["created_tracks"]),(1,0))
            self.assertEqual(api.annotation_patches,1); self.assertEqual(second["external_to_cvat_track"]["7"],1000)

    def test_lost_annotation_response_reconciles_without_duplicate(self):
        api = FakeCVAT(); api.lose_annotation_response = True
        with test_workspace() as tmp:
            root=Path(tmp); mot=root/"p.txt"; mot.write_text("1,7,1,2,10,5,0.9,-1,-1,-1\n")
            snapshot, ann=fetch_live_snapshot(api,20,18); mapping=validate_target(snapshot,20,18)
            with self.assertRaisesRegex(PipelineError,"lost response"):
                push_predictions(api,root,snapshot,ann,mot,mapping,api.labels[0],False)
            result=push_predictions(api,root,snapshot,api.annotations,mot,mapping,api.labels[0],False)
            self.assertEqual((result["created_tracks"],len(api.annotations["tracks"])),(0,1))

    def test_existing_annotations_require_explicit_permission(self):
        api=FakeCVAT(); api.annotations["tracks"]=[{"id":9,"label_id":158,"frame":0,"source":"manual","shapes":[]}]
        with test_workspace() as tmp:
            a=args(tmp,"annotate")
            with self.assertRaisesRegex(PipelineError,"not empty"): run(a,api,CounterTracker())
            self.assertEqual(api.downloads,0); self.assertEqual(api.annotation_patches,0)

    def test_dry_run_is_read_only_and_reports_existing_safety(self):
        api=FakeCVAT(); api.annotations["tracks"]=[{"id":9,"label_id":158,"frame":0,"source":"manual","shapes":[]}]
        with test_workspace() as tmp:
            tracker=CounterTracker(); result=run(args(tmp,"all",True),api,tracker)
            self.assertEqual(result["status"],"DRY_RUN")
            self.assertEqual(result["annotation_safety"],"WOULD_ABORT_EXISTING_ANNOTATIONS")
            self.assertEqual((api.downloads,api.annotation_patches,tracker.calls),(0,0,0))

    def test_stage_annotate_only_and_resume(self):
        api=FakeCVAT()
        with test_workspace() as tmp:
            tracker=CounterTracker(); first=run(args(tmp,"annotate"),api,tracker); second=run(args(tmp,"annotate"),api,tracker)
            self.assertEqual(tracker.calls,1); self.assertEqual(api.annotation_patches,1)
            self.assertIsNone(first["review_events"]); self.assertEqual(second["annotation_push"]["created_tracks"],0)

    def test_stage_all_then_review_only_and_issue_idempotency(self):
        api=FakeCVAT()
        with test_workspace() as tmp:
            tracker=CounterTracker(); first=run(args(tmp,"all"),api,tracker)
            second=run(args(tmp,"review"),api,tracker)
            self.assertGreaterEqual(first["review_events"],1)
            self.assertEqual(first["issue_push"]["created"],len(api.issues))
            self.assertEqual(second["issue_push"]["created"],0)
            self.assertEqual(second["issue_push"]["skipped"],len(api.issues))
            self.assertEqual(tracker.calls,1)

    def test_post_human_edit_rerun_fails_before_mutation(self):
        api=FakeCVAT()
        with test_workspace() as tmp:
            tracker=CounterTracker(); run(args(tmp,"all"),api,tracker)
            issue_count=len(api.issues); patches=api.annotation_patches
            api.annotations["tracks"][0]["shapes"][0]["points"][0] += 1
            with self.assertRaisesRegex(PipelineError,"annotation state changed"):
                run(args(tmp,"review"),api,tracker)
            self.assertEqual((len(api.issues),api.annotation_patches),(issue_count,patches))

    def test_post_completion_dry_run_preserves_locked_history(self):
        api=FakeCVAT()
        with test_workspace() as tmp:
            root=Path(tmp); tracker=CounterTracker(); run(args(tmp,"all"),api,tracker)
            workspace=root/"runs"/"task_20_job_18"
            locked_summary=(workspace/"run_summary.json").read_bytes()
            locked_metadata=json.loads((workspace/"metadata.json").read_text(encoding="utf-8-sig"))
            api.annotations["tracks"][0]["shapes"][0]["points"][0] += 1
            result=run(args(tmp,"all",True),api,tracker)
            self.assertEqual(result["annotation_safety"],
                             "CVAT_ANNOTATION_STATE_CHANGED_SINCE_PREDICTION_PUSH")
            self.assertEqual((workspace/"run_summary.json").read_bytes(),locked_summary)
            self.assertEqual(json.loads((workspace/"metadata.json").read_text(encoding="utf-8-sig")),
                             locked_metadata)
            latest=json.loads((workspace/"metadata_latest.json").read_text(encoding="utf-8-sig"))
            self.assertNotEqual(latest["annotation_hash"],locked_metadata["annotation_hash"])
            self.assertEqual(json.loads((workspace/"dry_run_summary.json").read_text())["status"],
                             "DRY_RUN")
            self.assertEqual((api.annotation_patches,len(api.issues)),(1,1))

    def test_review_only_requires_completed_annotation_stage(self):
        api=FakeCVAT()
        with test_workspace() as tmp:
            with self.assertRaisesRegex(PipelineError,"requires"):
                run(args(tmp,"review"),api,CounterTracker())

    def test_malformed_and_out_of_bounds_mot_rejected(self):
        with test_workspace() as tmp:
            path=Path(tmp)/"bad.txt"; path.write_text("broken\n")
            with self.assertRaises(PipelineError): read_mot_rows(path)
            path.write_text("1,1,1,1,2,2,nan,-1,-1,-1\n")
            with self.assertRaises(PipelineError): read_mot_rows(path)
        api=FakeCVAT(); snapshot,_=fetch_live_snapshot(api,20,18); mapping=validate_target(snapshot,20,18)
        with self.assertRaises(PipelineError): cvat_track_payloads([(6,1,1,1,2,2,.5)],mapping,158)

    def test_issue_plan_uses_absolute_cvat_frame_without_object_id_guess(self):
        api=FakeCVAT(); api.job.update(start_frame=10,stop_frame=14); api.meta["frames"]=[{"name":f"x{i}","width":100,"height":50} for i in range(15)]
        api.task["size"]=15; api.meta["size"]=15
        snapshot,_=fetch_live_snapshot(api,20,18); mapping=validate_target(snapshot,20,18)
        data={"schema_version":2,"events":[{"event_id":"E000001","track_id":7,"related_track_ids":[],"start_frame":1,"end_frame":3,"anchor_frame":2,"context_start":1,"context_end":5,"reasons":["track_gap"],"raw_flag_ids":["F1"]}]}
        plan=issue_plan(data,snapshot,mapping,api.url); item=plan["items"][0]
        self.assertEqual(item["payload"]["frame"],11)
        self.assertEqual(item["metadata"]["object_mapping"],"UNAVAILABLE")
        self.assertNotIn("object_id",item["payload"])

    def test_issue_marker_uses_anchor_bbox_center_and_readable_metadata(self):
        api=FakeCVAT(); snapshot,_=fetch_live_snapshot(api,20,18); mapping=validate_target(snapshot,20,18)
        data={"schema_version":2,"events":[{"event_id":"E000001","track_id":7,"related_track_ids":[],"start_frame":1,"end_frame":3,"anchor_frame":3,"context_start":1,"context_end":5,"reasons":["track_gap"],"raw_flag_ids":["F1"]}]}
        rows=CounterTracker()(None,None,None,None,None,None,None,None,None)
        plan=issue_plan(data,snapshot,mapping,api.url,rows,{"external_to_cvat_track":{"7":1000}})
        item=plan["items"][0]
        self.assertEqual((item["payload"]["frame"],item["payload"]["position"]),(2,[21.0,15.0]))
        self.assertEqual(item["metadata"]["placement"]["mode"],"ANCHOR_BBOX_CENTER")
        for value in ["event_id=E000001","reasons=track_gap","cvat_track_id=1000","external_track_id=7",
                      "related_external_track_ids=none","analyzer_version=2"]:
            self.assertIn(value,item["payload"]["message"])
        for value in ["Possible tracking issue", "Label: unknown", "Reasons:\n- track gap",
                      "Suggested action:"]:
            self.assertIn(value,item["payload"]["message"])

    def test_existing_issue_plan_keeps_pre_upgrade_comment_and_position(self):
        api=FakeCVAT()
        with test_workspace() as tmp:
            root=Path(tmp); folder=root/"cvat_push"; folder.mkdir()
            old={"schema_version":1,"task_id":20,"job_id":18,"sequence":"task_20_job_18","source_sha256":"source",
                 "items":[{"event_id":"E000001","marker":"SATV2|task_20_job_18|E000001",
                           "payload":{"job":18,"frame":2,"position":[10,10],
                                      "message":"SATV2|task_20_job_18|E000001\nlegacy"}}]}
            new=copy.deepcopy(old); new["items"][0]["payload"].update(position=[20,20],message="changed")
            (folder/"issues_plan.json").write_text(json.dumps(old))
            first=push_issues(api,root,new)
            second=push_issues(api,root,new)
            self.assertEqual((first["created"],second["created"]),(1,0))
            self.assertEqual(api.issues[0]["position"],[10,10])
            self.assertTrue(api.comments[0]["message"].endswith("legacy"))

    def test_issue_marker_nearest_bbox_fallback_is_deterministic(self):
        api=FakeCVAT(); snapshot,_=fetch_live_snapshot(api,20,18); mapping=validate_target(snapshot,20,18)
        event={"event_id":"E000001","track_id":7,"related_track_ids":[],"start_frame":1,"end_frame":3,"anchor_frame":2,"context_start":1,"context_end":5,"reasons":["track_gap"],"raw_flag_ids":["F1"]}
        rows=CounterTracker()(None,None,None,None,None,None,None,None,None)
        item=issue_plan({"schema_version":2,"events":[event]},snapshot,mapping,api.url,rows,{"external_to_cvat_track":{"7":1000}})["items"][0]
        self.assertEqual((item["payload"]["frame"],item["metadata"]["placement"]["mot_frame"]),(0,1))
        self.assertEqual(item["metadata"]["placement"]["mode"],"NEAREST_BBOX_CENTER")

    def test_issue_marker_unmapped_track_and_invalid_geometry(self):
        api=FakeCVAT(); snapshot,_=fetch_live_snapshot(api,20,18); mapping=validate_target(snapshot,20,18)
        event={"event_id":"E000001","track_id":7,"related_track_ids":[],"start_frame":1,"end_frame":3,"anchor_frame":3,"context_start":1,"context_end":5,"reasons":["track_gap"],"raw_flag_ids":["F1"]}
        rows=CounterTracker()(None,None,None,None,None,None,None,None,None)
        fallback=issue_plan({"schema_version":2,"events":[event]},snapshot,mapping,api.url,rows,{"external_to_cvat_track":{}})["items"][0]
        self.assertEqual(fallback["metadata"]["placement"]["mode"],"FRAME_LEVEL_FALLBACK_UNMAPPED_TRACK")
        self.assertEqual(fallback["payload"]["position"],[10,10])
        partial=[(3,7,-5,10,20,10,.8)]
        clipped=issue_plan({"schema_version":2,"events":[event]},snapshot,mapping,api.url,partial,{"external_to_cvat_track":{"7":1000}})["items"][0]
        self.assertEqual(clipped["payload"]["position"],[7.5,15.0])
        self.assertEqual(clipped["metadata"]["placement"]["mode"],"CLIPPED_ANCHOR_BBOX_CENTER")
        self.assertEqual(clipped["metadata"]["placement"]["visible_bbox"],[0.0,10,15.0,10])
        bad=[(3,7,101,10,20,10,.8)]
        with self.assertRaisesRegex(PipelineError,"geometry"):
            issue_plan({"schema_version":2,"events":[event]},snapshot,mapping,api.url,bad,{"external_to_cvat_track":{"7":1000}})

    def test_shape_count_audit_distinguishes_visible_and_outside_keyframes(self):
        api=FakeCVAT(); snapshot,_=fetch_live_snapshot(api,20,18); mapping=validate_target(snapshot,20,18)
        rows=[(1,7,1,2,10,5,.9),(3,7,2,2,10,5,.8)]
        expected=cvat_track_payloads(rows,mapping,158)
        api.create_annotations(18,{"tracks":[x["track"] for x in expected]})
        audit=shape_count_audit(rows,expected,api.annotations,5)
        self.assertEqual((audit["mot_boxes"],audit["gap_boundary_outside_keyframes"],audit["terminal_outside_keyframes"],audit["remote_total_track_shapes"]),(2,1,1,4))
        self.assertEqual(audit["classification"],"EXPECTED")


if __name__ == "__main__":
    unittest.main()
