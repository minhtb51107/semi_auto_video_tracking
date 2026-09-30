"""Deterministic random QA, read-only final validation, and release decisions."""
from __future__ import annotations

import hashlib
import json
import math
import random
from collections import Counter, defaultdict

from review_priority import SEVERITIES


def deterministic_qa_samples(events_data, rows, mapping, count, seed, task_id, job_id, annotation_sha256):
    if type(count) is not int or count < 0 or type(seed) is not int:
        raise ValueError("Invalid QA sample count/seed")
    events = events_data.get("events", [])
    excluded = set()
    for event in events:
        excluded.update(range(int(event["context_start"]), int(event["context_end"]) + 1))
    frame_map = {int(x["mot_frame"]): x for x in mapping}
    candidates = sorted(set(frame_map) - excluded)
    material = f"{task_id}:{job_id}:{annotation_sha256}:{seed}:{count}"
    derived_seed = int(hashlib.sha256(material.encode()).hexdigest(), 16)
    selected = sorted(random.Random(derived_seed).sample(candidates, min(count, len(candidates))))
    by_frame = defaultdict(list)
    for row in rows or []:
        value = row.legacy() if hasattr(row, "legacy") else row
        by_frame[int(value[0])].append(value)
    samples = []
    for index, frame in enumerate(selected, 1):
        boxes = sorted(by_frame.get(frame, []), key=lambda x: (-float(x[6]), int(x[1])))
        anchor = None
        nearby = sorted({int(x[1]) for x in boxes})
        if boxes:
            _, track_id, x, y, width, height, confidence = boxes[0]
            dims = frame_map[frame]
            x1, y1 = max(0.0, float(x)), max(0.0, float(y))
            x2 = min(float(dims["width"]), float(x) + float(width))
            y2 = min(float(dims["height"]), float(y) + float(height))
            if x2 > x1 and y2 > y1:
                anchor = {"external_track_id": int(track_id), "bbox": [float(x), float(y), float(width), float(height)],
                          "position": [round((x1+x2)/2, 2), round((y1+y2)/2, 2)],
                          "confidence": float(confidence)}
        samples.append({"sample_id": f"Q{index:06d}", "frame": frame,
                        "cvat_frame": int(frame_map[frame]["cvat_frame"]), "reason": "RANDOM_QA",
                        "severity": "LOW", "nearby_track_ids": nearby, "anchor": anchor})
    return {"schema_version": 1, "type": "NON_FLAGGED_RANDOM_QA", "requested": count,
            "generated": len(samples), "seed": seed, "excluded_frame_count": len(excluded),
            "candidate_frame_count": len(candidates), "samples": samples,
            "interpretation": "review_samples_not_claimed_correct"}


def _marker_map(issues, comments):
    issue_by_id = {x.get("id"): x for x in issues if isinstance(x, dict)}
    output = {}
    for comment in comments:
        if not isinstance(comment, dict) or comment.get("issue") not in issue_by_id:
            continue
        first = str(comment.get("message", "")).splitlines()[0].strip()
        if first:
            output[first] = issue_by_id[comment["issue"]]
    return output


