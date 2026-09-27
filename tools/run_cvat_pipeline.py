#!/usr/bin/env python3
"""Run the existing tracking and Analyzer v2 workflow against one CVAT job.

The runner only appends predictions with CVAT's ``action=create`` endpoint. It
never clears or replaces annotations. MOT frames are local and 1-based; CVAT
frames are absolute task frames and 0-based.
"""
from __future__ import annotations

import argparse
from collections import defaultdict
import hashlib
import json
import math
from pathlib import Path
import statistics
import sys
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request

from cvat_integration import (Client, IntegrationError, digest, execute,
                              load_dotenv, parse_events, save, writer_lock)
from review_tracks_v2 import DEFAULT_V2, review_v2
from review_tracks import DEFAULT_CONFIG
from run_tracker import track_image_dir, write_mot
from workspace_lifecycle import (WorkspaceError, cleanup_frames, cleanup_run,
                                 workspace_status)


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MODEL = "yolo26n.pt"
DEFAULT_TRACKER = "bytetrack.yaml"
DEFAULT_CLASSES = [2, 5, 7]


class PipelineError(ValueError):
    pass


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def canonical_hash(value) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
                                     ensure_ascii=False).encode()).hexdigest()


def annotation_hash(data) -> str:
    return canonical_hash(data)


def annotation_counts(data) -> dict:
    if not isinstance(data, dict):
        raise PipelineError("Unexpected CVAT annotation response schema")
    tracks = data.get("tracks") or []
    if (not all(isinstance(data.get(key, []), list) for key in ("tags", "shapes", "tracks", "intervals"))
            or not all(isinstance(track, dict) and isinstance(track.get("shapes", []), list) for track in tracks)):
        raise PipelineError("Unexpected CVAT annotation response schema")
    return {
        "tags": len(data.get("tags") or []),
        "shapes": len(data.get("shapes") or []),
        "tracks": len(tracks),
        "track_shapes": sum(len(t.get("shapes") or []) for t in tracks),
        "intervals": len(data.get("intervals") or []),
    }


def annotation_is_empty(data) -> bool:
    c = annotation_counts(data)
    return c["tags"] == c["shapes"] == c["tracks"] == c["intervals"] == 0


class PipelineClient(Client):
    """Explicitly adds only frame download and append-only annotation creation."""

    def _open(self, request: Request, endpoint: str):
        try:
            return self.opener.open(request, timeout=30)
        except HTTPError as exc:
            raise PipelineError(f"HTTP {exc.code} endpoint={endpoint}") from None
        except (URLError, TimeoutError, OSError):
            raise PipelineError(f"Network failure endpoint={endpoint}") from None

    def frame_bytes(self, job_id: int, cvat_frame: int) -> bytes:
        endpoint = f"/api/jobs/{job_id}/data?{urlencode({'type':'frame','number':cvat_frame,'quality':'original'})}"
        request = Request(self.url + endpoint, headers={"Authorization": self.headers["Authorization"]})
        with self._open(request, endpoint) as response:
            return response.read()

    def create_annotations(self, job_id: int, payload: dict) -> dict:
        endpoint = f"/api/jobs/{job_id}/annotations?action=create"
        body = json.dumps(payload, separators=(",", ":")).encode()
        request = Request(self.url + endpoint, data=body, method="PATCH", headers=self.headers)
        with self._open(request, endpoint) as response:
            raw = response.read()
        try:
            return json.loads(raw) if raw else {}
        except json.JSONDecodeError:
            raise PipelineError(f"Unexpected response schema endpoint={endpoint}") from None


def fetch_live_snapshot(client, task_id: int, job_id: int) -> dict:
    task = client.request("GET", f"/api/tasks/{task_id}")
    job = client.request("GET", f"/api/jobs/{job_id}")
    meta = client.request("GET", f"/api/jobs/{job_id}/data/meta")
    annotations = client.request("GET", f"/api/jobs/{job_id}/annotations")
    raw_labels = client.request("GET", f"/api/labels?task_id={task_id}")
    labels = raw_labels.get("results", raw_labels) if isinstance(raw_labels, dict) else raw_labels
    if (not all(isinstance(x, dict) for x in (task, job, meta, annotations))
            or not isinstance(labels, list) or not all(isinstance(x, dict) for x in labels)):
        raise PipelineError("Unexpected CVAT metadata response schema")
    snapshot = {"task": task, "job": job, "meta": meta, "labels": labels,
                "annotation_summary": annotation_counts(annotations),
                "annotation_hash": annotation_hash(annotations)}
    validate_target(snapshot, task_id, job_id)
    return snapshot, annotations


