"""Deterministic, explainable prioritization layered over Analyzer v2 events."""
from __future__ import annotations

from collections import Counter
import json
import math
from pathlib import Path
import statistics


DEFAULT_POLICY = Path(__file__).resolve().parents[1] / "configs" / "qa_policy.json"
SEVERITIES = ("CRITICAL", "HIGH", "MEDIUM", "LOW")


def load_policy(path=DEFAULT_POLICY):
    value = json.loads(Path(path).read_text(encoding="utf-8-sig"))
    if set(value) != {"schema_version", "priority", "release"} or value["schema_version"] != 1:
        raise ValueError("Invalid QA policy schema")
    priority = value["priority"]
    required = {
        "reason_weights", "duration_points_per_frame", "duration_points_cap",
        "extra_raw_flag_points", "extra_raw_flag_cap", "repeat_track_points",
        "repeat_track_cap", "long_gap_points_per_frame", "long_gap_points_cap",
        "persistent_duplicate_points_per_frame", "persistent_duplicate_points_cap",
        "low_confidence_threshold", "low_confidence_points", "boundary_margin_ratio",
        "boundary_penalty", "severity_thresholds",
    }
    if set(priority) != required or set(priority["severity_thresholds"]) != set(SEVERITIES):
        raise ValueError("Invalid priority policy keys")
    numeric = [v for key, v in priority.items() if key not in ("reason_weights", "severity_thresholds")]
    numeric += list(priority["reason_weights"].values()) + list(priority["severity_thresholds"].values())
    if any(type(v) not in (int, float) or not math.isfinite(v) or v < 0 for v in numeric):
        raise ValueError("Invalid priority policy value")
    thresholds = priority["severity_thresholds"]
    if not thresholds["CRITICAL"] >= thresholds["HIGH"] >= thresholds["MEDIUM"] >= thresholds["LOW"]:
        raise ValueError("Severity thresholds must descend")
    release = value["release"]
    if (set(release) != {"blocking_severities", "require_qa_completion", "block_on_structural_failure"}
            or not isinstance(release["blocking_severities"], list)
            or not set(release["blocking_severities"]).issubset(SEVERITIES)
            or type(release["require_qa_completion"]) is not bool
            or type(release["block_on_structural_failure"]) is not bool):
        raise ValueError("Invalid release policy")
    return value


def _severity(score, thresholds):
    for name in SEVERITIES:
        if score >= thresholds[name]:
            return name
    return "LOW"


def _legacy(row):
    return row.legacy() if hasattr(row, "legacy") else row


