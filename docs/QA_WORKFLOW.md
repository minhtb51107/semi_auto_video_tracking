# Closed-loop QA workflow

```text
RAW DATA
  -> AUTO ANNOTATION
  -> ANALYZER V2
  -> EVENT PRIORITIZATION
  -> TARGETED REVIEW + RANDOM QA
  -> HUMAN CORRECTION / ISSUE RESOLUTION
  -> FINAL VALIDATION (READ ONLY)
  -> RELEASE CHECK
  -> MANUAL EXPORT
```

## Prioritized targeted review

Analyzer raw flags are aggregated into stable events first. Priority is then computed from configured reason weights, duration, contributing flags, repeat events for the same track, gap length, duplicate persistence, median confidence and proximity to image boundaries. Scores are deterministic integers from 0–100. Thresholds in `configs/qa_policy.json` map scores to `CRITICAL`, `HIGH`, `MEDIUM`, or `LOW`.

Priority is a review-order heuristic. It is not an error probability and does not alter the event ID or raw evidence. `--min-review-severity` and `--max-review-events` only select which prioritized events become CVAT Issues. Omitting both preserves previous behavior.

## Random QA

`--qa-sample-count N --qa-seed S` selects up to N unique frames outside every raw event context. The deterministic seed includes task ID, job ID, annotation hash, requested count and user seed. The same inputs reproduce the same sample. Each sample is a LOW-severity `QA-SAMPLE` Issue and may use the highest-confidence nearby track as a spatial anchor.

Random QA exposes potential Analyzer blind spots. A sampled frame is not presumed correct. Resolve the Issue only after inspection.

## Human review

Reviewers inspect high-priority events first, correct CVAT annotations themselves, and Resolve the corresponding Issues. The integration never merges, relabels, deletes or adjusts boxes automatically. CVAT Issue state is authoritative; compact local JSON records generation and read-back counts.

## Final validation

`--stage final-validate` is read-only. It validates annotation response shape, label IDs/types, frame bounds, bbox finiteness/intersection, strictly ordered track shapes, exact duplicate shapes, suspicious adjacent jumps, external/CVAT mapping consistency, unresolved Issues and QA completion. It verifies the annotation hash is identical before and after the stage.

This stage cannot prove object class correctness, detect all missing objects, or establish identity correctness from appearance.

## Release policy

`--stage release-check` applies `configs/qa_policy.json`:

- structural failure gives `BLOCKED`;
- unresolved configured severities, incomplete required QA, or orphan mappings give `REVIEW_REQUIRED`;
- otherwise it gives `READY_FOR_EXPORT`.

The command makes no export call. `READY_FOR_EXPORT` means the configured structural and workflow gate passed; it is not a semantic quality guarantee.

## Golden regression cases

`tests/golden_data/manifest.json` separates synthetic rule-behavior fixtures from references to observed evidence. Run:

```powershell
.venv\Scripts\python.exe -X utf8 tools/run_golden_qa.py
```

The runner checks stable Analyzer/release-gate behavior without inventing ground truth. Semantic false positives, detector-level false negatives, appearance identity ambiguity, VLM verification, training and automatic correction remain future work.