def validate_target(snapshot: dict, task_id: int, job_id: int) -> list[dict]:
    task, job, meta = snapshot["task"], snapshot["job"], snapshot["meta"]
    if task.get("id") != task_id or job.get("id") != job_id or job.get("task_id") != task_id:
        raise PipelineError("Task/job mismatch")
    if task.get("dimension") != "2d" or job.get("dimension") != "2d" or job.get("type") != "annotation":
        raise PipelineError("Only 2D annotation jobs are supported")
    start, stop = job.get("start_frame"), job.get("stop_frame")
    if type(start) is not int or type(stop) is not int or start < 0 or stop < start:
        raise PipelineError("Unexpected job frame range")
    count = stop - start + 1
    if job.get("frame_count") not in (None, count):
        raise PipelineError("Job frame count does not match its frame range")
    if meta.get("frame_filter", "") not in ("", "step=1") or meta.get("deleted_frames"):
        raise PipelineError("Sampled/deleted frames are unsupported")
    if meta.get("included_frames"):
        raise PipelineError("Explicit included-frame tasks are unsupported")
    frames = meta.get("frames")
    if not isinstance(frames, list) or len(frames) <= stop:
        raise PipelineError("CVAT did not return complete frame metadata")
    selected = frames[start:stop + 1]
    if len(selected) != count or any(not f.get("name") or not f.get("width") or not f.get("height") for f in selected):
        raise PipelineError("Incomplete frame names/dimensions")
    return [{"mot_frame": i + 1, "cvat_frame": start + i,
             "remote_name": str(f["name"]), "local_name": f"{i+1:06d}.jpg",
             "width": f["width"], "height": f["height"]}
            for i, f in enumerate(selected)]


def target_fingerprint(snapshot: dict) -> str:
    task, job, meta = snapshot["task"], snapshot["job"], snapshot["meta"]
    keep = {
        "task": {k: task.get(k) for k in ("id", "size", "dimension", "mode", "project_id", "subset", "organization")},
        "job": {k: job.get(k) for k in ("id", "task_id", "start_frame", "stop_frame", "frame_count", "type", "dimension")},
        "meta": {"size": meta.get("size"), "start_frame": meta.get("start_frame"),
                 "stop_frame": meta.get("stop_frame"), "frame_filter": meta.get("frame_filter"),
                 "deleted_frames": meta.get("deleted_frames"), "included_frames": meta.get("included_frames"),
                 "frames": [{k: f.get(k) for k in ("name", "width", "height")} for f in meta.get("frames", [])]},
        "labels": [{"id": x.get("id"), "name": x.get("name"), "type": x.get("type"),
                    "attributes": x.get("attributes", [])} for x in snapshot["labels"]],
    }
    return canonical_hash(keep)


def select_label(snapshot: dict, name: str) -> dict:
    labels = [x for x in snapshot["labels"] if x.get("name") == name and x.get("type") == "rectangle"]
    if len(labels) != 1:
        raise PipelineError(f"Require exactly one rectangle label named {name!r}")
    return labels[0]


def write_metadata(workspace: Path, snapshot: dict, mapping: list[dict]) -> None:
    task, job = snapshot["task"], snapshot["job"]
    public = {
        "schema_version": 1,
        "task": {k: task.get(k) for k in ("id", "name", "size", "dimension", "mode", "project_id", "subset", "organization")},
        "job": {k: job.get(k) for k in ("id", "task_id", "start_frame", "stop_frame", "frame_count", "type", "dimension", "status")},
        "frames": mapping,
        "labels": [{"id": x.get("id"), "name": x.get("name"), "type": x.get("type"),
                    "attributes": [a.get("name") for a in x.get("attributes", [])]} for x in snapshot["labels"]],
        "annotation_summary": snapshot["annotation_summary"],
        "annotation_hash": snapshot["annotation_hash"],
        "target_sha256": target_fingerprint(snapshot),
    }
    path = workspace / "metadata.json"
    if path.is_file():
        existing = json.loads(path.read_text(encoding="utf-8-sig"))
        if existing.get("target_sha256") != public["target_sha256"]:
            raise PipelineError("Live task/frame/label metadata differs from locked workspace")
        # Preserve the initial lock; a later read-only check must not rewrite history.
        save(workspace / "metadata_latest.json", public)
    else:
        save(path, public)


def validate_image(path: Path, width: int, height: int) -> None:
    from PIL import Image
    try:
        with Image.open(path) as image:
            image.load()
            if image.size != (width, height):
                raise PipelineError(f"Downloaded frame dimension mismatch: {path.name}")
    except PipelineError:
        raise
    except Exception:
        raise PipelineError(f"Downloaded frame is not a valid image: {path.name}") from None


