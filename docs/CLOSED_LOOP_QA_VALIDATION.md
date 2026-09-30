# Closed-loop QA live validation

Validation date: 2026-09-30 (Asia/Saigon).

This is operational evidence from a new disposable CVAT task. It is not a semantic-quality benchmark or a human-efficiency result.

## Target and configuration

- CVAT task 44, job 61, 40 chronological frames
- labels: `person`, `vehicle`
- task URL: <http://localhost:8080/tasks/44/jobs/61>
- chunk size: 20
- event selection: top 8 events
- random QA: 3 samples, seed 42
- source: the first 40 frames of the already-downloaded, gitignored Bangladesh Urban Traffic validation clip

Dry-run found an empty annotation job, both labels supported, and annotation safety `PASS`.

## Live result

- detector detections: 111
- predicted boxes: 72
- predicted tracks: 14, all `vehicle` in this 40-frame segment
- Analyzer: 14 raw flags -> 13 aggregated events
- priority distribution before top-N selection: 1 CRITICAL, 6 MEDIUM, 6 LOW
- selected targeted-review Issues: 8
- random-QA Issues: 3
- total Issues read back: 11
- second completed invocation: 0 Issues created, 11 skipped
- annotation push: verified; 14 tracks, 94 CVAT keyframes including outside markers

The first network attempts failed safely during GET/frame download and resumed from the local frame/chunk state. A later read-back exposed that remote reconciliation indexed only `SATV2|...` markers and ignored the new `QA-SAMPLE|...` namespace. All 11 remote Issues had already been created and locally checkpointed, so the safety guard refused to recreate them. The reconciliation code now recognizes both namespaces; a regression test covers read-back with prior QA mappings. The next invocation verified all 11 and created zero duplicates.

## Read-only stages

`final-validate` returned structural `PASS`, zero structural errors, zero orphan mappings, and confirmed the annotation hash was unchanged during validation.

`release-check` returned `REVIEW_REQUIRED` because one CRITICAL targeted-review Issue and all three random-QA Issues remain unresolved. This is the expected gate result before human review. No export was attempted.

## Status matrix

| Capability | Status | Evidence |
|---|---|---|
| Deterministic prioritization | **LIVE_VERIFIED** | 13 events scored/sorted; top 8 selected |
| Severity/readable Issue comment | **LIVE_VERIFIED** | plan and 8 targeted Issues read back |
| Random QA representation | **LIVE_VERIFIED** | 3 distinct QA Issues read back |
| Issue retry/idempotency | **LIVE_VERIFIED** | retry created 0 and skipped 11 |
| Final validation read-only | **LIVE_VERIFIED** | before/after annotation hash identical |
| Release gate | **LIVE_VERIFIED** | explainable `REVIEW_REQUIRED` result |
| Post-human correction preservation | **MOCK_TESTED** | no human edit was made in this validation |
| QA completion/resolution read-back | **IMPLEMENTED / NOT_YET_LIVE_VERIFIED** | requires a reviewer to inspect and Resolve samples |

To complete the manual lifecycle check, a reviewer should inspect task 44, correct annotations if needed, Resolve the CRITICAL Issue and all three `QA-SAMPLE` Issues, then rerun `final-validate` and `release-check`.
