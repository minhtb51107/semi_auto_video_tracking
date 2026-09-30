# Live Fix Verification

Validation date: 2026-10-01. Code under test: commit `6295e39e1dd805ceeb7ba0d4ce7707ae6e6a911b`.

This is a controlled live verification of the canonical-label Analyzer fix and CVAT Issue comment fix. It reuses a short traffic sequence with known cross-subclass duplicates; it is not an independent accuracy benchmark. Prior evidence tasks 20, 21, 38, and 44 were not mutated.

## A. Target

| Field | Value |
|---|---|
| CVAT task | 45 |
| CVAT job | 62 |
| Task name | `SATV2-LIVE-FIX-20261001-004743` |
| Frame count | 40 consecutive JPEG frames, CVAT 0–39 |
| Source | locked downloaded frames from task44/job61 workspace |
| Source inventory SHA-256 | `bfef2f34e1886c507991b190805bdb8b4c2e4fd2be67c1cb6aa202dd7ef645c1` |
| CVAT labels | rectangle `vehicle` (ID 221) |
| Canonical mapping | detector classes 2, 5, 7 → `vehicle` |

Dry-run reported an empty annotation state, supported `vehicle` mapping, zero unsupported labels, and `annotation_safety: PASS`. It did not download frames, run inference, or mutate CVAT.

The live run produced 105 detector detections, 72 predicted boxes, 14 external/CVAT tracks, 19 raw flags, 18 review events, 3 `possible_duplicate` flags, 6 `possible_fragmentation` flags, and 21 CVAT Issues (18 selected review events plus 3 random-QA samples). CVAT read-back returned 14 tracks, 94 total track shapes including boundary/outside shapes, 21 Issues, and 21 comments.

## B. Canonical duplicate live validation

All three live duplicate alerts compare different detector subclasses that map to canonical/CVAT `vehicle`:

| Event | External tracks | CVAT tracks | Detector classes | CVAT frames | Frame IoUs | Visual verdict |
|---|---|---|---|---|---|---|
| E000002 | E2 + E3 | C173 + C174 | 7 + 5 | 0–2 | 0.986, 0.980, 0.977 | `TRUE_ALERT`: both tracks cover the same colorful bus |
| E000001 | E4 + E5 | C175 + C176 | 2 + 7 | 0–1 | 0.957, 0.957 | `TRUE_ALERT`: both tracks cover the same left-side vehicle |
| E000016 | E3 + E11 | C174 + C182 | 5 + 7 | 13–14 | 0.811, 0.852 | `TRUE_ALERT`: both tracks cover the same colorful bus |

Result: **3 TRUE_ALERT, 0 FALSE_ALERT, 0 UNCERTAIN** among live `possible_duplicate` events. These verdicts come from visual inspection of the live task45 frames with the live CVAT track read-back overlaid; they are not inferred from IoU alone. The two-frame persistence, center-distance, size-ratio, and IoU safeguards remained active.

## C. Visual windows and Issue UX

Four consecutive-frame windows were rendered from the downloaded task45 frames and live annotation read-back:

| Window | CVAT frames | Visual finding | Analyzer usefulness |
|---|---:|---|---|
| L01 | 0–4 | Colorful bus has C173/E2 + C174/E3 simultaneously; left vehicle has C175/E4 + C176/E5 | Both duplicate Issues are correct and name both tracks |
| L02 | 5–10 | Same colorful bus transitions from C179/E8 to C174/E3 | Fragmentation/gap context is useful for continuity review |
| L03 | 11–16 | Colorful bus has C174/E3 + C182/E11 simultaneously at 13–14; blue bus changes identities | Duplicate and fragmentation alerts are visually relevant |
| L04 | 17–21 | C174/E3 remains stable on the colorful bus; blue bus coverage ends while it remains visible | Continuity context is useful; the later missing boxes remain an out-of-scope detector coverage defect |

Live read-back confirmed exact equality between remote and planned comments for a duplicate, a fragmentation, and a combined gap/reappearance event:

- Duplicate E000002 identifies `CVAT 173 / external 2` and `CVAT 174 / external 3`, says `CVAT anchor frame: 1`, gives context 0–4, and asks the reviewer to decide whether they are different physical objects.
- Fragmentation E000015 identifies `CVAT 184 / external 13` and `CVAT 181 / external 10`, gives CVAT context 9–18, and asks whether to consolidate physical identity.
- Gap/reappearance E000005 identifies `CVAT 176 / external 5`, gives CVAT context 0–14, and separates a continuity check from the pre-gap/post-gap identity check.

No human-facing line presents an MOT 1-based value as a CVAT frame. Raw MOT fields remain only in structured `METADATA_JSON`. All three duplicate Issues used `ANCHOR_BBOX_CENTER`; remote frames/positions matched the plan and every marker lay inside its relevant primary bbox.

## D. Idempotency

First live run:

- annotation tracks created: 14; skipped: 0;
- Issues created: 21; skipped: 0;
- annotation read-back verified and unchanged during Issue push.

Exact second invocation:

- annotation tracks created: 0; existing tracks recognized/skipped: 14;
- Issues created: 0; existing Issues recognized/skipped: 21;
- inference workspace resumed: frame fetch 0.103 s, inference replay 0.034 s;
- annotation hash remained `2c2ad2027c485fc3fb18817470b0c4e7bdc27a8f841b5ae4608bcdea2df1979c`;
- remote state remained 14 tracks, 21 Issues, and 21 comments.

No human annotation was overwritten. No confirmed live defect required a source change.

## E. Live status matrix

| Capability | Status | Evidence |
|---|---|---|
| Canonical duplicate compatibility | `LIVE_VERIFIED` | Three class 2/5/7 cross-subclass pairs evaluated as canonical `vehicle` |
| Cross-subclass duplicate detection | `LIVE_VERIFIED` | Three live alerts, all visually confirmed |
| Issue CVAT-frame rendering | `LIVE_VERIFIED` | Remote duplicate/fragmentation/gap comments use verified CVAT frame map |
| Related CVAT/external IDs | `LIVE_VERIFIED` | Remote paired comments contain both identity namespaces |
| Reason-specific Issue actions | `LIVE_VERIFIED` | Duplicate, fragmentation, continuity, and identity instructions read back exactly |
| Issue marker positioning | `LIVE_VERIFIED` | Three duplicate markers match remote payload and lie inside anchor bboxes |
| Idempotency | `LIVE_VERIFIED` | Second run created 0 tracks and 0 Issues |
| Post-human resolution preservation | `NOT_YET_LIVE_VERIFIED` | All 21 disposable Issues remain unresolved; manual action was not fabricated |

For optional resolution verification, open `http://localhost:8080/tasks/45/jobs/62?frame=1`, resolve Issue 278, then rerun read-back/final validation. This optional action is not required for the canonical/UX fix acceptance above.