def ensure_frames(client, workspace: Path, snapshot: dict, mapping: list[dict]) -> dict:
    folder = workspace / "frames"
    manifest_path = folder / "manifest.json"
    expected_target = target_fingerprint(snapshot)
    manifest = None
    if manifest_path.is_file():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8-sig"))
        if manifest.get("target_sha256") != expected_target or not isinstance(manifest.get("frames"), list):
            raise PipelineError("Existing frame manifest does not match CVAT source")
        if manifest.get("status") == "cleaned":
            if list(folder.glob("*.jpg")):
                raise PipelineError("Cleaned frame manifest conflicts with cached images")
            manifest = {"target_sha256": expected_target, "frames": []}
        else:
            for item in manifest["frames"]:
                path = folder / item["local_name"]
                if not path.is_file() or sha256_file(path) != item["sha256"]:
                    raise PipelineError("Cached frame is missing or corrupt")
            if manifest.get("status") == "complete" and len(manifest["frames"]) == len(mapping):
                return manifest
    elif folder.exists() and any(folder.iterdir()):
        raise PipelineError("Frames exist without a valid manifest; refuse ambiguous resume")
    folder.mkdir(parents=True, exist_ok=True)
    items = list((manifest or {}).get("frames", []))
    completed = {x["local_name"] for x in items}
    for item in mapping:
        if item["local_name"] in completed:
            continue
        path = folder / item["local_name"]
        temp = path.with_suffix(".tmp")
        try:
            temp.write_bytes(client.frame_bytes(snapshot["job"]["id"], item["cvat_frame"]))
            validate_image(temp, item["width"], item["height"])
            temp.replace(path)
        finally:
            if temp.exists():
                temp.unlink()
        items.append(dict(item, sha256=sha256_file(path), byte_size=path.stat().st_size))
        # Checkpoint each frame so a network/process failure resumes at the next one.
        save(manifest_path, {"schema_version": 1, "status": "downloading",
                            "target_sha256": expected_target, "frames": items})
    manifest = {"schema_version": 1, "status": "complete", "target_sha256": expected_target, "frames": items,
                "inventory_sha256": canonical_hash(items)}
    save(manifest_path, manifest)
    return manifest


def resolve_model(path_or_name: str) -> Path:
    candidate = Path(path_or_name)
    if not candidate.is_absolute():
        candidate = ROOT / candidate
    if not candidate.is_file():
        raise PipelineError(f"Model file not found locally: {path_or_name}")
    return candidate.resolve()


def resolve_tracker(path_or_name: str) -> Path:
    candidate = Path(path_or_name)
    if not candidate.is_absolute():
        local = ROOT / candidate
        if local.is_file():
            candidate = local
        else:
            try:
                import ultralytics
                candidate = Path(ultralytics.__file__).resolve().parent / "cfg" / "trackers" / path_or_name
            except Exception:
                pass
    if not candidate.is_file():
        raise PipelineError(f"Tracker config not found: {path_or_name}")
    return candidate.resolve()


def tracking_config(args) -> dict:
    model = resolve_model(args.model)
    tracker = resolve_tracker(args.tracker)
    return {"model": str(model), "model_sha256": sha256_file(model),
            "tracker_argument": args.tracker, "tracker_file": str(tracker),
            "tracker_sha256": sha256_file(tracker), "conf": args.conf, "iou": args.iou,
            "imgsz": args.imgsz, "classes": args.classes, "device": args.device,
            "runner_sha256": sha256_file(Path(__file__).with_name("run_tracker.py"))}


def read_mot_rows(path: Path) -> list[tuple[int, int, float, float, float, float, float]]:
    rows = []
    seen = set()
    for number, raw in enumerate(Path(path).read_text(encoding="utf-8-sig").splitlines(), 1):
        if not raw.strip():
            continue
        parts = raw.split(",")
        if len(parts) < 7:
            raise PipelineError(f"Malformed MOT row {number}")
        try:
            row = (int(parts[0]), int(parts[1]), *(float(x) for x in parts[2:7]))
        except ValueError:
            raise PipelineError(f"Malformed MOT row {number}") from None
        if (row[0] < 1 or row[1] < 0 or row[4] <= 0 or row[5] <= 0
                or not all(math.isfinite(x) for x in row[2:]) or not 0 <= row[6] <= 1
                or (row[0], row[1]) in seen):
            raise PipelineError(f"Invalid MOT value row {number}")
        seen.add((row[0], row[1]))
        rows.append(row)
    return sorted(rows)


