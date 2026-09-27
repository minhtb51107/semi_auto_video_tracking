"""Read-only workspace accounting and guarded cleanup for completed CVAT runs."""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path


class WorkspaceError(ValueError):
    pass


def _read(path: Path):
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError):
        raise WorkspaceError(f"Missing or corrupt workspace artifact: {path.name}") from None


def _save(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    temp.replace(path)


def _sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _size(paths) -> int:
    return sum(p.stat().st_size for p in paths if p.is_file())


def _files(folder: Path):
    return list(folder.rglob("*")) if folder.is_dir() else []


def validate_completed_workspace(workspace: Path) -> dict:
    workspace = Path(workspace).resolve()
    required = {
        "metadata": workspace / "metadata.json",
        "summary": workspace / "run_summary.json",
        "frames": workspace / "frames" / "manifest.json",
        "prediction": workspace / "predictions" / "manifest.json",
        "review": workspace / "predictions" / "review_manifest.json",
        "mot": workspace / "mot" / "predictions.txt",
        "events": workspace / "review_events.json",
        "prediction_push": workspace / "cvat_push" / "predictions.json",
        "issue_state": workspace / "cvat_push" / "issues_state.json",
    }
    missing = [str(path.relative_to(workspace)) for key, path in required.items() if not path.is_file()]
    reasons = [f"missing:{name}" for name in missing]
    if reasons:
        return {"eligible": False, "reasons": reasons, "workspace": str(workspace)}
    values = {key: _read(path) for key, path in required.items() if key not in ("mot", "events")}
    summary, prediction, review = values["summary"], values["prediction"], values["review"]
    push, issues, frames = values["prediction_push"], values["issue_state"], values["frames"]
    checks = [
        (summary.get("status") == "COMPLETE", "run_not_complete"),
        (push.get("status") == "verified", "prediction_push_not_verified"),
        (summary.get("issue_push", {}).get("verified") is True, "issue_push_not_verified"),
        (summary.get("issue_push", {}).get("annotations_unchanged") is True, "issue_annotation_guard_failed"),
        (issues.get("verified") is True, "issue_readback_not_verified"),
        (issues.get("annotations_unchanged") is True, "issue_state_annotation_guard_failed"),
        (prediction.get("status") == "complete", "prediction_manifest_incomplete"),
        (prediction.get("mot_sha256") == _sha(required["mot"]), "mot_hash_mismatch"),
        (review.get("mot_sha256") == prediction.get("mot_sha256"), "review_mot_hash_mismatch"),
        (review.get("events_sha256") == _sha(required["events"]), "event_hash_mismatch"),
        (push.get("mot_sha256") == prediction.get("mot_sha256"), "push_mot_hash_mismatch"),
        (issues.get("annotations_before_sha256") == push.get("annotation_hash_after"), "issue_prediction_hash_mismatch"),
        (not (workspace / "cvat_push" / "push.lock").exists(), "writer_lock_present"),
        (frames.get("status") in ("complete", "cleaned"), "frame_manifest_incomplete"),
    ]
    reasons.extend(reason for ok, reason in checks if not ok)
    entries = frames.get("frames", [])
    if not isinstance(entries, list):
        reasons.append("invalid_frame_manifest")
    elif frames.get("status") == "complete":
        for item in entries:
            path = workspace / "frames" / str(item.get("local_name", ""))
            if not path.is_file() or _sha(path) != item.get("sha256"):
                reasons.append(f"frame_hash_mismatch:{item.get('local_name')}")
                break
    elif list((workspace / "frames").glob("*.jpg")):
        reasons.append("cleaned_manifest_has_frames")
    return {"eligible": not reasons, "reasons": reasons, "workspace": str(workspace),
            "task_id": summary.get("task_id"), "job_id": summary.get("job_id"),
            "frame_state": frames.get("status")}


def cleanup_candidates(workspace: Path, whole_run: bool = False) -> list[Path]:
    workspace = Path(workspace).resolve()
    if whole_run:
        candidates = [path for path in workspace.rglob("*")
                      if path.is_file() and path.name != "minimal_audit_manifest.json"]
    else:
        candidates = list((workspace / "frames").glob("*.jpg"))
        candidates.extend(path for path in workspace.rglob("*")
                          if path.is_file() and path.suffix == ".tmp")
    unique = []
    for path in sorted(set(p.resolve() for p in candidates)):
        try:
            path.relative_to(workspace)
        except ValueError:
            raise WorkspaceError("Cleanup candidate escaped workspace") from None
        unique.append(path)
    return unique


def workspace_status(workspace: Path) -> dict:
    workspace = Path(workspace).resolve()
    all_files = [p for p in _files(workspace) if p.is_file()]
    frames = [p for p in _files(workspace / "frames") if p.is_file()]
    predictions = [p for p in _files(workspace / "predictions") if p.is_file()]
    mot = [p for p in _files(workspace / "mot") if p.is_file()]
    known = set(frames + predictions + mot)
    evidence = [p for p in all_files if p not in known]
    try:
        eligibility = validate_completed_workspace(workspace)
    except WorkspaceError as exc:
        eligibility = {"eligible": False, "reasons": [str(exc)], "workspace": str(workspace)}
    summary_path = workspace / "run_summary.json"
    summary = _read(summary_path) if summary_path.is_file() else {}
    return {
        "schema_version": 1,
        "workspace": str(workspace),
        "total_bytes": _size(all_files),
        "sizes": {"frames_bytes": _size(frames), "predictions_bytes": _size(predictions),
                  "mot_bytes": _size(mot), "evidence_metadata_bytes": _size(evidence)},
        "pipeline_status": summary.get("status", "UNKNOWN"),
        "cleanup_eligibility": eligibility,
        "cleanup_preview": {"frames": [str(p.relative_to(workspace)).replace("\\", "/") for p in cleanup_candidates(workspace)],
                            "frames_reclaim_bytes": _size(cleanup_candidates(workspace)),
                            "whole_run": [str(p.relative_to(workspace)).replace("\\", "/") for p in cleanup_candidates(workspace, True)],
                            "whole_run_reclaim_bytes": _size(cleanup_candidates(workspace, True))},
        "artifact_classification": {
            "frames": ["REQUIRED_FOR_RESUME", "EXPENSIVE_TO_REGENERATE", "SAFE_TO_DELETE_AFTER_VERIFY"],
            "prediction_manifests": ["REQUIRED_FOR_AUDIT", "REQUIRED_FOR_RESUME"],
            "mot": ["REQUIRED_FOR_AUDIT", "REQUIRED_FOR_RESUME", "EXPENSIVE_TO_REGENERATE"],
            "review_events_and_flags": ["REQUIRED_FOR_AUDIT", "CHEAP_TO_REGENERATE"],
            "cvat_push_manifests": ["REQUIRED_FOR_AUDIT", "REQUIRED_FOR_RESUME"],
            "metadata_hashes_summaries": ["REQUIRED_FOR_AUDIT", "REQUIRED_FOR_RESUME"],
            "temp_cache": ["CHEAP_TO_REGENERATE", "SAFE_TO_DELETE_AFTER_VERIFY"],
        },
    }


def _audit_manifest(workspace: Path, removed: list[Path], released: int, action: str) -> dict:
    metadata = _read(workspace / "metadata.json")
    summary = _read(workspace / "run_summary.json")
    prediction = _read(workspace / "predictions" / "manifest.json")
    push = _read(workspace / "cvat_push" / "predictions.json")
    return {
        "schema_version": 1, "action": action,
        "cleaned_at_utc": datetime.now(timezone.utc).isoformat(),
        "task": metadata.get("task"), "job": metadata.get("job"),
        "target_sha256": metadata.get("target_sha256"),
        "model_sha256": prediction.get("tracking_config", {}).get("model_sha256"),
        "tracker_sha256": prediction.get("tracking_config", {}).get("tracker_sha256"),
        "tracking_config_sha256": prediction.get("tracking_config_sha256"),
        "frame_inventory_sha256": prediction.get("frame_inventory_sha256"),
        "mot_sha256": prediction.get("mot_sha256"),
        "result_summary": summary,
        "cvat_mapping_summary": {"count": len(push.get("external_to_cvat_track", {})),
                                 "external_to_cvat_track": push.get("external_to_cvat_track", {})},
        "removed_files": [str(p.relative_to(workspace)).replace("\\", "/") for p in removed],
        "released_bytes": released,
    }


def cleanup_frames(workspace: Path) -> dict:
    workspace = Path(workspace).resolve()
    valid = validate_completed_workspace(workspace)
    if not valid["eligible"]:
        raise WorkspaceError("Cleanup refused: " + ", ".join(valid["reasons"]))
    candidates = cleanup_candidates(workspace)
    released = _size(candidates)
    for path in candidates:
        path.unlink()
    manifest_path = workspace / "frames" / "manifest.json"
    manifest = _read(manifest_path)
    manifest.update(status="cleaned", frames_removed=True,
                    cleaned_at_utc=datetime.now(timezone.utc).isoformat(), released_bytes=released)
    _save(manifest_path, manifest)
    record = _audit_manifest(workspace, candidates, released, "cleanup_frames")
    _save(workspace / "cvat_push" / "cleanup_record.json", record)
    return {"status": "CLEANED" if candidates else "ALREADY_CLEAN", "workspace": str(workspace),
            "removed_count": len(candidates), "released_bytes": released,
            "preserved": ["metadata.json", "frames/manifest.json", "predictions/", "mot/",
                          "review_events.json", "cvat_push/", "run_summary.json"]}


def cleanup_run(workspace: Path, confirm: str | None = None) -> dict:
    workspace = Path(workspace).resolve()
    minimal_path = workspace / "minimal_audit_manifest.json"
    existing = [path for path in _files(workspace) if path.is_file() and path != minimal_path]
    if minimal_path.is_file() and not existing:
        return {"status": "ALREADY_CLEAN", "workspace": str(workspace),
                "confirmation_required": workspace.name, "files": [], "reclaim_bytes": 0,
                "minimal_audit_manifest": "minimal_audit_manifest.json"}
    valid = validate_completed_workspace(workspace)
    if not valid["eligible"]:
        raise WorkspaceError("Cleanup refused: " + ", ".join(valid["reasons"]))
    candidates = cleanup_candidates(workspace, True)
    preview = {"status": "PREVIEW", "workspace": str(workspace),
               "confirmation_required": workspace.name,
               "files": [str(p.relative_to(workspace)).replace("\\", "/") for p in candidates],
               "reclaim_bytes": _size(candidates)}
    if confirm is None:
        return preview
    if confirm != workspace.name:
        raise WorkspaceError(f"Confirmation must equal {workspace.name}")
    released = preview["reclaim_bytes"]
    record = _audit_manifest(workspace, candidates, released, "cleanup_run")
    for path in candidates:
        path.unlink()
    for folder in sorted((path for path in workspace.rglob("*") if path.is_dir()),
                         key=lambda path: len(path.parts), reverse=True):
        try:
            folder.rmdir()
        except OSError:
            pass
    _save(minimal_path, record)
    return {**preview, "status": "CLEANED" if candidates else "ALREADY_CLEAN",
            "minimal_audit_manifest": "minimal_audit_manifest.json"}
