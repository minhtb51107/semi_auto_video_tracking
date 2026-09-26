# Human review pilot — package readiness, not human results

**Status: PACKAGE_READY_HUMAN_COLLECTION_PENDING.** No reviewer session has been collected or adjudicated by this task. Phase3 human pilot acceptance is therefore pending, not passed.

## Delivered

- `outputs/human_review/index.html`: offline entry point. Open in Edge/Chrome, keeping folder structure intact.
- Four prediction-only pages: A/B for KITTI0000 (154 frames,12 assisted events) and0001 (31 frames,7 assisted events). No detector/tracker/analyzer rerun or threshold change.
- Mode A has no embedded analyzer events/reasons; first viewing pass must progress sequentially. Mode B has context, reasons, primary/related tracks, event verdict/fix/note and expansion controls. All pages hide GT and prior adjudications.
- Browser timing: UTC start/end, monotonic active duration, pause/resume, auto-pause when hidden/blurred, displayed-frame history, per-event dwell and action logs. Metadata is fixed at Start. Reload/import checkpoint resumes paused; elapsed time away is not invented.
- Findings separate from event verdicts; proposed fixes separate from actual self-reported correction actions. This is review-only, not an annotation editor.
- JSON/CSV exports and simple post-review adjudication UI with a historical **partial** reference set (5 issue units0001,12 issue units0000). Match known IDs or use `NEW-...` with evidence; duplicate findings share a canonical ID.
- Baseline, assisted and adjudication CSV templates contain headers only. No fake participants, times, verdicts or findings are prefilled.
- `docs/HUMAN_REVIEW_PROTOCOL.md`: single-reviewer default, reversed within-mode sequence order, optional second reviewer opposite group, preferred24h break, familiarity/order limitations and metric definitions.

No fresh sequence was acquired in this round. This is a workflow pilot on familiar data, not an unbiased controlled study. The administrative reference data and historical reports must remain unopened during timed review. Reference IDs/notes can be checked against their source reports after review; the historical set is neither an exhaustive census nor independent new adjudication.

## Technical verification

**38/38 tests PASS**, including all33 previous tests and five new package/accounting tests. Node is used for pure JavaScript accounting tests; reviewer runtime only requires a browser. Existing Windows Temp tests were run outside the restricted sandbox, without changing tests. Expected FFmpeg invalid-video message remains a negative test.

Browser QA used **Edge headless, isolated profiles and practice-only pages**. Both baseline and assisted controls exercised Start, successful frame rendering, premature-Finish rejection, finding/verdict recording, Pause/Resume, Finish and export. The adjudication page rejected a practice export and retained its empty-human-results state. Screenshots were inspected:

- `outputs/human_review/qa/baseline_qa.png`
- `outputs/human_review/qa/assisted_qa.png`
- `outputs/human_review/qa/adjudication_qa.png`

These screenshots show synthetic software tests, **not human effort or results**. QA/practice exports are excluded by the summary validator. Browser stdout was empty on this Windows Edge invocation; screenshots provide the visible PASS markers. Unit tests cover metric calculations with synthetic fixtures only; fixture values are not placed in `collected/` or human summaries.

Package audit verified every image link,185 source image files, correct event counts, baseline event omission, prediction-only overlays, asset/source hashes and preservation of1,257 pre-existing output/core files. `source_manifest.json`, `qa/integrity.json`, `status.json` hold machine-readable checks. `outputs/human_review_preservation_before.json` is the before snapshot. Collected session directory remains empty.

## Launch and collection

1. Read the protocol; choose group X/Y and a pseudonymous reviewer ID. Disclose prior exposure.
2. Open `outputs/human_review/index.html` by double-clicking in Explorer or using Open File in Edge/Chrome. Practice first. No server, npm install, API or network is needed.
3. Open the assigned mode/sequence, enter metadata, press Start. Record actual findings and, in assisted mode, every event verdict. “Dùng frame đang xem” fills the current finding frame/track; adjust the range when the issue spans multiple frames.
4. Pause for interruption; save checkpoints. Finish downloads JSON. Keep files from Downloads; browser cannot silently save into the project. Import a checkpoint through the UI if draft storage is lost. CSV is supplementary; JSON carries the complete frame/timing/event history.
5. After all sessions, open adjudication, import completed session JSONs, confirm/deduplicate findings and export comparison JSON plus adjudication CSV. Send those files for analysis. No complex JSON editing is required.

Historical recall, missed known issues and efficiency stay N/A until adjudication is complete. Reviewer-rated event precision is distinguished from independent truth. Empty/no-issue denominators stay N/A where appropriate. Tool candidate scope is not time saving. A/B comparison is paired only for the same reviewer and sequence with exactly one completed session of each mode; repetitions require explicit selection.

## Remaining blockers and decision

No known technical blocker prevents starting manual review now. Remaining work necessarily requires the real reviewer: complete both modes, retain actual timings, supply verdicts/findings, adjudicate and inspect friction/slow events. A full counterbalanced four-session run may span more than one day if the preferred break is respected; starting today does not mean the human pilot has already completed.

After the real pilot, judge missed issues and workload together. One familiar reviewer on two already analyzed sequences will still not justify production or automatic CVAT integration. No human outcome has been assessed, no threshold tuned, no CVAT/deployment/database/authentication added, and no commit/push performed.

## Reproduction

`tools/build_review_package.py` builds a fresh package and refuses an existing output directory to protect sessions. For another build use `--out outputs/human_review_new_package`; do not mix package versions within a paired pilot. Run `.venv\Scripts\python.exe -X utf8 -m unittest discover -s tests -v` for the full suite. Browser QA script is `tests/pilot_browser_qa.js`, explicitly restricted to practice payloads; it is not a participant-data generator.
