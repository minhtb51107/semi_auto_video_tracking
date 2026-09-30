# Output Quality Audit — CVAT task 44 / job 61

Audit date: 2026-09-30. This is a visual audit of 40 real consecutive frames and the live CVAT annotations, not an inference from API counts. Frame numbers below are **CVAT 0-based** unless explicitly marked MOT 1-based.

## Audit taxonomy

- `CORRECT_TRACK`: the same physical object keeps one identity through the inspected interval.
- `FRAGMENTATION`: one physical object is split across multiple track IDs over time.
- `ID_SWITCH`: one track ID changes from one physical object to another.
- `DUPLICATE_TRACK`: simultaneous tracks represent the same physical object.
- `MISSED_DETECTION`: a clearly visible in-scope object has no bbox.
- `WRONG_CLASS`: an annotation exists with the wrong semantic class.
- `FALSE_ALERT`: an Analyzer Issue has no relevant visual problem.
- `UNCERTAIN`: image evidence is insufficient for a confident decision.

## Evidence and method

The audit used the live annotation snapshot (14 tracks, 11 Issues/comments), the 40 downloaded task frames, CVAT track IDs, locked external→CVAT mapping, Analyzer events, and spatial overlays. Ten consecutive windows of 5–8 frames were inspected. Three were deliberately outside Analyzer event contexts; two cover the three deterministic random-QA samples.

Generated overlays remain local under `.runtime/quality_audit/`. Important evidence hashes:

- `BUS_08_14_CROP.jpg`: `603596f59836572c7430dcee7039111064c5332663d098b4f2cded67f5a19314`
- `EARLY_DUPLICATES_00_04_CROP.jpg`: `1b5f8d096dd6c08e95f4bb7d8b1db451dfc6e5a020addb41ab47b07e0d5b8da1`
- W01–W10 hashes are recorded in `OUTPUT_QUALITY_AUDIT_EXECUTION_LOG.md`.

## Audit plan and visual findings

| Window | CVAT frames | Selection | Related CVAT / external tracks | Events / reasons / severity | Visual findings and recommended action |
|---|---:|---|---|---|---|
| W01 | 0–6 | flagged, low/medium/critical context | C158–C166 / E1–E9 | E001–E008 contexts | `DUPLICATE_TRACK`: colorful bus has C159/E2 + C160/E3 simultaneously at 0–2 and 4; C164/E7 + C165/E8 at 3. A left vehicle has C161/E4 + C162/E5 at 0–1. `FRAGMENTATION`: colorful bus changes IDs. Analyzer flags gaps but misses all simultaneous duplicates. Human should retain one identity per physical object and remove duplicate shapes. |
| W02 | 3–10 | flagged gaps | C158–C160, C164–C166 / E1–E3, E7–E9 | E003, E006–E010 and low gaps | `FRAGMENTATION`: colorful bus changes C164/C165 → C160; blue bus alternates C158/C166 and has uncovered frames. Gap alerts are relevant, but do not explain the full multi-ID chain. |
| W03 | 8–14 | known bus case | C158, C160, C162, C165–C169 / E1, E3, E5, E8–E12 | E003 CRITICAL; E009–E011 MEDIUM; gaps | `FRAGMENTATION` and `DUPLICATE_TRACK` confirmed for the colorful bus; blue bus also fragments and is duplicated at frame 14. C162/E5 reappears on a different physical object, an `ID_SWITCH`/false continuation. Correct identities should be consolidated manually. |
| W04 | 10–17 | flagged fragmentation | C160, C162, C167–C170 / E3, E5, E10–E13 | E009–E012 MEDIUM, E003 CRITICAL | Analyzer correctly suspects several fragmentation transitions. It misses simultaneous colorful-bus duplicate C160+C168 at 13–14 and blue-bus duplicate C162+C169 at 14–15. |
| W05 | 15–21 | flagged tail | C160, C162, C169, C170 / E3, E5, E12, E13 | E011–E013 | `FRAGMENTATION`: blue bus alternates C169→C170→C169, then stays clearly visible without a bbox from frame 19. C160 is a `CORRECT_TRACK` for the colorful bus in this window. |
| W06 | 22–26 | unflagged | C160/E3 | none | C160 correctly follows the colorful bus. `MISSED_DETECTION`: the clearly visible blue/white bus at left has no bbox. A small center three-wheeler is visible but its expected taxonomy is `UNCERTAIN`. |
| W07 | 25–29 | unflagged | C160/E3 | none | C160 remains correct. `MISSED_DETECTION`: blue bus remains unboxed; another green bus enters from the left around 28–29 without a bbox. |
| W08 | 28–32 | random QA Q000001/Q000002 | C160/E3 | RANDOM_QA | Random QA exposes real blind spots: the green bus and blue/white bus at left are unboxed; a red minibus behind/right of the colorful bus is also visible without a bbox. No Analyzer event covers them. |
| W09 | 33–37 | unflagged | C160/E3, C171/E14 | none | C160 remains correct. Green bus is unboxed at 33–36, receives only one C171 shape at 37, and stays visible afterward. Red minibus remains unboxed. |
| W10 | 35–39 | random QA Q000003 | C160/E3, C171/E14 | RANDOM_QA | `FRAGMENTATION`/short-lived coverage: green bus has C171 only at 37 despite visibility at 35–39. `MISSED_DETECTION`: red minibus and blue/white bus remain visible without boxes. Random QA is useful here. |