def ensure_predictions(workspace: Path, snapshot: dict, frames_manifest: dict, args,
                       tracker_fn=track_image_dir) -> tuple[Path, dict]:
    folder, mot_folder = workspace / "predictions", workspace / "mot"
    manifest_path, mot_path = folder / "manifest.json", mot_folder / "predictions.txt"
    config = tracking_config(args)
    expected = {"target_sha256": target_fingerprint(snapshot),
                "frame_inventory_sha256": frames_manifest["inventory_sha256"],
                "tracking_config_sha256": canonical_hash(config)}
    if manifest_path.is_file():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8-sig"))
        if any(manifest.get(k) != v for k, v in expected.items()):
            raise PipelineError("Existing prediction artifact does not match locked inputs")
        if manifest.get("status") == "complete" and mot_path.is_file() and sha256_file(mot_path) == manifest.get("mot_sha256"):
            return mot_path, manifest
        if manifest.get("status") != "running" or mot_path.exists():
            raise PipelineError("Incomplete prediction artifact cannot be resumed safely")
    if mot_path.exists() or (folder.exists() and any(folder.iterdir())):
        if not manifest_path.is_file():
            raise PipelineError("Prediction artifact exists without a valid manifest")
    folder.mkdir(parents=True, exist_ok=True); mot_folder.mkdir(parents=True, exist_ok=True)
    save(manifest_path, {"schema_version": 1, "status": "running", **expected,
                         "tracking_config": config})
    rows = tracker_fn(workspace / "frames", config["model"], args.tracker, args.conf,
                      args.iou, args.imgsz, args.classes, args.device, True)
    temp = mot_path.with_suffix(".tmp")
    write_mot(rows, temp); temp.replace(mot_path)
    manifest = {"schema_version": 1, "status": "complete", **expected, "tracking_config": config,
                "mot_sha256": sha256_file(mot_path), "box_count": len(rows),
                "track_count": len({r[1] for r in rows})}
    save(manifest_path, manifest)
    return mot_path, manifest


def cvat_track_payloads(rows, mapping: list[dict], label_id: int) -> list[dict]:
    frame_map = {x["mot_frame"]: x for x in mapping}
    grouped = defaultdict(list)
    for row in rows:
        if row[0] not in frame_map:
            raise PipelineError(f"Prediction frame {row[0]} is out of job bounds")
        grouped[row[1]].append(row)
    payloads = []
    last_local = len(mapping)
    for external_id, detections in sorted(grouped.items()):
        detections.sort()
        shapes, previous = [], None
        for frame, _, x, y, w, h, confidence in detections:
            if previous is not None and frame != previous[0] + 1:
                pf, px, py, pw, ph = previous[:5]
                outside_local = pf + 1
                shapes.append({"type": "rectangle", "frame": frame_map[outside_local]["cvat_frame"],
                               "points": [px, py, px + pw, py + ph], "outside": True,
                               "occluded": False, "z_order": 0, "rotation": 0, "attributes": []})
            shapes.append({"type": "rectangle", "frame": frame_map[frame]["cvat_frame"],
                           "points": [x, y, x + w, y + h], "outside": False,
                           "occluded": False, "z_order": 0, "rotation": 0, "attributes": []})
            previous = (frame, x, y, w, h, confidence)
        if previous and previous[0] < last_local:
            pf, px, py, pw, ph = previous[:5]
            shapes.append({"type": "rectangle", "frame": frame_map[pf + 1]["cvat_frame"],
                           "points": [px, py, px + pw, py + ph], "outside": True,
                           "occluded": False, "z_order": 0, "rotation": 0, "attributes": []})
        payloads.append({"external_track_id": external_id,
                         "confidence": {"min": min(x[6] for x in detections),
                                        "max": max(x[6] for x in detections)},
                         "track": {"label_id": label_id, "frame": shapes[0]["frame"], "group": 0,
                                   "source": "auto", "attributes": [], "shapes": shapes, "elements": []}})
    return payloads


def track_signature(track: dict) -> str:
    shapes = []
    for shape in track.get("shapes", []):
        shapes.append({"type": shape.get("type"), "frame": shape.get("frame"),
                       "outside": bool(shape.get("outside")), "occluded": bool(shape.get("occluded")),
                       "points": [round(float(x), 2) for x in shape.get("points", [])]})
    value = {"label_id": track.get("label_id"), "frame": track.get("frame"),
             "source": track.get("source", "manual"), "shapes": shapes}
    return canonical_hash(value)


def reconcile_prediction_tracks(expected: list[dict], remote: dict) -> dict:
    remote_by_signature = defaultdict(list)
    for track in remote.get("tracks") or []:
        remote_by_signature[track_signature(track)].append(track)
    mapping, missing = {}, []
    for item in expected:
        signature = track_signature(item["track"])
        matches = remote_by_signature.get(signature, [])
        if len(matches) > 1:
            raise PipelineError("Duplicate matching CVAT tracks make external-ID mapping ambiguous")
        if matches:
            mapping[str(item["external_track_id"])] = matches[0].get("id")
        else:
            missing.append(item)
    return {"external_to_cvat_track": mapping, "missing": missing,
            "matched": len(mapping), "expected": len(expected)}


