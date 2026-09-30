# Output Quality Audit Fix Validation

Validation date: 2026-10-01. This is an offline regression against the locked task 44/job 61 artifacts. The live CVAT task and its existing Issues were not changed.

## Canonical class compatibility

The Analyzer now accepts an optional detector-class compatibility map derived from the CVAT run's locked `label_plan`. Classes 2, 5, and 7 therefore compare as canonical `vehicle`. When the map is absent or does not contain both known classes, the prior safe behavior remains: known subclasses must be exactly equal, while class-less legacy MOT rows retain geometry-only behavior.

Temporal and geometric safeguards are unchanged: two consecutive frames are still required, along with IoU at least 0.75, normalized center distance at most 0.10, and size ratio at most 1.35.

### Locked task 44 before/after

| Measure | Before | After |
|---|---:|---:|
| Raw Analyzer flags | 14 | 19 |
| Aggregated events | 13 | 18 |
| `possible_duplicate` flags | 0 | 3 |
| Confirmed false duplicate alerts in the audited windows | 0 | 0 |
| Runtime missed-detection candidates | 0 | 0 |

The three newly surfaced duplicate runs are:

| MOT frames / CVAT frames | External tracks | Minimum IoU | Audit interpretation |
|---|---|---:|---|
| 1–3 / 0–2 | E2 + E3 | 0.977 | confirmed duplicate of the main colorful bus |
| 1–2 / 0–1 | E4 + E5 | 0.957 | confirmed duplicate of the left vehicle |
| 14–15 / 13–14 | E3 + E11 | 0.811 | confirmed task44 bus duplicate |

The one-frame E7/E8 overlap remains unflagged because persistence was not weakened. Two additional canonical-compatible `possible_fragmentation` candidates were produced (E9→E10 and E10→E13); they remain review candidates and were not counted as confirmed false alerts without a new visual adjudication.

The permanent golden case `observed_task44_bus_fragmentation_duplicate` copies only the four audited MOT rows for E3/E11 and links back to `OUTPUT_QUALITY_AUDIT.md`. It now executes the real rule and requires `possible_duplicate`; it does not claim automated ground truth.

## CVAT Issue UX

Human-readable comments now:

- label all displayed frame values explicitly as CVAT frames;
- map first, middle, last, anchor, and context frames through the verified MOT→CVAT frame map;
- display primary and related identities as `CVAT <id> / external <id>`;
- provide distinct continuity, identity, fragmentation, duplicate, and geometry actions;
- keep raw MOT/event fields inside `METADATA_JSON` for audit.

For the task44 bus case, a fresh offline plan produced a bbox-centered marker at CVAT frame 14, position `[592.34, 278.15]`, and told the reviewer to compare CVAT track 160/external 3 with CVAT track 168/external 11 across CVAT frames 11–16. Existing live Issues are intentionally left unchanged to preserve prior evidence and idempotency.

## Detector coverage

Pre-tracker detections, including class and confidence, were already persisted in hashed chunk checkpoints and are read during deterministic resume. The coverage audit remains `DESIGNED_ONLY`: task44 evidence is not sufficient to set a reference-free heuristic that catches its principal fully missed buses without conflating exits and occlusions. No fake missed-object rule, box, relabel, or CVAT Issue was added. See `DETECTOR_COVERAGE_AUDIT_DESIGN.md`.

## Commands and status

- Golden QA: `.venv\Scripts\python.exe -X utf8 tools\run_golden_qa.py` — PASS.
- Task44 offline comparison: locked `mot/predictions.txt`, canonical map `{2,5,7: vehicle}` — 3 confirmed duplicate runs surfaced.
- Full unit suite: 126/126 PASS.
- Live mutation: not performed.
