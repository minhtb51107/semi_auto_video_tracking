# Semi-Auto Video Tracking — Analyzer v2 results

Implemented a separate **experimental, reference-free** analyzer and exact-interval event aggregation. Legacy analyzer/config, tracker, evaluator and prior validation artifacts remain unchanged. **33/33 tests PASS** (25 baseline + 8 new). No commit/push or next-phase integration.

## Scope and implementation

Plan written before code: `ANALYZER_V2_IMPLEMENTATION_PLAN.md`. New runtime files: `tools/review_tracks_v2.py`, `configs/review_v2.json`. Reuse v1 `load_tracks`, `load_config`, `analyze`, and compatibility writer; reuse motlib frame grouping/IoU. New tests: `tests/test_review_tracks_v2.py`. Regression runner: `tools/regress_analyzer_v2.py`. Future unsupported signals: `ANALYZER_V2_FUTURE_SIGNALS.md`.

One experimental config frozen before all four regressions: IoU≥0.75; center distance divided by smaller box diagonal≤0.10; symmetric width/height ratio≤1.35; **at least2 consecutive frames** passing all criteria. No per-sequence retuning. Missing frames or failed geometry break a run. Emit one `possible_duplicate` per maximal qualifying pair/run, with related ID, full interval, observed min/max geometry, frame count, thresholds and explanation. Anchor is the first confirmation frame (second supporting frame at defaults), not the entire run's end. This is an offline analyzer; aggregate duration/end can include frames after anchor.

User's current temporal requirement overrides the earlier design document's optional extreme-overlap singleton exception. Even identical boxes in a single frame are not sufficient. Persistent geometry can still belong to distinct vehicles; the rule does not prove physical identity.

## Regression results

Stored predictions only; no tracker inference or GT access in the runtime/regression runner. Offline issue labels below are joined from prior validation after runtime outputs exist. `outputs/analyzer_v2_regression/summary.json` records outputs and compatibility checks.

| Dataset | v1 raw flags | v2 raw flags | Runtime events | New duplicate flags | New true / false / uncertain |
|---|---:|---:|---:|---:|---|
| Internal01 (190 frames) | 27 | 27 | 20 | 0 | 0 / 0 / 0 |
| Internal02 (60 frames) | 2 | 2 | 2 | 0 | 0 / 0 / 0 |
| KITTI0001 (31 frames) | 7 | 8 | 7 | 1 | 1 / 0 / 0 |
| KITTI0000 (154 frames) | 15 | 15 | 12 | 0 | 0 / 0 / 0 |
| Total | 51 | 52 | 41 | 1 | 1 / 0 / 0 |

No new benign candidate. Zero new false/uncertain means the sole new candidate matches confirmed evidence; it is **not a reliable estimate of universal false-positive rate**. Internal sequences have no confirmed duplicate positives, not exhaustive proof that every overlapping pair is a negative.

### Confirmed duplicate evidence

| Case | Result | Explanation |
|---|---|---|
| 0001 P77/P85, f23–24, Van G93 | Captured | 2 consecutive frames; min IoU .869808, max normalized center distance .032279, max size ratio1.119650. One event, anchor24 |
| 0000 P26/P140, f99, Van G4 | Missed intentionally | IoU .995987 but only one shared frame. Temporal criterion fails; do not lower it to force this case |
| 0000 P319/P348, f144, G14 episode already targeted by legacy flags | No new duplicate flag | IoU .569837, center distance .162240; later shared frames overlap much less. No qualifying persistent run |

Thus **1/2 confirmed duplicate blind spots** is captured. If including the additional already-targeted G14 duplicate observation, **1/3 confirmed duplicate observations** is captured specifically by the new reason. Of the primary blind-spot positives, only0001 has at least two shared frames (1/1 captured); this restricted denominator must not replace the full1/2 result. The wider G14 episode is still reached by existing gap flags, but is not a successful duplicate-rule detection.

`known_duplicate_geometry.csv` keeps every shared frame for those pairs, including failures. `new_candidate_labels.csv` gives the new verdict. Preserved/copied evidence in `evidence/` includes0001 frames23/24 and0000 M002/M003. Image24 was rechecked: two red boxes lie on the same Van; the original KITTI-aware audit matches one Van distractor and leaves the duplicate unmatched. Runtime detection does not read these labels or ignore semantics.

### Known issues captured and remaining

`issue_capture.csv` is a deduplicated ledger based on previous confirmed evidence. It does not count FP/FN atoms as issues. Repeated static-ghost flags in internal01 are grouped by physical spurious track, while different gap intervals are distinct events. These counts are descriptive, not standardized cross-dataset recall.

| Dataset | Known issue units captured v1→v2 | Confirmed missed units remaining | Notes |
|---|---:|---:|---|
| Internal01 | 4→4 | 1 | Two ghost tracks and two visible-gap events still targeted; G5 switch/fragmentation at94 remains one missed cause. Old per-frame diagnostics are not new independent errors |
| Internal02 | 2→2 | 0 confirmed in prior audit | Two P9 gaps; uncertain border/continuation candidates remain unresolved |
| KITTI0001 | 3→4 | 1 | Adds duplicate; G10 missed track remains. P54 and other uncertain cases are not promoted |
| KITTI0000 | 8→8 | 4 | G12 undercoverage, singleton duplicate and two G1 splits remain; manual R009/R010 dedup preserved only in offline ledger |