def shape_count_audit(rows, expected: list[dict], remote: dict, total_frames: int) -> dict:
    grouped = defaultdict(list)
    for row in rows:
        grouped[row[1]].append(row[0])
    gap_boundaries = sum(sum(b > a + 1 for a, b in zip(sorted(frames), sorted(frames)[1:]))
                         for frames in grouped.values())
    terminal_boundaries = sum(max(frames) < total_frames for frames in grouped.values() if frames)
    expected_shapes = [shape for item in expected for shape in item["track"]["shapes"]]
    remote_shapes = [shape for track in remote.get("tracks", []) for shape in track.get("shapes", [])]
    result = {
        "mot_boxes": len(rows),
        "expected_visible_keyframes": sum(not shape.get("outside", False) for shape in expected_shapes),
        "generated_outside_keyframes": sum(bool(shape.get("outside")) for shape in expected_shapes),
        "gap_boundary_outside_keyframes": gap_boundaries,
        "terminal_outside_keyframes": terminal_boundaries,
        "expected_total_track_shapes": len(expected_shapes),
        "remote_visible_keyframes": sum(not shape.get("outside", False) for shape in remote_shapes),
        "remote_outside_keyframes": sum(bool(shape.get("outside")) for shape in remote_shapes),
        "remote_total_track_shapes": len(remote_shapes),
        "all_expected_track_signatures_present": not reconcile_prediction_tracks(expected, remote)["missing"],
    }
    result["classification"] = ("EXPECTED" if result["mot_boxes"] == result["expected_visible_keyframes"] == result["remote_visible_keyframes"]
                                and result["generated_outside_keyframes"] == gap_boundaries + terminal_boundaries
                                and result["expected_total_track_shapes"] == result["remote_total_track_shapes"]
                                and result["all_expected_track_signatures_present"] else "BUG_OR_DRIFT")
    return result


def push_predictions(client, workspace: Path, snapshot: dict, annotations: dict,
                     mot_path: Path, mapping: list[dict], label: dict,
                     allow_existing: bool) -> dict:
    folder = workspace / "cvat_push"; folder.mkdir(parents=True, exist_ok=True)
    state_path = folder / "predictions.json"
    rows = read_mot_rows(mot_path)
    expected = cvat_track_payloads(rows, mapping, label["id"])
    source = {"target_sha256": target_fingerprint(snapshot), "mot_sha256": sha256_file(mot_path),
              "label_id": label["id"], "expected_sha256": canonical_hash(expected)}
    prior = json.loads(state_path.read_text(encoding="utf-8-sig")) if state_path.is_file() else None
    if prior and any(prior.get(k) != v for k, v in source.items()):
        raise PipelineError("Prediction push state belongs to different inputs")
    reconciliation = reconcile_prediction_tracks(expected, annotations)
    if not annotation_is_empty(annotations) and prior is None and not allow_existing:
        raise PipelineError("CVAT job already has annotations; pass --allow-existing-annotations to append explicitly")
    if reconciliation["matched"] and prior is None and not allow_existing:
        raise PipelineError("Remote predictions exist without local state; explicit allow is required")
    prepared = {"schema_version": 1, **source, "status": "prepared",
                "annotation_hash_before": prior.get("annotation_hash_before") if prior else annotation_hash(annotations),
                "annotation_count_before": prior.get("annotation_count_before") if prior else annotation_counts(annotations)}
    save(state_path, prepared)
    if reconciliation["missing"]:
        payload = {"version": annotations.get("version", 0), "tags": [], "shapes": [],
                   "tracks": [x["track"] for x in reconciliation["missing"]]}
        client.create_annotations(snapshot["job"]["id"], payload)
    after = client.request("GET", f"/api/jobs/{snapshot['job']['id']}/annotations")
    verified = reconcile_prediction_tracks(expected, after)
    if verified["missing"]:
        raise PipelineError("Prediction read-back verification failed")
    result = {**prepared, "status": "verified", "created_tracks": len(reconciliation["missing"]),
              "skipped_tracks": reconciliation["matched"], "external_to_cvat_track": verified["external_to_cvat_track"],
              "annotation_hash_after": annotation_hash(after), "annotation_count_after": annotation_counts(after),
              "confidence_preservation": "MOT_ONLY_NO_CVAT_LABEL_ATTRIBUTE"}
    save(state_path, result)
    return result


def ensure_review(workspace: Path, snapshot: dict, mot_path: Path) -> tuple[dict, dict]:
    manifest_path = workspace / "predictions" / "review_manifest.json"
    events_path = workspace / "review_events.json"
    expected = {"mot_sha256": sha256_file(mot_path),
                "v1_config_sha256": sha256_file(DEFAULT_CONFIG),
                "v2_config_sha256": sha256_file(DEFAULT_V2),
                "analyzer_sha256": sha256_file(Path(__file__).with_name("review_tracks_v2.py")),
                "total_frames": snapshot["job"]["stop_frame"] - snapshot["job"]["start_frame"] + 1}
    if manifest_path.is_file():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8-sig"))
        if any(manifest.get(k) != v for k, v in expected.items()) or not events_path.is_file() or sha256_file(events_path) != manifest.get("events_sha256"):
            raise PipelineError("Existing analyzer artifact does not match locked inputs")
        return json.loads(events_path.read_text(encoding="utf-8-sig")), manifest
    if events_path.exists():
        raise PipelineError("Review events exist without a valid manifest")
    result = review_v2(mot_path, DEFAULT_CONFIG, DEFAULT_V2, workspace, expected["total_frames"])
    events = json.loads(events_path.read_text(encoding="utf-8-sig"))
    manifest = {"schema_version": 1, **expected, "events_sha256": sha256_file(events_path),
                "raw_flag_count": len(result["flags"]), "event_count": len(result["events"])}
    save(manifest_path, manifest)
    return events, manifest


