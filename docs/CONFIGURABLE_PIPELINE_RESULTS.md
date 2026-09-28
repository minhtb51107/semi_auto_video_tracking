# Configurable Pipeline Milestone Results

## Status

| Capability | Status | Evidence |
|---|---|---|
| Configurable multi-label mapping and aliases | IMPLEMENTED / MOCK_TESTED | Single/multiple/mixed/unsupported/type/alias tests |
| Normalized Detector/Tracker protocols | IMPLEMENTED / MOCK_TESTED | Mock substitution plus real local ByteTrack adapter test |
| Class identity through MOT and CVAT payload | IMPLEMENTED / MOCK_TESTED | Two-class mock run creates the corresponding CVAT label IDs |
| Task `--all-jobs` orchestration | IMPLEMENTED / MOCK_TESTED | Deterministic two-job partial-failure fixture |
| Chunk checkpoint/resume | IMPLEMENTED / MOCK_TESTED | Detector crash/retry, cache replay, hash/config mismatch tests |
| Human-readable Issue comment | IMPLEMENTED / MOCK_TESTED | Comment/marker/idempotency/legacy-plan tests |
| Compact operational summary | IMPLEMENTED / MOCK_TESTED | Per-job/task summaries and stage timing assertions |
| Multi-label or multi-job CVAT server | NOT LIVE_VERIFIED | No live task mutation in this iteration |

## Local vehicle compatibility smoke

The refactored detector + ByteTrack adapters were run on the 60-frame internal clip 02 with the established model/config (`yolo26n.pt`, COCO classes 2/5/7, `bytetrack.yaml`, confidence 0.25, IoU 0.7, image size 960, CPU). It produced **228 tracked boxes / 7 tracks**. A separate current-environment `Ultralytics YOLO.track(... persist=True ...)` reference produced the same **228 / 7** counts.

This is a local runtime compatibility smoke, not live CVAT validation and not proof of identical track IDs. External track IDs are implementation-local; geometry/class payloads and CVAT read-back remain the integration contract.

## Resume semantics

Only the detector work of completed chunks is skipped. ByteTrack state is rebuilt by replaying cached normalized detections, and replay output must match the locked TrackBox checkpoint. The implementation deliberately rejects incompatible/corrupt resume state rather than serializing private Ultralytics tracker objects.

## Remaining gates

- Run a disposable live task containing at least two configured rectangle labels.
- Run a disposable live task split into multiple annotation jobs.
- Benchmark a 1,000+ frame job and record disk/runtime behavior.
- Decide whether Analyzer inter-track rules should be class-aware using held-out evidence.
- Semantic false-positive verification and detector-level false-negative discovery remain out of scope.
