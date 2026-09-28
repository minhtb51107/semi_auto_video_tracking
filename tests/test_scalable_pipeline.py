import copy
import json
from pathlib import Path
from types import SimpleNamespace
import sys
import unittest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "tools"))
sys.path.insert(0, str(PROJECT_ROOT / "tests"))

from label_mapping import LabelMappingError, load_label_config, match_task_labels
from run_cvat_pipeline import run, run_task
from test_run_cvat_pipeline import FakeCVAT, args, test_workspace
from tracking_runtime import (ByteTrackTracker, Detection, TrackBox, TrackingRuntimeError,
                              run_chunked)


CONFIG = PROJECT_ROOT / "configs" / "label_mappings.json"


class MockDetector:
    identity = {"implementation": "MockDetector"}

    def __init__(self, fail_frame=None):
        self.calls = []
        self.fail_frame = fail_frame

    def detect(self, image_path, frame_id):
        self.calls.append(frame_id)
        if frame_id == self.fail_frame:
            raise RuntimeError("injected detector crash")
        class_id = 0 if frame_id % 2 else 67
        name = "person" if class_id == 0 else "cell phone"
        return [Detection(frame_id, (frame_id, 2, 10, 8), .8, class_id, name)]


class MockTracker:
    identity = {"implementation": "MockTracker"}

    def reset(self):
        self.frames = []

    def update(self, detections, frame_id):
        self.frames.append(frame_id)
        return [TrackBox(frame_id, 100 + d.class_id, d.bbox, d.confidence,
                         d.class_id, d.class_name) for d in detections]


class MultiJobAPI(FakeCVAT):
    def __init__(self):
        super().__init__(frames=3)
        self.jobs = [copy.deepcopy(self.job), dict(copy.deepcopy(self.job), id=19)]

    def request(self, method, path, payload=None):
        if method == "GET" and path == "/api/jobs/19":
            return dict(copy.deepcopy(self.jobs[1]), dimension="3d")
        if method == "GET" and path == "/api/jobs/19/data/meta":
            return copy.deepcopy(self.meta)
        if method == "GET" and path == "/api/jobs/19/annotations":
            return copy.deepcopy(self.annotations)
        return super().request(method, path, payload)

    def listing(self, path, **params):
        if path == "/api/jobs":
            return list(reversed(copy.deepcopy(self.jobs)))
        return super().listing(path, **params)