def _issue_placement(event: dict, rows, mapping: list[dict], prediction_state: dict | None) -> dict:
    frame_map = {x["mot_frame"]: x for x in mapping}
    external_id = event["track_id"]
    cvat_id = (prediction_state or {}).get("external_to_cvat_track", {}).get(str(external_id))
    if cvat_id is None:
        anchor = frame_map[event["anchor_frame"]]
        return {"mode": "FRAME_LEVEL_FALLBACK_UNMAPPED_TRACK", "mot_frame": event["anchor_frame"],
                "cvat_frame": anchor["cvat_frame"], "position": [10, 10], "bbox": None,
                "confidence": None, "cvat_track_id": None}
    candidates = [r for r in (rows or []) if r[1] == external_id]
    if not candidates:
        anchor = frame_map[event["anchor_frame"]]
        return {"mode": "FRAME_LEVEL_FALLBACK_NO_BBOX", "mot_frame": event["anchor_frame"],
                "cvat_frame": anchor["cvat_frame"], "position": [10, 10], "bbox": None,
                "confidence": None, "cvat_track_id": cvat_id}
    chosen = min(candidates, key=lambda r: (abs(r[0] - event["anchor_frame"]), r[0]))
    frame, _, x, y, width, height, confidence = chosen
    target = frame_map.get(frame)
    values = (x, y, width, height, confidence)
    if (target is None or not all(math.isfinite(v) for v in values) or width <= 0 or height <= 0
            or x < 0 or y < 0 or x + width > target["width"] + .01 or y + height > target["height"] + .01):
        raise PipelineError(f"Invalid/out-of-range marker geometry for external track {external_id}")
    center = [round(x + width / 2, 2), round(y + height / 2, 2)]
    return {"mode": "ANCHOR_BBOX_CENTER" if frame == event["anchor_frame"] else "NEAREST_BBOX_CENTER",
            "mot_frame": frame, "cvat_frame": target["cvat_frame"], "position": center,
            "bbox": [x, y, width, height], "confidence": confidence, "cvat_track_id": cvat_id}


def issue_plan(events_data: dict, snapshot: dict, mapping: list[dict], base_url: str,
               rows=None, prediction_state: dict | None = None) -> dict:
    events = parse_events(events_data)
    frame_map = {x["mot_frame"]: x for x in mapping}
    task_id, job_id = snapshot["task"]["id"], snapshot["job"]["id"]
    sequence = f"task_{task_id}_job_{job_id}"
    items = []
    for event in events:
        if event["context_end"] not in frame_map:
            raise PipelineError(f"Out-of-range event {event['event_id']}")
        cv = {key: frame_map[event[key]]["cvat_frame"] for key in
              ("anchor_frame", "start_frame", "end_frame", "context_start", "context_end")}
        marker = f"SATV2|{sequence}|{event['event_id']}"
        placement = _issue_placement(event, rows, mapping, prediction_state)
        track_rows = [r for r in (rows or []) if r[1] == event["track_id"]]
        confidences = [r[6] for r in track_rows]
        metadata = {"event": event, "analyzer_version": "2", "event_source_sha256": digest(events_data),
                    "external_track_id": event["track_id"], "cvat_track_id": placement["cvat_track_id"],
                    "object_mapping": "MAPPED_BY_VERIFIED_TRACK_SIGNATURE" if placement["cvat_track_id"] is not None else "UNAVAILABLE",
                    "cvat_frames": cv, "placement": placement,
                    "track_confidence": ({"min": min(confidences), "median": statistics.median(confidences),
                                          "max": max(confidences)} if confidences else None),
                    "experimental": "possible_duplicate" in event["reasons"]}
        readable = [marker, f"event_id={event['event_id']}", f"reasons={','.join(event['reasons'])}",
                    f"cvat_track_id={placement['cvat_track_id']}", f"external_track_id={event['track_id']}",
                    f"related_external_track_ids={','.join(str(x) for x in event['related_track_ids']) or 'none'}",
                    f"anchor_frame_mot={event['anchor_frame']}",
                    f"context_mot={event['context_start']}..{event['context_end']}",
                    "analyzer_version=2", f"experimental={str(metadata['experimental']).lower()}",
                    f"marker={placement['mode']} mot_frame={placement['mot_frame']} cvat_frame={placement['cvat_frame']}",
                    "METADATA_JSON=" + json.dumps(metadata, sort_keys=True, ensure_ascii=False)]
        message = "\n".join(readable)
        items.append({"event_id": event["event_id"], "marker": marker,
                      "payload": {"job": job_id, "frame": placement["cvat_frame"],
                                  "position": placement["position"], "message": message},
                      "metadata": metadata, "links": {k: f"{base_url}/tasks/{task_id}/jobs/{job_id}?frame={v}" for k, v in cv.items()}})
    return {"schema_version": 1, "human_review_status": "PREPARED_NOT_EXECUTED",
            "task_id": task_id, "job_id": job_id, "sequence": sequence, "url": base_url,
            "source_sha256": digest(events_data), "snapshot_status": "LIVE_VERIFIED",
            "image_inventory_sha256": canonical_hash(mapping), "frame_mapping": mapping,
            "items": items, "validation_errors": [], "event_count": len(items)}


