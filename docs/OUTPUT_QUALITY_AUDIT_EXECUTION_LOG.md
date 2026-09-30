# Output Quality Audit execution log

Audit target: CVAT task 44 / job 61. Date: 2026-09-30. No credentials are recorded. All CVAT reads in this audit were read-only.

| Step | Command or action | Input / artifact | Result | Finding / bug | Next decision |
|---:|---|---|---|---|---|
| 1 | Inspected Git/runtime state | `outputs/runs/task_44_job_61/`, `.gitignore` | 40 frames, MOT, mapping, events, QA plan available; runtime/output excluded from Git | Existing artifacts sufficient; no inference rerun needed | Reuse locked frames and annotations |
| 2 | Read prioritized/selected events and QA plan | `review_events_prioritized.json`, `review_events_selected.json`, `qa_samples.json` | 13 events; 8 selected Issues; QA at CVAT frames 30, 31, 38 | Event contexts occupy CVAT frames 0–20 | Select flagged, QA, and unflagged windows |
| 3 | Read-only CVAT snapshot | `GET task 44`, `job 61`, annotations, Issues, comments | 14 tracks, 11 Issues, 11 comments | API success treated only as software evidence | Render actual annotation geometry on frames |
| 4 | Created audit plan | `.runtime/quality_audit/audit_plan.json` | 10 windows, each 5–8 consecutive frames | Includes 5 flagged, 2 random-QA, 3 unflagged windows | Visual inspection |
| 5 | Rendered overlays | `.runtime/quality_audit/W01_00_06.jpg` … `W10_35_39.jpg` | CVAT track and external IDs drawn from live mapping | Multiple same-object IDs and unboxed vehicles immediately visible | Inspect every window at original detail |
| 6 | Inspected W01–W05 | real frames 0–21 + live bboxes | Confirmed fragmentation, duplicates, and C162 identity reuse | Analyzer gaps are relevant; duplicate and identity diagnoses incomplete | Quantify exact overlap and track intervals |
| 7 | Calculated pairwise IoU for simultaneous boxes | locked `mot/predictions.txt` | Cross-subclass duplicate pairs: E2/E3 IoU 0.977–0.986; E4/E5 0.957; E7/E8 0.972; E3/E11 0.811–0.852; E5/E12 0.616–0.657 | Exact detector-class equality hides same-canonical-label duplicates | Highest-priority confirmed defect |
| 8 | Inspected W06–W10 | real frames 22–39 + live bboxes | C160 remains correct; blue bus, green bus, and red minibus have long missing intervals | Random QA Q1–Q3 exposes real misses | Separate detector blind spots from Analyzer errors |
| 9 | Rendered focused crops | `BUS_08_14_CROP.jpg`, `EARLY_DUPLICATES_00_04_CROP.jpg` | Same physical buses visibly carry sequential and simultaneous IDs | Known bus case confirmed as fragmentation + duplicate | Add observed golden reference |
| 10 | Read live human-readable comments | 11 CVAT comments | Reasons and anchor track present | MOT/CVAT frame off-by-one in text; related CVAT IDs absent; action text generic | Propose text, do not implement |
| 11 | Wrote audit report and regression reference | this log, `OUTPUT_QUALITY_AUDIT.md`, golden manifest | Findings separated into software, annotation, Analyzer, UX and blind spots | Evidence complete for this 40-frame sample | No feature implementation in this milestone |

## Audit window artifact checksums

| Artifact | SHA-256 |
|---|---|
| W01_00_06.jpg | `eb43f57a23769e9642f2588313f3473b280508cce438558b93a200241bffe445` |
| W02_03_10.jpg | `81aa0f02ff9f41af0153848fb9e40d950dee8a734165860ea221109681a36c8f` |
| W03_08_14.jpg | `40e54f02c88be7be029bb5257b50c6180c7f9a7d2a3431df000ff60cc8c80845` |
| W04_10_17.jpg | `2bdde0b8d626e11593bf3c4e337f4ea3a825e83d8184b33cd491e30f03985eb6` |
| W05_15_21.jpg | `7337dacbc398479fe884fe71b89360ce9ff1d6a38ce286513b836598effa16e0` |
| W06_22_26.jpg | `94b2e842d7a427448dadbf1a96afff09d03762e5e8c2e755b19ffb2322be8880` |
| W07_25_29.jpg | `206a29255c04c67e76eee7def4079ab8ffa5f407bb2e9974abcf438dc6bee44e` |
| W08_28_32.jpg | `229b076977ae86f6d5deff8ebcd1421c5e8b4aaa4e0ccf1705d3097fd8898a64` |
| W09_33_37.jpg | `e06f562c0228cebf03f9bf3e3982a2ea0a75c58719e779c93701fb9a6b4dc7e7` |
| W10_35_39.jpg | `e5f95c41ec35366da2e19b9897ac628870ee2c1b381f5810c24f978087a2df37` |
| BUS_08_14_CROP.jpg | `603596f59836572c7430dcee7039111064c5332663d098b4f2cded67f5a19314` |
| EARLY_DUPLICATES_00_04_CROP.jpg | `1b5f8d096dd6c08e95f4bb7d8b1db451dfc6e5a020addb41ab47b07e0d5b8da1` |

The JPEG overlays are visual aids, not ground truth. The report records only findings confirmed by inspecting the underlying consecutive frames; ambiguous small/blurred objects remain `UNCERTAIN`.
## 2026-10-01 — confirmed-defect fix validation

| Action | Input | Artifact inspected | Result | Finding / next decision |
|---|---|---|---|---|
| Re-run Analyzer offline with canonical compatibility | locked task44/job61 MOT, classes 2/5/7 → `vehicle` | `outputs/runs/task_44_job_61/mot/predictions.txt` | 14→19 flags; 13→18 events; 0→3 duplicate flags | All three duplicate runs match visually confirmed audit findings; live task unchanged. |
| Execute observed bus regression | E3/E11 rows at MOT 14–15 | `tests/golden_data/manifest.json` | `possible_duplicate` PASS | Keep temporal minimum of two frames and geometry thresholds unchanged. |
| Review detector coverage inputs | locked chunk checkpoints | `tools/tracking_runtime.py`, task44 `predictions/chunks` | class/confidence detections are preserved and replayed | Evidence does not justify a reliable runtime missed-object heuristic; document design only. |
| Validate Issue text/frame mapping | first/middle/last mock frames and paired tracks | `tests/test_run_cvat_pipeline.py` | CVAT 0/2/4 mapping and reason-specific actions PASS | Do not rewrite or duplicate historical live Issues. |
