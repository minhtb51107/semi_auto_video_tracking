# Semi-Auto Video Tracking — Human review workflow pilot

Status: package preparation / human collection pending. No human result or time saving has been measured. Analyzer v2 remains experimental and frozen. This pilot is authorized separately from production/CVAT acceptance; no integration is started.

## Participants and data

Use KITTI0000 (154 frames) and0001 (31 frames), original prepared images and locked predictions, v2 events (12 and7). No additional sequence has been acquired for this workflow round. Both have been extensively analyzed and may be familiar to the reviewer: **workflow pilot, not an unbiased controlled human study**. Do not claim a lack of publicly available alternatives; fresh-data acquisition is simply deferred.

Default: one reviewer, pseudonymous participant ID only. Select order group X or Y before opening packages, e.g. coin toss. Record prior familiarity honestly. Do not read prior reports, reference set, adjudication page or previous notes during timed review. Familiarity cannot be undone by these controls.

| Group | Session1 | Session2 | Break | Session3 | Session4 |
|---|---|---|---|---|---|
| X | A0000 | B0001 | Prefer ≥24 hours | B0000 | A0001 |
| Y | B0000 | A0001 | Prefer ≥24 hours | A0000 | B0001 |

Two reviewers: assign opposite groups, review independently; do not share results until all timed sessions finish. One reviewer: record actual break, order and memory in notes; do not pretend washout removes learning. Compare within sequence, not total A0000 time against B0001. Distinct lengths, practice/fatigue and repeat exposure confound aggregate differences. A later fresh sequence plus independent reviewers is needed for stronger conclusions.

## Start here

Open `outputs/human_review/index.html` in Edge/Chrome. No server, installation or network is needed. Keep package folders intact so relative JPEG links work. Test image rendering and controls in **Practice** first; practice data are marked synthetic and excluded from human summaries. Then choose your assigned sequence/mode; enter reviewer ID, order group, session number and familiarity before pressing Start. No timer runs during setup.

All review pages contain only predictions and image pixels. No GT boxes, previous issue labels or old conclusions are bundled into them. Mode A contains no analyzer events/reasons, even in its embedded data. Administrative adjudication is a separate page; open only after all four sessions have ended.

### Mode A — baseline

Inspect frames sequentially, starting at1. Next/Previous and frame number allow revisiting. No autoplay. Record each distinct issue with affected frame range, track(s), error/fix type and note. Finish requires all frames to have been displayed while timing is active. A displayed frame is not proof of attention; fast clicking can invalidate the pilot and must be disclosed.

### Mode B — assisted

Begin with v2 event queue. Selecting an event opens its context_start; read reasons/track IDs and navigate its context. Record one of TRUE_ISSUE, BENIGN_EVENT, FALSE_ALERT, UNCERTAIN for every event, plus fix type/note. You may expand ±5 frames or navigate anywhere; expansions and actual displayed frames are logged. Do not treat two reasons as two issues.

For every distinct suspected correction, also add a finding. An event verdict is not itself a count of physical issues. Multiple events may lead to the same issue; adjudication later deduplicates findings by reference/canonical ID. UNCERTAIN is valid. Finish requires all event verdicts and at least one displayed context frame per event; it does not falsely assume all context frames were watched.

## Timing and recording

Start/end UTC timestamps are actual browser clock readings. Primary duration is active review seconds measured by a monotonic clock, accumulated only while active. Wall duration includes breaks. Pause explicitly for interruptions; tab hidden/window focus lost auto-pauses. Resume deliberately. Per-event active dwell is a workflow measure including context/finding entry, not proof that all time was spent on the event.

State is checkpointed locally every second. Reload restores a paused draft and does not count time away; a crash can lose up to the last checkpoint interval. Draft storage depends on browser/file permissions and is not the authoritative export. Export checkpoints regularly; if storage is blocked the UI warns. Start/end clock changes, crashes, interruptions, order and familiarity must be reported. Timing is self-recorded, not externally certified.

Unique reviewed frames are successful image displays during active review; repeated displays are separately counted. Navigation before Start/while paused does not count. Record a note for confusing reasons or slow events; per-event time and expansion logs help locate friction.

This minimal UI is a **review-only** tool, not a box editor. `fix_type` is a proposed correction. Default performed correction actions=0. If you actually edit annotations elsewhere, enter the real action count and explain the external tool/method; pause for unrelated work, keep actual correction effort timed if it is part of the defined task in both modes. Do not count clicks or suggested fixes as corrections. UI interactions are logged separately. Mixing review-only and review+editing sessions invalidates direct timing comparison.

Finish freezes the session and downloads JSON; export CSV is also available. Save the downloaded files. The HTML cannot silently write to the project folder. Copy/download results into a chosen folder (e.g. `outputs/human_review/collected/`) or select them directly in the adjudication page. No manual editing of complex JSON is needed. No human result is prefilled.

## Adjudication and summary

After timed sessions, open `outputs/human_review/adjudication.html`, select completed human session JSON files. Practice/QA and incomplete sessions are rejected. For each reported finding, a reviewer/adjudicator selects TRUE_ISSUE/BENIGN_EVENT/FALSE_ALERT/UNCERTAIN and assigns the canonical reference ID if confirmed. The page includes a **historical partial confirmed issue set**: 5 issue units for0001,12 for0000, inherited from validation. It is not a complete error census. Known labels are for post-review matching only.

Match findings by object, temporal interval and correction needed, not merely frame proximity. Multiple findings mapping to the same reference count once. For a newly confirmed issue outside that set, use a new canonical ID (`NEW-...`) and evidence note; reuse that ID to deduplicate repeats. Such issues count as confirmed discoveries but are not automatically added to the historical recall denominator. Do not map an unrelated finding to a known ID just to improve recall.

If only the same reviewer adjudicates, record this lack of independence. Unmatched known references are missed **relative to this partial set**, not all real errors. Historical reference images/reports may now be consulted. Export adjudication CSV and comparison JSON after completing decisions. Send the session JSON and adjudication/comparison exports back for further analysis; no assistant-generated human timings are valid.

Metrics per session:

- Human: active and wall time, unique/repeated displayed frames, findings reported, actual self-reported correction actions, confirmed unique issues after adjudication, known references found/missed, issues/minute, frames/confirmed issue.
- Recall: distinct matched known reference IDs / known issue set for that sequence. New confirmed issues are separate.
- Event precision: reviewer TRUE / (TRUE+BENIGN+FALSE), excluding UNCERTAIN; report uncertain count and unresolved denominator. This is reviewer-rated event precision, not independent detector ground truth.
- Tool: available events, context ranges and candidate scope. Never substitute these for measured review time.

Until adjudication is complete, confirmed counts/recall/efficiency stay unavailable, not zero. Ratios with zero time/issues or no resolved events are unavailable. Compare A/B only when both completed sessions have the same reviewer and sequence; report order/familiarity, not just a pooled speedup. Do not infer time savings without actual paired data.

## Acceptance and limitations

Technical package readiness is not pilot completion. Human pilot succeeds only after a real reviewer completes both modes, exports actual timing/verdicts/findings, performs adjudication and obtains a paired summary. Then inspect friction, slow events, missed known issues and correction effort. No human results currently exist.

Controls reduce but cannot remove learning bias. Dataset sizes are small, prior exposure likely, reference set incomplete, labels preliminary, rendered-frame counts imperfect attention proxies, timers vulnerable to OS/browser interruptions, and review-only effort differs from full annotation correction. No threshold tuning during collection. Do not proceed automatically to CVAT; decide after reviewing real pilot evidence and residual coverage risks.