def prioritize_events(events_data, flags_data, rows, mapping, policy=None):
    """Return every event with priority metadata; never change event_id/reasons."""
    policy = policy or load_policy()
    cfg = policy["priority"]
    events = events_data.get("events") if isinstance(events_data, dict) else None
    flags = flags_data.get("flags") if isinstance(flags_data, dict) else None
    if not isinstance(events, list) or not isinstance(flags, list):
        raise ValueError("Invalid Analyzer event/flag data")
    flag_by_id = {x.get("raw_flag_id"): x for x in flags}
    if len(flag_by_id) != len(flags) or None in flag_by_id:
        raise ValueError("Invalid or duplicate raw flag IDs")
    dimensions = {x["mot_frame"]: (float(x["width"]), float(x["height"])) for x in mapping}
    rows_by_track = {}
    for value in rows or []:
        legacy = _legacy(value)
        rows_by_track.setdefault(int(legacy[1]), []).append(legacy)
    repeats = Counter(int(e["track_id"]) for e in events)
    output = []
    for event in events:
        item = dict(event)
        explanations = []
        score = 0.0
        for reason in sorted(set(item["reasons"])):
            points = float(cfg["reason_weights"].get(reason, 10))
            score += points
            explanations.append({"signal": f"reason:{reason}", "points": points})
        duration = max(1, int(item["end_frame"]) - int(item["start_frame"]) + 1)
        points = min(cfg["duration_points_cap"], max(0, duration - 1) * cfg["duration_points_per_frame"])
        if points:
            score += points; explanations.append({"signal": "event_duration", "value": duration, "points": points})
        raw_count = len(item["raw_flag_ids"])
        points = min(cfg["extra_raw_flag_cap"], max(0, raw_count - 1) * cfg["extra_raw_flag_points"])
        if points:
            score += points; explanations.append({"signal": "contributing_raw_flags", "value": raw_count, "points": points})
        repeat_count = repeats[int(item["track_id"])]
        points = min(cfg["repeat_track_cap"], max(0, repeat_count - 1) * cfg["repeat_track_points"])
        if points:
            score += points; explanations.append({"signal": "repeat_events_for_track", "value": repeat_count, "points": points})
        related_flags = [flag_by_id[x] for x in item["raw_flag_ids"] if x in flag_by_id]
        gaps = [float(x["observed_value"]) for x in related_flags
                if x.get("reason") in ("track_gap", "track_reappeared")
                and type(x.get("observed_value")) in (int, float)]
        if gaps:
            points = min(cfg["long_gap_points_cap"], max(gaps) * cfg["long_gap_points_per_frame"])
            score += points; explanations.append({"signal": "long_gap", "value": max(gaps), "points": points})
        persistent = [float(x["observed_value"].get("consecutive_frames", 0)) for x in related_flags
                      if x.get("reason") == "possible_duplicate" and isinstance(x.get("observed_value"), dict)]
        if persistent:
            points = min(cfg["persistent_duplicate_points_cap"], max(persistent) * cfg["persistent_duplicate_points_per_frame"])
            score += points; explanations.append({"signal": "persistent_duplicate", "value": max(persistent), "points": points})
        track_rows = rows_by_track.get(int(item["track_id"]), [])
        confidences = [float(x[6]) for x in track_rows if math.isfinite(float(x[6]))]
        if confidences and statistics.median(confidences) < cfg["low_confidence_threshold"]:
            points = cfg["low_confidence_points"]
            score += points; explanations.append({"signal": "low_track_confidence", "value": round(statistics.median(confidences), 6), "points": points})
        if track_rows:
            chosen = min(track_rows, key=lambda x: (abs(int(x[0]) - int(item["anchor_frame"])), int(x[0])))
            dims = dimensions.get(int(chosen[0]))
            if dims:
                _, _, x, y, w, h, _ = chosen
                margin_x, margin_y = dims[0] * cfg["boundary_margin_ratio"], dims[1] * cfg["boundary_margin_ratio"]
                near = x <= margin_x or y <= margin_y or x + w >= dims[0] - margin_x or y + h >= dims[1] - margin_y
                if near:
                    points = -cfg["boundary_penalty"]
                    score += points; explanations.append({"signal": "near_image_boundary", "points": points})
        score = int(round(max(0, min(100, score))))
        item["severity"] = _severity(score, cfg["severity_thresholds"])
        item["priority_score"] = score
        item["priority_reasons"] = explanations
        output.append(item)
    output.sort(key=lambda x: (-x["priority_score"], x["start_frame"], x["event_id"]))
    return {"schema_version": 1, "source_schema_version": events_data.get("schema_version"),
            "events": output, "severity_counts": dict(Counter(x["severity"] for x in output))}


def select_events(prioritized, min_severity=None, max_events=None):
    events = list(prioritized.get("events", []))
    if min_severity is not None:
        if min_severity not in SEVERITIES:
            raise ValueError("Invalid minimum review severity")
        allowed = set(SEVERITIES[:SEVERITIES.index(min_severity) + 1])
        events = [x for x in events if x["severity"] in allowed]
    if max_events is not None:
        if type(max_events) is not int or max_events < 1:
            raise ValueError("max_review_events must be positive")
        events = events[:max_events]
    return {"schema_version": 2, "events": events,
            "selection": {"min_severity": min_severity, "max_events": max_events,
                          "selected": len(events), "available": len(prioritized.get("events", []))}}
