"""Validated detector-class to CVAT-label configuration."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path


class LabelMappingError(ValueError):
    pass


def load_label_config(path: Path | str) -> dict:
    path = Path(path)
    try:
        raw = path.read_bytes()
        data = json.loads(raw.decode("utf-8-sig"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        raise LabelMappingError(f"Cannot read label mapping config: {path}") from None
    labels = data.get("labels") if isinstance(data, dict) else None
    if not isinstance(data, dict) or data.get("schema_version") != 1 or not isinstance(labels, dict) or not labels:
        raise LabelMappingError("Label mapping config requires schema_version=1 and non-empty labels")
    aliases: dict[str, str] = {}
    class_owners: dict[int, str] = {}
    normalized = {}
    for name, spec in labels.items():
        if not isinstance(name, str) or not name.strip() or not isinstance(spec, dict):
            raise LabelMappingError("Invalid configured label")
        canonical = name.strip().lower()
        classes = spec.get("detector_classes")
        label_aliases = spec.get("aliases", [])
        if (not isinstance(classes, list) or not classes
                or any(type(value) is not int or value < 0 for value in classes)
                or len(set(classes)) != len(classes)):
            raise LabelMappingError(f"Invalid detector_classes for {name}")
        if not isinstance(label_aliases, list) or any(not isinstance(x, str) or not x.strip() for x in label_aliases):
            raise LabelMappingError(f"Invalid aliases for {name}")
        for value in [canonical, *(x.strip().lower() for x in label_aliases)]:
            if value in aliases and aliases[value] != canonical:
                raise LabelMappingError(f"Alias {value!r} maps to multiple labels")
            aliases[value] = canonical
        for class_id in classes:
            if class_id in class_owners:
                raise LabelMappingError(f"Detector class {class_id} belongs to multiple labels")
            class_owners[class_id] = canonical
        normalized[canonical] = {"detector_classes": classes,
                                 "aliases": sorted({x.strip().lower() for x in label_aliases})}
    return {"schema_version": 1, "labels": normalized, "aliases": aliases,
            "class_owners": class_owners, "path": str(path.resolve()),
            "sha256": hashlib.sha256(raw).hexdigest()}


def match_task_labels(task_labels: list[dict], config: dict,
                      selected: list[str] | None = None,
                      class_filter: list[int] | None = None) -> dict:
    """Return a non-ambiguous class-to-CVAT-label plan and explicit unsupported rows."""
    requested_raw = {x.strip().lower() for x in (selected or []) if x.strip()}
    requested = {config["aliases"].get(value, value) for value in requested_raw}
    supported, unsupported = [], []
    canonical_seen: dict[str, str] = {}
    task_names = {str(x.get("name", "")).strip().lower() for x in task_labels}
    for item in task_labels:
        name = str(item.get("name", "")).strip()
        key = name.lower()
        if requested and config["aliases"].get(key, key) not in requested:
            continue
        canonical = config["aliases"].get(key)
        if item.get("type") != "rectangle":
            unsupported.append({"label": name, "reason": "INCORRECT_CVAT_LABEL_TYPE",
                                "type": item.get("type")})
            continue
        if canonical is None:
            unsupported.append({"label": name, "reason": "UNSUPPORTED_LABEL"})
            continue
        if canonical in canonical_seen:
            raise LabelMappingError(
                f"CVAT labels {canonical_seen[canonical]!r} and {name!r} map to the same configured label {canonical!r}"
            )
        classes = list(config["labels"][canonical]["detector_classes"])
        if class_filter is not None:
            classes = [value for value in classes if value in class_filter]
        if not classes:
            unsupported.append({"label": name, "reason": "NO_SELECTED_DETECTOR_CLASSES"})
            continue
        canonical_seen[canonical] = name
        supported.append({"cvat_label_id": item.get("id"), "cvat_label": name,
                          "canonical_label": canonical, "detector_classes": classes})
    for name in sorted(requested):
        if name not in task_names and not any(row["canonical_label"] == name for row in supported):
            unsupported.append({"label": name, "reason": "LABEL_NOT_IN_CVAT_TASK"})
    class_to_label = {}
    for row in supported:
        if type(row["cvat_label_id"]) is not int:
            raise LabelMappingError(f"CVAT label {row['cvat_label']!r} has no integer ID")
        for class_id in row["detector_classes"]:
            if class_id in class_to_label:
                raise LabelMappingError(f"Selected labels overlap on detector class {class_id}")
            class_to_label[class_id] = row
    return {"supported": supported, "unsupported": unsupported,
            "class_to_label": class_to_label,
            "detector_classes": sorted(class_to_label),
            "selected": sorted(requested), "config_sha256": config["sha256"]}