def final_validate(snapshot, annotations, label_plan, issue_plan=None, qa_plan=None,
                   issues=None, comments=None, prediction_state=None, motion_threshold=1.5):
    """Pure read-only validation of a fetched CVAT annotation snapshot."""
    issues, comments = issues or [], comments or []
    errors, warnings = [], []
    task_labels = {x.get("id"): x for x in snapshot.get("labels", []) if isinstance(x, dict)}
    supported_ids = {x["cvat_label_id"] for x in label_plan.get("supported", [])}
    job = snapshot["job"]
    start, stop = job["start_frame"], job["stop_frame"]
    frame_dims = {int(x["cvat_frame"]): (float(x["width"]), float(x["height"]))
                  for x in snapshot.get("mapping", [])}
    tracks = annotations.get("tracks") if isinstance(annotations, dict) else None
    if not isinstance(tracks, list):
        errors.append({"code": "MALFORMED_ANNOTATION_RESPONSE"}); tracks = []
    seen_track_ids, exact_shapes = set(), defaultdict(list)
    suspicious_jumps = []
    for track_index, track in enumerate(tracks):
        if not isinstance(track, dict) or not isinstance(track.get("shapes"), list):
            errors.append({"code": "MALFORMED_TRACK", "track_index": track_index}); continue
        track_id = track.get("id")
        if track_id is not None:
            if track_id in seen_track_ids:
                errors.append({"code": "DUPLICATE_TRACK_ID", "track_id": track_id})
            seen_track_ids.add(track_id)
        label_id = track.get("label_id")
        if label_id not in task_labels:
            errors.append({"code": "INVALID_LABEL_ID", "track_id": track_id, "label_id": label_id})
        elif task_labels[label_id].get("type") != "rectangle":
            errors.append({"code": "NON_RECTANGLE_TRACK_LABEL", "track_id": track_id, "label_id": label_id})
        elif supported_ids and label_id not in supported_ids:
            warnings.append({"code": "UNSUPPORTED_BUT_VALID_TASK_LABEL", "track_id": track_id, "label_id": label_id})
        previous_frame, previous_visible = None, None
        for shape_index, shape in enumerate(track["shapes"]):
            frame = shape.get("frame") if isinstance(shape, dict) else None
            if type(frame) is not int or not start <= frame <= stop:
                errors.append({"code": "FRAME_OUT_OF_RANGE", "track_id": track_id, "shape_index": shape_index, "frame": frame}); continue
            if previous_frame is not None and frame <= previous_frame:
                errors.append({"code": "TRACK_SHAPES_NOT_STRICTLY_ORDERED", "track_id": track_id, "frame": frame})
            previous_frame = frame
            points = shape.get("points")
            if (not isinstance(points, list) or len(points) != 4
                    or any(type(v) not in (int, float) or not math.isfinite(v) for v in points)):
                errors.append({"code": "INVALID_BBOX_POINTS", "track_id": track_id, "frame": frame}); continue
            x1, y1, x2, y2 = map(float, points)
            dims = frame_dims.get(frame)
            if x2 <= x1 or y2 <= y1 or dims is None or x2 <= 0 or y2 <= 0 or x1 >= dims[0] or y1 >= dims[1]:
                errors.append({"code": "INVALID_OR_OFFFRAME_BBOX", "track_id": track_id, "frame": frame})
            signature = (label_id, frame, tuple(round(v, 4) for v in (x1, y1, x2, y2)), bool(shape.get("outside", False)))
            exact_shapes[signature].append(track_id)
            if not shape.get("outside", False):
                current = (frame, x1, y1, x2-x1, y2-y1)
                if previous_visible and frame == previous_visible[0] + 1:
                    pf, px, py, pw, ph = previous_visible
                    motion = math.hypot((x1+(x2-x1)/2)-(px+pw/2), (y1+(y2-y1)/2)-(py+ph/2)) / max(math.hypot(pw, ph), 1e-9)
                    if motion > motion_threshold:
                        suspicious_jumps.append({"track_id": track_id, "frame": frame, "value": round(motion, 6), "threshold": motion_threshold})
                previous_visible = current
    duplicates = [{"label_id": key[0], "frame": key[1], "track_ids": ids}
                  for key, ids in exact_shapes.items() if len(set(ids)) > 1]
    if duplicates:
        warnings.append({"code": "DUPLICATE_EXACT_SHAPES", "count": len(duplicates), "examples": duplicates[:10]})
    if suspicious_jumps:
        warnings.append({"code": "SUSPICIOUS_IMPOSSIBLE_JUMPS", "count": len(suspicious_jumps), "examples": suspicious_jumps[:10]})

    markers = _marker_map(issues, comments)
    severity_counts, resolved_counts = Counter(), Counter()
    review_items = [item for item in (issue_plan or {}).get("items", [])
                    if item.get("metadata", {}).get("type") != "RANDOM_QA"]
    for item in review_items:
        severity = item.get("metadata", {}).get("severity", "LOW")
        severity_counts[severity] += 1
        remote = markers.get(item.get("marker"))
        if remote and remote.get("resolved") is True:
            resolved_counts[severity] += 1
    qa_items = (qa_plan or {}).get("items", [])
    qa_completed = sum(1 for item in qa_items
                       if markers.get(item.get("marker"), {}).get("resolved") is True)
    orphaned = []
    if prediction_state:
        remote_ids = {x.get("id") for x in tracks}
        orphaned = [{"external_track_id": external, "cvat_track_id": cvat}
                    for external, cvat in prediction_state.get("external_to_cvat_track", {}).items()
                    if cvat not in remote_ids]
        if orphaned:
            warnings.append({"code": "ORPHANED_EXTERNAL_TRACK_MAPPING", "count": len(orphaned), "examples": orphaned[:10]})
    current_hash = hashlib.sha256(json.dumps(
        annotations, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode()).hexdigest()
    auto_hash = (prediction_state or {}).get("annotation_hash_after")
    unresolved = {severity: severity_counts[severity]-resolved_counts[severity] for severity in SEVERITIES}
    return {"schema_version": 1, "mode": "READ_ONLY_FINAL_VALIDATION",
            "structural_checks": "PASS" if not errors else "FAIL", "errors": errors, "warnings": warnings,
            "annotation_hash": current_hash, "auto_annotation_hash": auto_hash,
            "human_edits_detected": bool(auto_hash and auto_hash != current_hash),
            "tracks": len(tracks), "track_shapes": sum(len(x.get("shapes", [])) for x in tracks if isinstance(x, dict)),
            "review_events": len(review_items), "events_by_severity": dict(severity_counts),
            "resolved_by_severity": dict(resolved_counts), "unresolved_by_severity": unresolved,
            "qa_samples_required": len(qa_items), "qa_samples_completed": qa_completed,
            "orphaned_mapping_count": len(orphaned), "suspicious_jump_count": len(suspicious_jumps)}


def release_decision(validation, policy):
    release = policy["release"]
    reasons = []
    if release["block_on_structural_failure"] and validation.get("structural_checks") != "PASS":
        return {"status": "BLOCKED", "structural_checks": validation.get("structural_checks"),
                "blocking_reasons": ["STRUCTURAL_VALIDATION_FAILED"],
                "unresolved_critical": validation.get("unresolved_by_severity", {}).get("CRITICAL", 0),
                "unresolved_high": validation.get("unresolved_by_severity", {}).get("HIGH", 0),
                "qa_samples_required": validation.get("qa_samples_required", 0),
                "qa_samples_completed": validation.get("qa_samples_completed", 0)}
    unresolved = validation.get("unresolved_by_severity", {})
    for severity in release["blocking_severities"]:
        if unresolved.get(severity, 0):
            reasons.append(f"UNRESOLVED_{severity}_ISSUES")
    if (release["require_qa_completion"]
            and validation.get("qa_samples_completed", 0) < validation.get("qa_samples_required", 0)):
        reasons.append("RANDOM_QA_INCOMPLETE")
    if validation.get("orphaned_mapping_count", 0):
        reasons.append("ORPHANED_TRACK_MAPPING_REQUIRES_REVIEW")
    return {"status": "REVIEW_REQUIRED" if reasons else "READY_FOR_EXPORT",
            "structural_checks": validation.get("structural_checks"),
            "unresolved_critical": unresolved.get("CRITICAL", 0),
            "unresolved_high": unresolved.get("HIGH", 0),
            "qa_samples_required": validation.get("qa_samples_required", 0),
            "qa_samples_completed": validation.get("qa_samples_completed", 0),
            "blocking_reasons": reasons}


def compact_review_state(task_id, job_id, issue_plan, qa_plan, validation=None, release=None):
    review_items = [x for x in (issue_plan or {}).get("items", [])
                    if x.get("metadata", {}).get("type") != "RANDOM_QA"]
    severity = Counter(x.get("metadata", {}).get("severity", "LOW") for x in review_items)
    state = {"schema_version": 1, "task_id": task_id, "job_id": job_id,
             "review_events_generated": len(review_items),
             "events_by_severity": dict(severity),
             "qa_samples_generated": len((qa_plan or {}).get("items", [])),
             "final_validation": validation, "release_check": release}
    if validation:
        state.update(issues_resolved=sum(validation.get("resolved_by_severity", {}).values()),
                     qa_samples_completed=validation.get("qa_samples_completed", 0))
    return state
