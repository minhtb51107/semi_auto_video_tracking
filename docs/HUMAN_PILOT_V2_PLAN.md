# Human Pilot V2 — specification only

HUMAN_REVIEW_STATUS = PREPARED_NOT_EXECUTED

## Eligibility

Recruit a reviewer and choose sequences they have never seen, annotated or reviewed. Record prior exposure before assignment. Task6/clip01 and previously inspected KITTI0000/0001 are not eligible for an unbiased comparison for that reviewer. Existing familiar datasets remain workflow/regression fixtures only. No new sequence is selected, downloaded or assigned in this specification.

Use at least two held-out clips matched approximately for length, object density, occlusion and entry/exit; freeze tracker output, analyzer events/config and checksums before review. A separate adjudicator may use reference/GT after blind sessions. The runtime analyzer and timed reviewer receive no GT or prior issue labels.

## Assignment and modes

Baseline A: sequential inspection of the complete clip, prediction boxes visible, no analyzer hints. Assisted B: begin at frozen review events with context, external IDs and reasons; allow context expansion and log it. Same prediction version, player speed controls, display and findings form for both.

With one reviewer, randomly assign unseen matched clipA to baseline and clipB to assisted; do not let the person review the same clip in both modes for the primary comparison. Add another unseen pair with reversed mode order if possible. Different clips create a content confound: report clip-specific results, not a causal time-saving estimate. A delayed repeat on the same clip is exploratory only and explicitly subject to memory bias.

With two or more reviewers, counterbalance assignments: reviewer1 sees clipA baseline/clipB assisted, reviewer2 sees clipB baseline/clipA assisted. Each reviewer sees each clip once. Randomize order and balance breaks. Record expertise, prior exposure, device and interruptions. Fix assignment before opening any clip. No study size or power claim for a small pilot.

## Measurements

| Metric | Definition |
|---|---|
| Active review time | Actual monotonic timer between Start/Finish minus pauses/blur; report wall time separately |
| Frames inspected | Unique frames displayed plus repeat-display count; display is a proxy, not proof of attention |
| Findings | Reviewer reports with frame span, external IDs, error type, note |
| Confirmed errors found | Deduplicated canonical issues matched by an independent adjudicator |
| Confirmed errors missed | Adjudicated reference issues not found in that session; full-set validity reported |
| Review actions | Navigation/context expansion/verdict/finding operations; actual correction actions separate |
| Diagnostic rates | Confirmed issues/minute, frames/confirmed issue, event precision and reference recall; N/A for undefined denominators |

Reference set must be built by exhaustive full-clip adjudication, not just flagged frames. Adjudicator inspects unmatched findings and missed-issue candidates, resolves identity/duplicate grouping, and records uncertainty. If only a partial reference exists, report recall against that partial set and do not claim complete recall. Group raw reasons into canonical issues; gap/reappeared is not two errors.

## Decision criteria (set before collection)

Workflow pilot passes when real sessions finish, timing and findings export correctly, event text/context are understood and friction is documented. Quality/effort decision requires valid adjudication, disclosure of critical missed identity/coverage errors, and a joint time-versus-recall comparison. Choose any acceptable recall loss margin and minimum useful effort reduction with the study owner before collecting data; this plan does not invent numeric thresholds or tune them after results.

If assisted review misses important errors or offers no consistent benefit across unseen clips, report that and investigate; do not relabel candidate scope as time savings. Small, unmatched, familiar or incomplete-reference runs are exploratory. Integration success alone does not establish review efficacy. No fake session or human result is created by this plan.