## Known bus case: CVAT frames 8–14

The colorful bus is one physical object with these relevant identities:

| CVAT track | External track | First–last visible in task | Presence in frames 8–14 | Interpretation |
|---:|---:|---:|---|---|
| 165 | 8 | 3–8 | frame 8 | same colorful bus |
| 160 | 3 | 0–39 | frames 9–14 | same colorful bus |
| 168 | 11 | 13–14 | frames 13–14 | same colorful bus |

The identity changes from C165 at frame 8 to C160 at frame 9, so this is confirmed `FRAGMENTATION`. C160 and C168 overlap on the same bus at frames 13–14 (IoU 0.811 and 0.852), so those frames also contain a confirmed `DUPLICATE_TRACK`. It is not an ID switch among these three IDs because none is shown moving to a different physical object in this interval.

Event E000009 (`possible_fragmentation`, C168/E11 related to E8/C165, MEDIUM) points to the correct physical bus but skips the intervening C160/E3 identity and does not report the simultaneous duplicate. The alert is therefore relevant but incomplete. This case is now an `OBSERVED_RULE_FIXTURE` golden regression: it uses only four audited MOT geometry rows, links to this visual evidence, and does not claim synthetic or automated ground truth.

Post-fix offline validation is recorded in `OUTPUT_QUALITY_FIX_VALIDATION.md`. Canonical `vehicle` compatibility surfaces the confirmed C160/E3 + C168/E11 duplicate while retaining the existing persistence and center-consistency safeguards. The live task and its historical Issues were not mutated.

The blue/white bus in the same window also changes C166→C158→C167→C162/C169. C162/E5 previously represented a different left-side vehicle at frames 0–2, then represents the blue bus from frame 12. E000003 catches its long gap/reappearance but does not state the actual `ID_SWITCH`/false continuation.

## Analyzer versus visual findings

| Window/group | Human finding | Analyzer flagged? | Analyzer reason | Correct alert? | Missed error? | Severity appropriate? | Notes |
|---|---|---|---|---|---|---|---|
| W01 main bus | duplicate + fragmentation | partial | several gaps | yes, for discontinuity | duplicate missed | gaps LOW/MEDIUM reasonable | class IDs 5 and 7 suppress duplicate comparison although both map to CVAT `vehicle` |
| W01 left vehicle | duplicate C161+C162 | no | none | — | yes | — | IoU 0.957 at frames 0–1 |
| W03 C162 | ID switch/false continuation | yes | gap + reappeared | relevant anomaly, wrong diagnosis | identity error not named | CRITICAL appropriate | same ID changes physical object |
| W03/W04 colorful bus | fragmentation + duplicate | partial | possible fragmentation + gaps | yes | simultaneous duplicate missed | MEDIUM for fragmentation; duplicate absent | E009 omits C160 from chain |
| W03/W04 blue bus | fragmentation + duplicate | partial | E010/E011 fragmentation | yes | C162+C169 duplicate missed | MEDIUM reasonable | duplicate IoU 0.657/0.616 at frames 14–15 |
| W05 blue bus | fragmentation then missing | yes/partial | E012/E013 | yes | continued absence after 19 missed | MEDIUM/LOW reasonable | Analyzer has no detector-level coverage signal |
| W06–W10 | visible unboxed vehicles | no | none | — | yes, detector blind spot | — | random QA reveals these cases |
| W09/W10 green bus | one-frame track amid long visibility | no | none | — | yes | — | C171 exists only at frame 37 |

Event-level result on the 13 Analyzer events covered by W01–W05:

- confirmed relevant alerts: **13/13**;
- false alerts: **0/13**;
- live prioritized Issues inspected: **8**, all relevant;
- completely missed tracking issue groups: **3** — cross-subclass duplicates on the colorful bus, cross-subclass duplicates on the blue/left vehicles, and the one-frame green-bus fragment;
- partially surfaced but misclassified: **1** — C162 identity switch described only as gap/reappearance;
- confirmed detector-level missed-object intervals: **3** — blue/white bus (19–39), green bus (mostly 28–39), red minibus (approximately 29–39).

These are descriptive counts for one 40-frame sample, not statistically significant metrics. Multiple events often describe the same physical root problem, so 13 relevant alerts do not mean 13 independent errors.

No `WRONG_CLASS` was confirmed at the CVAT label level: inspected boxes are vehicles and use label `vehicle`. Detector subclass instability (`bus` versus `truck`) is real, but both subclasses intentionally map to the same CVAT label.

