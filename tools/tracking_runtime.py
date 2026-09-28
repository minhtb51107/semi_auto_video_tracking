"""Normalized detector/tracker contracts and resumable chunk inference."""
from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import json
import math
from pathlib import Path
from typing import Protocol, Sequence


class TrackingRuntimeError(ValueError):
    pass


@dataclass(frozen=True)
class Detection:
    frame_id: int
    bbox: tuple[float, float, float, float]  # x, y, w, h
    confidence: float
    class_id: int
    class_name: str


@dataclass(frozen=True)
class TrackBox:
    frame_id: int
    track_id: int
    bbox: tuple[float, float, float, float]
    confidence: float
    class_id: int
    class_name: str

    def legacy(self) -> tuple[int, int, float, float, float, float, float]:
        return (self.frame_id, self.track_id, *self.bbox, self.confidence)

    def __getitem__(self, index):
        return self.legacy()[index]


class Detector(Protocol):
    identity: dict

    def detect(self, image_path: Path, frame_id: int) -> list[Detection]: ...


class Tracker(Protocol):
    identity: dict

    def reset(self) -> None: ...

    def update(self, detections: Sequence[Detection], frame_id: int) -> list[TrackBox]: ...


def _valid_detection(value: Detection) -> None:
    x, y, w, h = value.bbox
    if (value.frame_id < 1 or value.class_id < 0 or w <= 0 or h <= 0
            or not 0 <= value.confidence <= 1
            or not all(math.isfinite(v) for v in (x, y, w, h, value.confidence))):
        raise TrackingRuntimeError("Detector returned invalid normalized detection")


class UltralyticsYOLODetector:
    """Ultralytics adapter; no Results/Boxes objects escape this class."""

    def __init__(self, model: str, classes: list[int], conf: float, iou: float,
                 imgsz: int, device: str | None):
        from ultralytics import YOLO
        self.model = YOLO(model)
        self.classes, self.conf, self.iou = list(classes), conf, iou
        self.imgsz, self.device = imgsz, device
        self.identity = {"implementation": "UltralyticsYOLODetector", "model": str(model),
                         "classes": self.classes, "conf": conf, "iou": iou,
                         "imgsz": imgsz, "device": device}

    def detect(self, image_path: Path, frame_id: int) -> list[Detection]:
        result = self.model.predict(source=str(image_path), conf=self.conf, iou=self.iou,
                                    imgsz=self.imgsz, classes=self.classes,
                                    device=self.device, verbose=False)[0]
        boxes = result.boxes
        if boxes is None:
            return []
        names = result.names
        output = []
        for xyxy, confidence, class_id in zip(boxes.xyxy.tolist(), boxes.conf.tolist(), boxes.cls.int().tolist()):
            x1, y1, x2, y2 = (float(value) for value in xyxy)
            class_id = int(class_id)
            class_name = names.get(class_id, class_id) if isinstance(names, dict) else names[class_id]
            value = Detection(frame_id, (x1, y1, x2 - x1, y2 - y1), float(confidence),
                              class_id, str(class_name))
            _valid_detection(value)
            output.append(value)
        return output


class _Batch:
    """Small Results-like container accepted by Ultralytics trackers."""
    def __init__(self, detections: Sequence[Detection]):
        import numpy as np
        self.xywh = np.asarray([[x + w / 2, y + h / 2, w, h]
                                for detection in detections for x, y, w, h in [detection.bbox]], dtype=np.float32)
        self.conf = np.asarray([x.confidence for x in detections], dtype=np.float32)
        self.cls = np.asarray([x.class_id for x in detections], dtype=np.float32)
        if not detections:
            self.xywh = np.empty((0, 4), dtype=np.float32)

    def __len__(self):
        return len(self.conf)

    def __getitem__(self, key):
        result = object.__new__(_Batch)
        result.xywh, result.conf, result.cls = self.xywh[key], self.conf[key], self.cls[key]
        if result.xywh.ndim == 1:
            result.xywh, result.conf, result.cls = result.xywh[None, :], result.conf[None], result.cls[None]
        return result


class ByteTrackTracker:
    """Ultralytics ByteTrack adapter consuming and returning normalized objects."""

    def __init__(self, config_path: str | Path):
        candidate = Path(config_path)
        if not candidate.is_file():
            import ultralytics
            candidate = Path(ultralytics.__file__).resolve().parent / "cfg" / "trackers" / str(config_path)
        if not candidate.is_file():
            raise TrackingRuntimeError(f"Tracker config not found: {config_path}")
        self.config_path = str(candidate.resolve())
        self.identity = {"implementation": "ByteTrackTracker", "config": self.config_path}
        self.reset()

    def reset(self) -> None:
        from ultralytics.trackers.byte_tracker import BYTETracker
        from ultralytics.utils import IterableSimpleNamespace, YAML
        settings = YAML.load(self.config_path)
        if settings.get("tracker_type") != "bytetrack":
            raise TrackingRuntimeError("ByteTrackTracker requires tracker_type=bytetrack")
        self._tracker = BYTETracker(IterableSimpleNamespace(**settings))
        self._global_ids: dict[tuple[int, int], int] = {}
        self._next_id = 1

    def update(self, detections: Sequence[Detection], frame_id: int) -> list[TrackBox]:
        for detection in detections:
            _valid_detection(detection)
            if detection.frame_id != frame_id:
                raise TrackingRuntimeError("Detection frame does not match tracker update frame")
        output = []
        names = {x.class_id: x.class_name for x in detections}
        rows = self._tracker.update(_Batch(detections))
        for row in rows.tolist() if len(rows) else []:
            x1, y1, x2, y2, native_id, score, class_id, _ = row
            class_id = int(class_id)
            key = (class_id, int(native_id))
            if key not in self._global_ids:
                self._global_ids[key] = self._next_id
                self._next_id += 1
            output.append(TrackBox(frame_id, self._global_ids[key],
                                   (float(x1), float(y1), float(x2-x1), float(y2-y1)),
                                   float(score), class_id, names.get(class_id, str(class_id))))
        return sorted(output, key=lambda x: (x.track_id, x.class_id))