def push_issues(client, workspace: Path, plan: dict) -> dict:
    folder = workspace / "cvat_push"; folder.mkdir(parents=True, exist_ok=True)
    plan_path, state_path = folder / "issues_plan.json", folder / "issues_state.json"
    if plan_path.is_file() and canonical_hash(json.loads(plan_path.read_text(encoding="utf-8-sig"))) != canonical_hash(plan):
        raise PipelineError("Existing issue plan differs from current Analyzer output")
    save(plan_path, plan)
    prior = None
    if state_path.is_file():
        prior = json.loads(state_path.read_text(encoding="utf-8-sig")).get("event_issue_map")
    result = execute(client, plan, "push", prior,
                     checkpoint=lambda value: save(state_path, {"status": "partial", "event_issue_map": value}))
    result["created"] = sum(a["action"] == "CREATE" for a in result["actions"])
    result["skipped"] = sum(a["action"] == "SKIP_EXISTING" for a in result["actions"])
    save(state_path, result)
    return result


def local_artifact_summary(workspace: Path) -> dict:
    result = {"predicted_boxes": None, "predicted_tracks": None, "review_flags": None,
              "review_events": None}
    pred = workspace / "predictions" / "manifest.json"
    review = workspace / "predictions" / "review_manifest.json"
    if pred.is_file():
        value = json.loads(pred.read_text(encoding="utf-8-sig"))
        result.update(predicted_boxes=value.get("box_count"), predicted_tracks=value.get("track_count"))
    if review.is_file():
        value = json.loads(review.read_text(encoding="utf-8-sig"))
        result.update(review_flags=value.get("raw_flag_count"), review_events=value.get("event_count"))
    return result