The ledger's8 known caught0000 events differ from runtime event count12: runtime retains uncertain events and cannot use GT to merge the cross-ID R009/R010 handoff. No new miss-coverage or identity detector was implemented. Existing false/benign/uncertain labels are not altered.

## Event aggregation

Preserve every raw flag exactly once. Group only exact `(track_id, start_frame, end_frame, related IDs)`; no broad overlapping-window or cross-ID merge. Gap/reappeared pairs collapse **7 times in internal01, 1 in0001, 3 in0000: 11 redundant event entries removed**, 52 raw flags→41 runtime events (21.15% fewer entries). On legacy reasons alone,51→40. The new duplicate contributes one additional event. This is not time saved or lower context-frame scope: grouping preserves the same context union.

Keep `track_reappeared` as a raw reason for audit/backward compatibility and long-gap context; show it inside the same event as gap. No evidence justifies deleting or retuning it here. Event IDs and flag IDs are deterministic ordinal IDs for fixed sorted input/config, not persistent IDs across changed inputs or configurations.

## Schema and migration

- V1 command remains `tools/review_tracks.py`; original `review_flags.csv/json`, numeric observed/threshold fields, config and schema1 unchanged.
- `tools/review_tracks_v2.py --compat-v1` delegates to the same writer, refuses overwriting existing output files, and writes schema1 files. Same arguments give byte-identical CSV and JSON to v1.
- Default v2 writes **separate** `review_flags_v2.csv/json`, plus `review_events.csv/json`; JSON declares `schema_version: 2`. Do not point an old v1 CSV consumer at v2 files without adaptation.
- V2 raw flags preserve all v1 fields/values, add `raw_flag_id`, `start_frame`, `end_frame`; duplicate observed_value/threshold are structured objects (JSON strings in CSV). Legacy scalar values remain scalar. `explanation` is populated for new duplicate flags; it is empty for legacy rows in CSV.
- Events contain event_id, track_id, related_track_ids, start/end/anchor frame, reasons, raw_flag_ids, context_start/end. Lists are JSON in CSV. No raw flags removed.
- Frames are1-based. Pass `--total-frames` from video metadata to clip context at the final frame. Without it, upper context is explicitly unbounded; do not infer video length from last prediction or GT.
- V2 output refuses overwrite. Use a fresh directory for another experiment; no migration rewrites prior artifacts.

## Commands

Run from project root, using a fresh output directory:

```powershell
.venv\Scripts\python.exe -X utf8 tools/review_tracks_v2.py --tracks outputs/external_validation/kitti_0001/tracks.txt --total-frames 31 --out-dir outputs/my_v2_review
.venv\Scripts\python.exe -X utf8 tools/review_tracks_v2.py --tracks outputs/external_validation/kitti_0001/tracks.txt --compat-v1 --out-dir outputs/my_v1_compatible_review
.venv\Scripts\python.exe -X utf8 -m unittest discover -s tests -v
```

`tools/regress_analyzer_v2.py` is the four-dataset runner used for this report. It refuses an existing summary/dataset destination to protect evidence; it is not an overwrite/restart command. Full frozen results already exist in `outputs/analyzer_v2_regression/`. To rerun an individual case, use the runtime commands above with a fresh output path; do not rerun tracker.

## Verification and acceptance

All25 old tests plus8 new tests pass: persistent duplicate observations; nearby distinct boxes, crossing/short overlap; missing-frame reset and entry/exit; split runs and permutation determinism; gap/reappearance grouping/membership/context bounds; invalid configs/empty inputs; exact geometry boundary/size mismatch; CLI in a temporary workspace with no GT and byte-compatible output/no overwrite. Test log: `outputs/analyzer_v2_regression/tests.log`. Expected invalid-video FFmpeg message belongs to a negative existing test.

Compatibility regression compared same-argument v1/compat bytes and exact legacy flag projection within v2 for all four datasets. Original stored CSV bytes also match. External stored JSON originally used absolute input path spelling; the initial relative-path regression differs only in that metadata field. Additional `exact_original_path_compat/` checks use original input_file spelling to establish byte-for-byte equality to all four historical JSON/CSV artifacts.

`preservation_before.json` snapshots1,614 pre-existing artifact/source/doc files before implementation. `integrity_final.json` verifies those bytes and frozen runtime/config hashes; no old validation artifact was rewritten. Default configuration was not changed after observing results.

**Acceptance status: implementation/compatibility/aggregation PASS; duplicate feature EXPERIMENTAL, general effectiveness gate NOT ESTABLISHED.** The temporal rule captures the persistent confirmed pair and emits no extra candidates on the four available datasets, but misses the singleton and less-aligned G14 case. This is conservative limited coverage, not a proven robust duplicate detector. The earlier independent≥20-event precision/uncertainty gate is not met with one new candidate. No tuning was attempted to raise regression recall.

**Not ready to approve operational Human-in-the-loop/CVAT integration on this evidence alone.** Next: independent review, hard negative pairs with persistent overlap, and a new held-out sequence with frozen settings. Missed objects, ambiguous identity, long-gap fragmentation and stable wrong boxes remain limitations. Manual research review may use the exported events, but no CVAT phase, auto-correction or deployment starts automatically.