def _json_detection(value: Detection) -> dict:
    result = asdict(value); result["bbox"] = list(value.bbox); return result


def _json_track(value: TrackBox) -> dict:
    result = asdict(value); result["bbox"] = list(value.bbox); return result


def _detections(values) -> list[Detection]:
    return [Detection(int(x["frame_id"]), tuple(float(v) for v in x["bbox"]),
                      float(x["confidence"]), int(x["class_id"]), str(x["class_name"])) for x in values]


def _tracks(values) -> list[TrackBox]:
    return [TrackBox(int(x["frame_id"]), int(x["track_id"]), tuple(float(v) for v in x["bbox"]),
                     float(x["confidence"]), int(x["class_id"]), str(x["class_name"])) for x in values]


def _save(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    temp.replace(path)


def _canonical(value) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def run_chunked(image_paths: list[Path], detector: Detector, tracker: Tracker,
                chunk_size: int, checkpoint_dir: Path, config_sha256: str,
                image_inventory_sha256: str) -> tuple[list[TrackBox], dict]:
    """Checkpoint detections/tracks per chunk; replay cached detections to restore tracker."""
    if chunk_size < 1:
        raise TrackingRuntimeError("chunk_size must be positive")
    checkpoint_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = checkpoint_dir / "manifest.json"
    expected = {"schema_version": 1, "config_sha256": config_sha256,
                "image_inventory_sha256": image_inventory_sha256,
                "frame_count": len(image_paths), "chunk_size": chunk_size}
    manifest = {**expected, "status": "running", "completed_chunks": []}
    if manifest_path.is_file():
        try:
            current = json.loads(manifest_path.read_text(encoding="utf-8-sig"))
        except (OSError, json.JSONDecodeError):
            raise TrackingRuntimeError("Corrupt inference checkpoint manifest") from None
        if any(current.get(key) != value for key, value in expected.items()):
            raise TrackingRuntimeError("Incompatible inference resume state")
        manifest = current
    listed = {int(x["index"]) for x in manifest.get("completed_chunks", [])}
    locked_chunks = {int(x["index"]): x for x in manifest.get("completed_chunks", [])}
    present = {int(path.stem.split("_")[-1]) for path in checkpoint_dir.glob("chunk_*.json")}
    if present != listed:
        raise TrackingRuntimeError("Orphan or missing chunk checkpoint; safe resume refused")
    tracker.reset()
    all_tracks: list[TrackBox] = []
    detector_calls = 0
    for chunk_index, start in enumerate(range(0, len(image_paths), chunk_size)):
        chunk_path = checkpoint_dir / f"chunk_{chunk_index:06d}.json"
        stop = min(start + chunk_size, len(image_paths))
        cached = None
        if chunk_index in listed:
            cached = json.loads(chunk_path.read_text(encoding="utf-8-sig"))
            if _canonical(cached) != locked_chunks[chunk_index].get("sha256"):
                raise TrackingRuntimeError("Chunk checkpoint hash mismatch")
            if cached.get("start_frame") != start + 1 or cached.get("end_frame") != stop:
                raise TrackingRuntimeError("Chunk frame range mismatch")
        chunk_detections, chunk_tracks = [], []
        cached_by_frame = {}
        if cached:
            for detection in _detections(cached.get("detections", [])):
                cached_by_frame.setdefault(detection.frame_id, []).append(detection)
        for offset in range(start, stop):
            frame_id = offset + 1
            if cached:
                detections = cached_by_frame.get(frame_id, [])
            else:
                detections = detector.detect(image_paths[offset], frame_id)
                detector_calls += 1
            for value in detections:
                _valid_detection(value)
            tracks = tracker.update(detections, frame_id)
            chunk_detections.extend(detections); chunk_tracks.extend(tracks)
        if cached:
            expected_tracks = _tracks(cached.get("tracks", []))
            if _canonical([_json_track(x) for x in chunk_tracks]) != _canonical([_json_track(x) for x in expected_tracks]):
                raise TrackingRuntimeError("Tracker replay differs from locked chunk output")
        else:
            payload = {"schema_version": 1, "index": chunk_index, "start_frame": start + 1,
                       "end_frame": stop, "detections": [_json_detection(x) for x in chunk_detections],
                       "tracks": [_json_track(x) for x in chunk_tracks]}
            _save(chunk_path, payload)
            manifest["completed_chunks"].append({"index": chunk_index, "start_frame": start + 1,
                                                  "end_frame": stop, "sha256": _canonical(payload)})
            _save(manifest_path, manifest)
        all_tracks.extend(chunk_tracks)
    detection_count = 0
    for item in manifest.get("completed_chunks", []):
        payload = json.loads((checkpoint_dir / f"chunk_{int(item['index']):06d}.json").read_text(encoding="utf-8-sig"))
        detection_count += len(payload.get("detections", []))
    manifest.update(status="complete", detector_frames_processed_this_run=detector_calls,
                    detection_count=detection_count, box_count=len(all_tracks),
                    track_count=len({x.track_id for x in all_tracks}))
    _save(manifest_path, manifest)
    return all_tracks, manifest