class ScalablePipelineTests(unittest.TestCase):
    def test_bytetrack_adapter_consumes_and_returns_normalized_objects(self):
        tracker=ByteTrackTracker("bytetrack.yaml")
        first=tracker.update([Detection(1,(1,2,10,8),.9,0,"person")],1)
        second=tracker.update([Detection(2,(2,2,10,8),.9,0,"person")],2)
        self.assertTrue(all(isinstance(value,TrackBox) for value in first+second))
        self.assertEqual((first[0].track_id,second[0].track_id),(1,1))
        self.assertEqual(first[0].class_id,0)

    def test_single_multiple_alias_and_mixed_unsupported_labels(self):
        config = load_label_config(CONFIG)
        labels = [{"id": 1, "name": "person", "type": "rectangle"},
                  {"id": 2, "name": "phone", "type": "rectangle"},
                  {"id": 3, "name": "head", "type": "rectangle"},
                  {"id": 4, "name": "vehicle", "type": "polygon"}]
        single = match_task_labels(labels, config, ["person"])
        self.assertEqual(single["detector_classes"], [0])
        multiple = match_task_labels(labels, config, ["person", "cell_phone"])
        self.assertEqual(multiple["detector_classes"], [0, 67])
        self.assertEqual(multiple["class_to_label"][67]["cvat_label"], "phone")
        mixed = match_task_labels(labels, config)
        self.assertEqual({x["label"] for x in mixed["unsupported"]}, {"head", "vehicle"})
        self.assertEqual({x["reason"] for x in mixed["unsupported"]},
                         {"UNSUPPORTED_LABEL", "INCORRECT_CVAT_LABEL_TYPE"})

    def test_ambiguous_alias_task_is_rejected(self):
        config = load_label_config(CONFIG)
        labels = [{"id": 1, "name": "cell_phone", "type": "rectangle"},
                  {"id": 2, "name": "phone", "type": "rectangle"}]
        with self.assertRaisesRegex(LabelMappingError, "same configured label"):
            match_task_labels(labels, config)

    def test_invalid_label_config_is_rejected(self):
        with test_workspace() as tmp:
            path=Path(tmp)/"labels.json"; path.write_text("[]")
            with self.assertRaisesRegex(LabelMappingError,"schema_version"):
                load_label_config(path)
            path.write_text(json.dumps({"schema_version":1,"labels":{
                "a":{"detector_classes":[0],"aliases":[]},
                "b":{"detector_classes":[0],"aliases":[]}}}))
            with self.assertRaisesRegex(LabelMappingError,"multiple labels"):
                load_label_config(path)

    def test_mock_detector_tracker_are_substitutable_and_class_identity_reaches_cvat(self):
        api = FakeCVAT(frames=4)
        api.labels = [{"id": 10, "name": "person", "type": "rectangle", "attributes": []},
                      {"id": 11, "name": "cell_phone", "type": "rectangle", "attributes": []},
                      {"id": 12, "name": "head", "type": "rectangle", "attributes": []}]
        with test_workspace() as tmp:
            value = args(tmp, "annotate")
            value.label_name = None; value.labels = "person,cell_phone"
            value.label_config = CONFIG; value.classes = None; value.chunk_size = 2
            detector = MockDetector(); tracker = MockTracker()
            result = run(value, api, runtime_factory=lambda config: (detector, tracker))
            self.assertEqual(result["predicted_boxes"], 4)
            self.assertEqual(result["detector_detections"], 4)
            self.assertEqual(result["tracks_per_class"]["person"]["tracks"], 1)
            self.assertEqual(result["tracks_per_class"]["cell_phone"]["tracks"], 1)
            self.assertEqual({track["label_id"] for track in api.annotations["tracks"]}, {10, 11})
            mot = (Path(tmp)/"runs/task_20_job_18/mot/predictions.txt").read_text()
            self.assertIn(",0,-1,-1", mot); self.assertIn(",67,-1,-1", mot)
            self.assertIn("elapsed_seconds", result); self.assertIn("inference", result["stage_elapsed_seconds"])

    def test_unsupported_label_dry_run_reports_without_crash(self):
        api = FakeCVAT(); api.labels = [{"id": 1, "name": "head", "type": "rectangle", "attributes": []}]
        with test_workspace() as tmp:
            value=args(tmp, "all", True); value.label_name=None; value.labels=None
            value.label_config=CONFIG; value.classes=None; value.chunk_size=2
            result=run(value,api)
            self.assertEqual(result["label_plan"]["supported"], [])
            self.assertEqual(result["label_plan"]["unsupported"][0]["reason"], "UNSUPPORTED_LABEL")

    def test_chunk_resume_replays_tracker_but_not_completed_detector_frames(self):
        with test_workspace() as tmp:
            root=Path(tmp); images=[]
            for frame in range(1,7):
                path=root/f"{frame:06d}.jpg"; path.write_bytes(b"fixture"); images.append(path)
            first=MockDetector(fail_frame=5)
            with self.assertRaisesRegex(RuntimeError,"injected"):
                run_chunked(images,first,MockTracker(),2,root/"chunks","cfg","inventory")
            self.assertEqual(first.calls,[1,2,3,4,5])
            second=MockDetector()
            tracks,manifest=run_chunked(images,second,MockTracker(),2,root/"chunks","cfg","inventory")
            self.assertEqual(second.calls,[5,6])
            self.assertEqual(manifest["status"],"complete")
            self.assertEqual([x.frame_id for x in tracks],[1,2,3,4,5,6])
            chunk=root/"chunks/chunk_000000.json"; original=chunk.read_text()
            changed=json.loads(original); changed["detections"][0]["confidence"]=.1
            chunk.write_text(json.dumps(changed))
            with self.assertRaisesRegex(TrackingRuntimeError,"hash mismatch"):
                run_chunked(images,MockDetector(),MockTracker(),2,root/"chunks","cfg","inventory")
            chunk.write_text(original)
            with self.assertRaisesRegex(TrackingRuntimeError,"Incompatible"):
                run_chunked(images,MockDetector(),MockTracker(),3,root/"chunks","changed","inventory")

    def test_all_jobs_is_deterministic_and_preserves_completed_job(self):
        api=MultiJobAPI()
        with test_workspace() as tmp:
            value=args(tmp,"all",True); value.job_id=None; value.all_jobs=True
            value.label_config=CONFIG; value.labels=None; value.chunk_size=2
            summary=run_task(value,api)
            self.assertEqual([x["job_id"] for x in summary["jobs"]],[18,19])
            self.assertEqual((summary["jobs_complete"],summary["jobs_failed"]),(1,1))
            self.assertEqual(summary["status"],"PARTIAL_FAILURE")
            self.assertTrue((Path(tmp)/"runs/task_20_job_18/run_summary.json").is_file())
            saved=json.loads((Path(tmp)/"runs/task_20_summary.json").read_text())
            self.assertEqual(saved["jobs_failed"],1)


if __name__ == "__main__":
    unittest.main()
