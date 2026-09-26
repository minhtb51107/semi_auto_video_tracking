# Semi-Auto Video Tracking — External validation comparison

Hai lần blind run giữ nguyên YOLO26n, ByteTrack, analyzer và config. KITTI preprocessing adapter cùng hash/policy. Nguồn số liệu: các `validation_summary.json`, raw `evaluation.json`, `kitti_semantics/evaluation.json`, verdict CSV và ảnh; chi tiết trong EXTERNAL_VALIDATION_RESULTS.md, KITTI_EVALUATION_RESULTS.md và EXTERNAL_VALIDATION_02_RESULTS.md. Không thay nhãn hay artifacts0001 để làm đẹp so sánh.

## Counts và review

| Quantity | KITTI0001 | KITTI0000 |
|---|---:|---:|
| Frames | 31 | 154 |
| Raw target boxes / tracks (Car+Van) | 247 / 15 | 535 / 12 |
| Eligible Car boxes / tracks | 203 / 14 | 215 / 9 |
| Predicted boxes / tracks | 228 / 22 | 534 / 27 |
| Raw flags | 7 | 15 |
| Flagged frames | 6 | 12 |
| Review events | 6 | 11 |
| Raw TRUE / BENIGN / FALSE / UNCERTAIN | 3 / 2 / 0 / 2 | 11 / 0 / 0 / 4 |
| Event TRUE / BENIGN / FALSE / UNCERTAIN | 3 / 2 / 0 / 1 | 8 / 0 / 0 / 3 |
| Confirmed missed events, deduplicated | 2 | 4 |
| Strict wholly missed track confirmed | 1 (G10) | 0 under that strict definition |
| Additional severe track undercoverage confirmed | 0 separately classified | 1 (G12: raw0/24 CLEAR; eligible0/18) |
| Confirmed missed duplicates | 1 (P77/P85, G93 Van) | 1 (P26/P140, G4 Van) |
| Confirmed missed fragmentation/ID replacement events | 0 | 2 (G1, same Van at two transitions) |
| Caught fragmentation | 0 | 1 (G1 P112→P322) |
| Raw pred→multiple-GT association conflicts | 1 (P54) | 3 (P187/P229/P331) |
| Adjusted pred→multiple-GT conflicts | 0 | 3 |
| Confirmed physical ID reuse events | 0; P54 uncertain | 2, both caught (P187/P229) |
| Anchor candidate scope | 6/31 = 19.35% | 12/154 = 7.79% |
| Context review scope (whole gap ±2) | 26/31 = 83.87% | 69/154 = 44.81% |
| Potential review reduction with context | 16.13% | 55.19% |

0000 initially has12 track/interval groups; R009/R010 describe one G14 handoff and become one adjudicated event. Gap+reappeared pairs are also deduplicated. Two incoming reused IDs at145 and148 remain distinct events. Five G4 interruptions remain separate gaps. Raw flags, review events and confirmed issues are different units.

The four missed0000 events are a conservative confirmed subset, not all FP/FN or an exhaustive count of physical errors. G12 may be visible inside another event's context but is not targeted by analyzer. No human timing was measured; scope reduction is not time saved. Class policy matters: six of eight true0000 events and two missed splits concern Van, whereas KITTI Car scoring treats Van as distractor.

## Metrics

| Metric | 0001 raw | 0001 KITTI-aware | 0000 raw | 0000 KITTI-aware |
|---|---:|---:|---:|---:|
| HOTA | .5193 | .5909 | .4400 | .4794 |
| DetA | .4145 | .4975 | .4933 | .4684 |
| AssA | .6589 | .7112 | .3952 | .5101 |
| LocA | .7988 | .8067 | .7708 | .7328 |
| IDF1 | .7074 | .7966 | .5650 | .6172 |
| MOTA | .4453 | .6502 | .5140 | .4047 |
| MOTP | .7586 | .7676 | .7318 | .6885 |
| FP | 59 | 7 | 124 | 53 |
| FN | 78 | 64 | 125 | 65 |
| IDSW | 0 | 0 | 11 | 10 |

These are project metric implementations, **not official KITTI scores**. Raw tracks Car+Van; adjusted tracks eligible Car. Different GT denominators and scene/class mix prohibit attributing raw→adjusted change to a better tracker. In0000 adjusted MOTA decreases while association metrics improve. In0001 adjusted metrics mostly improve.

| Preprocessing count | 0001 | 0000 |
|---|---:|---:|
| Matched Van predictions ignored | 11 | 244 |
| Matched invalid Car predictions ignored | 19 | 16 |
| Unmatched DontCare-qualified predictions | 50 | 70 |
| Unmatched small-box-qualified predictions | 50 | 4 |
| Intersection of previous two | 48 | 3 |
| Total predictions removed | 82 | 331 |
| Marginal FP reduction from DontCare with small-box still on | 2 | 67 |

This is strong evidence that ignore semantics cannot be replaced by a blanket FP subtraction or one threshold learned on0001. A duplicate on Van survives as the second unmatched box in **both** sequences, despite the first box being removed as distractor.

## Repeated evidence and limits

| Observation | Repeated? | Engineering implication |
|---|---|---|
| Gap flags identify visible annotation omissions | Yes: G6/0001, G4/0000 | Keep track_gap; do not tune from these two clips |
| track_reappeared adds a reason but no new event beyond gap | Yes: 1/1 flags in0001; 3/3 in0000 | Reference-free event consolidation is justified; keep raw reasons |
| Entirely absent/very poorly covered target remains unflagged | Yes at coverage-problem level: G10 vs G12 | A blind spot, but an unseen target cannot be inferred reliably from MOT alone |
| Duplicate predicted IDs on same physical vehicle | Yes, confirmed in both | Sufficient evidence to plan a possible_duplicate candidate rule using simultaneous box pairs |
| Physical identity merge/reuse missed in both | Not established | P54 uncertain and excluded by adjusted policy; P187/P229 confirmed but already caught; P331 uncertain |
| Missed long-gap fragmentation | Confirmed only in0000 | Research candidate, not a replicated basis for a new runtime rule yet |
| Stable localization error / semantic ghost | Not confirmed across both | Do not invent dedicated rules from raw FP/FN |

Confidence **increases** in reproducibility, usefulness of gap review and existence of the duplicate/coverage blind spots. Confidence **decreases** in using the current review list as an exhaustive quality gate. Two sequences do not establish universal precision/recall or physical identity correctness. No threshold change is justified now.

## Decision

**ANALYZER_V2_READY = YES, narrowly scoped to planning.** At least one actionable blind spot (duplicate) is independently visible in two external sequences and has reference-free signals already in MOT. Event/reason consolidation also has repeated evidence. See [ANALYZER_V2_PLAN.md](ANALYZER_V2_PLAN.md); no v2 implementation occurred.

Before implementing/tuning broader identity or coverage rules, sequence#3 should contain sustained dense Car traffic, clearly separable identities before/after occlusion, true close-by distinct cars as duplicate negatives, entry/exit and camera motion. Prefer >200 frames with complete images/GT, and preregister selection/thresholds before reading semantic labels. Add independent annotation review and retain all uncertain cases. This is a proposed next experiment, not a new download authorization exercised in this phase.
