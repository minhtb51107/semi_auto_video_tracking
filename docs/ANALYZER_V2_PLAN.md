# Semi-Auto Video Tracking — Analyzer v2 plan only

**ANALYZER_V2_READY = YES — limited design gate, not implementation approval or a completed v2.** Two external sequences support a duplicate blind spot and redundant gap/reappearance event reporting. No analyzer, tracker, threshold, model or adapter change was made in this phase.

Evidence is preliminary and scoped to vehicle annotation; Van distractor status in Car evaluation does not make two annotations on one Van legitimate. None of the proposed runtime paths may consume GT, converted GT, KITTI ignore labels, matched GT identity, evaluation metrics or validation verdicts. GT is permitted only for offline testing and adjudication. A reason remains a heuristic review candidate, never ground truth or auto-correction.

## Candidate 1 — possible_duplicate

**Problem:** two simultaneous predicted IDs annotate the same physical vehicle; current single-track continuity rules can remain quiet because each box is geometrically plausible.

**0001 evidence:** P77/P85 on G93 Van, frames23–24. One prediction is removed by Van matching, second remains two adjusted FP; images and issue event in preserved0001 outputs.

**0000 evidence:** P26/P140 on G4 Van, frame99, U002. Both GT IoU>0.71, near-identical geometry, DontCare IoA0; one unmatched duplicate survives adapter. M002/M025 are one event. The G14 overlapping-box episode provides an additional caught context, not an extra independent missed positive.

**Available runtime signals:** frame, ID, x/y/w/h, simultaneous pairwise IoU, intersection/minimum-area, normalized center distance, width/height ratios, track age and overlap duration from MOT. No GT required. Class is absent in current MOT, so do not assume a class-aware rule. Do not add ReID or a model.

**Proposal:** evaluate different-ID pairs coexisting in a frame, retain very high-overlap/near-identical geometry as a possible-duplicate candidate; group consecutive evidence by unordered ID pair into one event. Use surrounding trajectory consistency when available. Permit a separately marked extreme-overlap singleton candidate: requiring two frames unconditionally would miss U002. Duration/geometry parameters must be explicitly experimental config; this plan does not set or apply tuned values. Output both involved IDs, interval, observed geometric statistics and candidate threshold; keep original raw boxes unchanged.

**Expected benefit:** surface duplicate events missed in both samples with existing signals; prioritize review rather than claim identity equivalence.

**False-positive risks:** distinct overlapping vehicles in queues, overtaking/crossing, partial occlusion and amodal boxes; one large box surrounding another; camera motion; coincident detections at an ID handoff. High IoU alone is not physical proof. KITTI DontCare labels cannot be used as a production filter; unlabeled background vehicles can also be legitimate.

**Tests:** actual U002 and0001 duplicate fixtures; same-ID pair excluded; unordered pair symmetry; deterministic ordering; exact threshold boundaries; duplicate one-frame vs multi-frame grouping; nonoverlapping tracks; distinct cars with overlapping/amodal boxes; crossing cars; edge truncation; equal boxes on different frames; empty/single track input. Ensure existing gap/reappearance/fragmentation outputs remain reproducible. Reference-free execution test must work with all GT files absent.

**Proposed acceptance criteria (product gates, not calibrated findings):** detect both preserved confirmed duplicate events as two event-level regression positives without altering old raw artifacts; report event precision, confirmed recall on adjudicated positives, uncertain fraction, false events per1000 frames and added context scope on a new held-out sequence. Seek resolved event precision≥0.70 and uncertainty≤0.20 on at least20 independently adjudicated proposed events, with negatives including true overlapping vehicles; disclose numerator/denominator and uncertainty intervals. If evidence volume is insufficient, status remains exploratory rather than declaring the target met. Limit added candidate review scope to a proposed ≤10 percentage points on that new set and report misses caused by the limit. No threshold tuning against that final held-out evaluation.

## Candidate 2 — consolidate reasons into review events

**Problem:** gap and reappeared describe the same interval, inflating raw warning counts and reviewer workload if treated as separate issues.

**0001 evidence:** P64 gap/reappearance is one uncertain event (two raw flags).

**0000 evidence:** P152, P187, P229 each emit both reasons for one gap. Fifteen raw flags become12 mechanical groups. Additional R009/R010 handoff merging needed GT/visual adjudication; do **not** silently assume that broader merge is safe at runtime.

**Available signals/reference needs:** existing track ID, previous/current frame and related ID fields; no GT required for exact same-track/interval grouping.

**Proposal:** preserve raw reasons and values; add a deterministic event layer keyed by track and interval, retain all original flag IDs, list reasons once, expose context bounds. Automatically merge only exact shared-interval gap/reappeared pairs initially. Distinct gaps, different tracks and merely overlapping time windows remain distinct. Cross-ID handoff merging stays manual/research until there is reference-free evidence strong enough to justify it.

**Expected benefit:** eliminate double counting without hiding alerts or claiming improved error detection. Current validation-only event CSV is evidence for the design, not a changed production analyzer.

**False-positive/false-negative risks:** over-merging different causes, losing per-reason evidence, changing stable ordering or links. Exact-interval grouping is deliberately limited.

**Tests:** two reasons share one event, distinct intervals remain separate, different tracks remain separate, input permutation determinism, no lost/duplicated flag membership, context clipping at sequence boundaries, links back to raw observed_value/threshold. No GT directory should be required.

**Acceptance criteria:** all raw flags retained exactly once;0001 yields6 mechanical events from7 flags and0000 yields12 from15; event ordering stable; detected unique error set unchanged. Do not use the manually merged11 count as a runtime regression target, since that needs visual identity judgment. Measure human navigation cost later; no time-saved claim from counts alone.

## Blind spots not promoted to runtime rules

| Problem | Evidence | Current signal sufficiency | Decision |
|---|---|---|---|
| Whole-track absence / severe undercoverage | G10/0001 and G12/0000 | MOT cannot expose an object never emitted; presence of neighboring tracks is not proof | **NOT_RUNTIME_DETECTABLE_WITH_CURRENT_SIGNALS** for reliable never-detected-object detection. Document residual manual coverage requirement; do not propose a GT lookup runtime rule |
| Long occlusion fragmentation | G1 P1→P73 and P73→P112 only0000 | Endpoint geometry/time exists, but camera motion and long gaps make identity uncertain | Defer rule expansion; get independent repeated cases and hard entry/exit negatives first |
| Pred→multiple-GT identity conflict | P54/0001 uncertain/ignored; P187/P229/0000 caught; P331 uncertain | Multiple GT ownership is evaluation-only; it cannot itself be a runtime feature | Do not implement a GT-based merge detector. Gap endpoint geometry can be investigated later, without assuming proof from one confirmed sequence |
| Large localization/ghost | Low-IoU and no-owner candidates confounded by truncation, occlusion and DontCare | Smooth but wrong boxes may contain no abnormal MOT signal | Do not convert FP/FN into runtime reasons; evidence insufficient |

## Next experiment and controls

Obtain independent visual adjudication of both duplicate cases and ambiguous identity/coverage cases. Freeze rule specification and any development config before external#3 GT access; include dense overlapping Car negatives, >200 consecutive frames if practical, full labels and significant entry/exit/occlusion. Keep raw evaluator and KITTI-aware audit side by side. Acceptance decisions must use event units and explicit class policy, not raw flag counts or benchmark FP alone.

No frontend/API/database, CVAT integration, training, model replacement, ReID, deployment or annotation correction is part of this plan. Thresholds remain unchanged in this phase. The two candidates above are the only prioritized v2 changes justified now; unseen-object coverage remains an explicit limitation.