## A. Software correctness

The prior integration evidence remains valid: task/job mapping, append-only push, read-back, idempotency, and annotation hash checks passed. The audit snapshot read 14 live tracks and 11 Issues. These facts prove transport and state integrity only; they do not prove annotation quality.

## B. Annotation quality

The main colorful bus is ultimately stable as C160 through much of the clip, but early frames contain duplicate and fragmented identities. The blue bus is heavily fragmented, one ID is reused for another object, and coverage stops while the bus remains visible. Later non-flagged windows contain several clearly visible vehicles without boxes. No confident wrong CVAT class was found.

## C. Analyzer quality

Gap and fragmentation alerts consistently point to real continuity problems. The largest confirmed defect is that duplicate detection compares exact detector subclasses rather than configured canonical/CVAT compatibility. Car/bus/truck predictions all map to `vehicle`, yet class 5 versus class 7 pairs are excluded; this directly hides IoU 0.81–0.99 duplicate boxes.

Analyzer also lacks a signal for one-frame/short-lived tracks and for objects that receive no detection. The latter is a detector-level limitation and should not be disguised as something the current MOT-only Analyzer can solve.

## D. UX quality

The current Issues answer what is suspected and give the anchor CVAT track, context, reason, and generic action. They are not fully actionable:

1. Comments display MOT 1-based `Anchor frame`/`Review context`, while the Issue marker and CVAT UI use 0-based frames. Example: E000009 says anchor 14 but opens CVAT frame 13.
2. Fragmentation comments show related **external** IDs but omit related CVAT track IDs.
3. Suggested action is identical for every reason and does not say which tracks to compare or what decision to make.
4. E000003 cannot explain that pre-gap and post-gap boxes belong to different physical objects.

Proposed text, for a future implementation after this audit:

- **Fragmentation:** “Possible fragmentation. Compare CVAT tracks C165 and C168 (external E8/E11) across CVAT frames 7–15. Decide whether they are the same physical object; if yes, consolidate identity manually.”
- **Duplicate track:** “Possible duplicate. CVAT tracks C160 and C168 overlap on the same object at CVAT frames 13–14. Retain one track only if visual inspection confirms duplication.”
- **Track gap:** “Track C158 is absent for CVAT frames 6–8 while the object may remain visible. Inspect continuity; fill missing shapes or split the track if the object left/was fully occluded.”
- **Reappearance:** “Track C162 resumes at CVAT frame 12 after a 9-frame gap. Compare the last pre-gap and first post-gap objects; decide same identity versus false continuation.”
- **Identity conflict:** “Track C162 may represent different physical objects before and after the gap. Inspect CVAT frames 0–2 and 12–15; split/reassign the post-gap segment if identities differ.”

All future comments should label numbers explicitly as `CVAT frame` and include both CVAT and external IDs.

## E. Known blind spots

- Cross-subclass vehicle duplicates are suppressed even when both detector classes map to canonical `vehicle`.
- Track reuse after a long gap can be surfaced without being correctly diagnosed as an identity switch.
- A one-frame track that disappears while the object remains visible is not flagged.
- Completely missed objects cannot be recovered from tracker output alone.
- Privacy blur and small/distant road users create genuinely uncertain cases; motorcycles are outside the current `[2,5,7]` vehicle mapping.
- This audit covers one short clip and one visual reviewer; it is not a benchmark.

## Prioritized confirmed defects

1. **Duplicate suppression uses detector subclass rather than canonical label compatibility.** Evidence: same physical buses have simultaneous IoU 0.811–0.986 boxes with class IDs 5 and 7, with no `possible_duplicate`. Root cause: exact `class_id` equality guard. Proposed fix: compare configured canonical/CVAT label identity, retain safe legacy fallback, and add this observed case as regression evidence. Expected benefit: surface severe duplicate annotations now missed. Regression risk: more alerts where adjacent different vehicle subclasses overlap; temporal persistence and center consistency must remain required.
2. **Detector coverage leaves clearly visible vehicles unannotated.** Evidence: blue bus frames 19–39, green bus mostly 28–39, and red minibus around 29–39. Root cause: detection-driven architecture and class/confidence/domain limits. Proposed next step: preserve detector-before-tracker/drop history and design a reference-free coverage audit; do not invent a tracker-only false-negative rule. Expected benefit: expose missing annotations. Regression risk: high false-alert rate in blur/occlusion and extra compute.
3. **Issue comments use ambiguous frame numbering and incomplete identity context.** Evidence: E000009 comment says anchor 14 while the live marker is CVAT frame 13; related CVAT track is absent. Root cause: Analyzer MOT numbering is rendered directly. Proposed fix: render explicit CVAT frame/context and both CVAT/external IDs with reason-specific action text. Expected benefit: faster, safer reviewer decisions. Regression risk: off-by-one regressions unless mapping tests cover first/middle/last frames.