def run(args, client=None, tracker_fn=track_image_dir) -> dict:
    workspace = Path(args.output_root) / f"task_{args.task_id}_job_{args.job_id}"
    workspace.mkdir(parents=True, exist_ok=True)
    client = client or PipelineClient()
    snapshot, annotations = fetch_live_snapshot(client, args.task_id, args.job_id)
    mapping = validate_target(snapshot, args.task_id, args.job_id)
    label = select_label(snapshot, args.label_name)
    write_metadata(workspace, snapshot, mapping)
    state_path = workspace / "cvat_push" / "predictions.json"
    prior_push = json.loads(state_path.read_text(encoding="utf-8-sig")) if state_path.is_file() else None
    annotations_changed = bool(prior_push and prior_push.get("status") == "verified"
                               and annotation_hash(annotations) != prior_push.get("annotation_hash_after"))
    config = tracking_config(args)
    if args.dry_run:
        local = local_artifact_summary(workspace)
        existing_without_state = not annotation_is_empty(annotations) and prior_push is None
        result = {"status": "DRY_RUN", "mutated_cvat": False, "task_id": args.task_id,
                  "job_id": args.job_id, "stage": args.stage, "frame_count": len(mapping),
                  "frame_range": [mapping[0]["cvat_frame"], mapping[-1]["cvat_frame"]],
                  "task": {k: snapshot["task"].get(k) for k in ("id", "name", "dimension", "mode", "size")},
                  "job": {k: snapshot["job"].get(k) for k in ("id", "task_id", "type", "dimension", "start_frame", "stop_frame")},
                  "annotation_summary": annotation_counts(annotations),
                  "labels": [{"id": x.get("id"), "name": x.get("name"), "type": x.get("type")} for x in snapshot["labels"]],
                  "selected_label": {"id": label["id"], "name": label["name"]},
                  "tracking_config": config, **local,
                  "annotation_push_method": "PATCH job annotations action=create (append only)",
                  "planned_annotation_tracks": local["predicted_tracks"],
                  "planned_review_issues": local["review_events"],
                  "annotation_safety": ("CVAT_ANNOTATION_STATE_CHANGED_SINCE_PREDICTION_PUSH" if annotations_changed else
                                        "WOULD_ABORT_EXISTING_ANNOTATIONS" if existing_without_state and not args.allow_existing_annotations
                                        else "PASS"),
                  "note": "Unknown counts require a real local inference run; dry-run never downloads frames or runs the model."}
        summary_path = workspace / "run_summary.json"
        if summary_path.is_file() and json.loads(summary_path.read_text(encoding="utf-8-sig")).get("status") == "COMPLETE":
            save(workspace / "dry_run_summary.json", result)
        else:
            save(summary_path, result)
        return result
    if annotations_changed:
        raise PipelineError("CVAT annotation state changed since prediction push")
    if args.stage in ("annotate", "all") and not annotation_is_empty(annotations):
        state = workspace / "cvat_push" / "predictions.json"
        if not state.is_file() and not args.allow_existing_annotations:
            raise PipelineError("CVAT job is not empty; no annotation was changed")
    (workspace / "cvat_push").mkdir(parents=True, exist_ok=True)
    with writer_lock(workspace / "cvat_push"):
        mot_path = workspace / "mot" / "predictions.txt"
        if args.stage in ("annotate", "all"):
            frames_manifest = ensure_frames(client, workspace, snapshot, mapping)
            mot_path, predictions = ensure_predictions(workspace, snapshot, frames_manifest, args, tracker_fn)
            latest = client.request("GET", f"/api/jobs/{args.job_id}/annotations")
            prediction_push = push_predictions(client, workspace, snapshot, latest, mot_path, mapping,
                                                label, args.allow_existing_annotations)
        else:
            manifest = workspace / "predictions" / "manifest.json"
            push_state = workspace / "cvat_push" / "predictions.json"
            if not mot_path.is_file() or not manifest.is_file() or not push_state.is_file():
                raise PipelineError("Review stage requires a verified completed annotation stage")
            predictions = json.loads(manifest.read_text(encoding="utf-8-sig"))
            prediction_push = json.loads(push_state.read_text(encoding="utf-8-sig"))
            if prediction_push.get("status") != "verified" or prediction_push.get("mot_sha256") != sha256_file(mot_path):
                raise PipelineError("Prediction push state is stale or incomplete")
        issues = None; review_manifest = None
        if args.stage in ("review", "all"):
            events, review_manifest = ensure_review(workspace, snapshot, mot_path)
            plan = issue_plan(events, snapshot, mapping, client.url, read_mot_rows(mot_path), prediction_push)
            issues = push_issues(client, workspace, plan)
        result = {"status": "COMPLETE", "mutated_cvat": True, "task_id": args.task_id,
                  "job_id": args.job_id, "stage": args.stage, "frame_count": len(mapping),
                  "predicted_boxes": predictions["box_count"], "predicted_tracks": predictions["track_count"],
                  "annotation_push": prediction_push,
                  "review_flags": review_manifest.get("raw_flag_count") if review_manifest else None,
                  "review_events": review_manifest.get("event_count") if review_manifest else None,
                  "issue_push": {k: issues.get(k) for k in ("created", "skipped", "verified", "annotations_unchanged")} if issues else None}
        save(workspace / "run_summary.json", result)
        return result


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--task-id", required=True, type=int)
    p.add_argument("--job-id", required=True, type=int)
    p.add_argument("--stage", choices=("annotate", "review", "all"), default="all")
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--allow-existing-annotations", action="store_true")
    p.add_argument("--label-name", default="vehicle")
    p.add_argument("--model", default=DEFAULT_MODEL)
    p.add_argument("--tracker", default=DEFAULT_TRACKER)
    p.add_argument("--conf", type=float, default=0.25)
    p.add_argument("--iou", type=float, default=0.7)
    p.add_argument("--imgsz", type=int, default=960)
    p.add_argument("--classes", type=lambda x: [int(v) for v in x.split(",") if v.strip()], default=DEFAULT_CLASSES)
    p.add_argument("--device", default=None)
    p.add_argument("--output-root", type=Path, default=ROOT / "outputs" / "runs")
    actions = p.add_mutually_exclusive_group()
    actions.add_argument("--workspace-status", action="store_true")
    actions.add_argument("--cleanup-frames", action="store_true")
    actions.add_argument("--cleanup-run", action="store_true")
    p.add_argument("--confirm-cleanup-run", metavar="WORKSPACE_NAME")
    return p


def main(argv=None) -> int:
    load_dotenv()
    args = parser().parse_args(argv)
    if args.task_id < 1 or args.job_id < 1:
        parser().error("task/job IDs must be positive")
    try:
        workspace = Path(args.output_root) / f"task_{args.task_id}_job_{args.job_id}"
        if args.confirm_cleanup_run and not args.cleanup_run:
            raise PipelineError("--confirm-cleanup-run requires --cleanup-run")
        if args.workspace_status:
            result = workspace_status(workspace)
        elif args.cleanup_frames:
            result = cleanup_frames(workspace)
        elif args.cleanup_run:
            result = cleanup_run(workspace, args.confirm_cleanup_run)
        else:
            result = run(args)
    except (PipelineError, IntegrationError, WorkspaceError, OSError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
