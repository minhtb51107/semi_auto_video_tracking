# CVAT live verification

PHASE_4_STATUS = COMPLETE

HUMAN_REVIEW_STATUS = PREPARED_NOT_EXECUTED

## LIVE_TESTED

CVAT2.75.1 at localhost:8080, task6 `D03-V2-CLIP01-CORE`, job4. The task already contained annotations: it is an integration/regression sandbox, excluded from human-efficiency/manual-versus-assisted evidence.

-190 ordered960x540 images; MOT1..190 corresponds to validated CVAT0..189.
- First approved push created20 issues (IDs1..20), read-back20/20.
- Second push created0, skipped20 existing issues.
- The user manually resolved issue1 in CVAT. Subsequent GET read-back confirms issue1 resolved=true; IDs2..20 remain false.
- All20 event/frame/position/initial-comment payloads, including reasons/context, still match the locked plan.
- Annotation SHA-256 remains `df736d83c7561a8a5f42960bf0fb6ce9077fbdbc9b422d22ee0454d5374e6424`, equal to the first-push baseline. No annotation write was performed by the adapter.

Evidence under `outputs/cvat_integration/live_task_6_job_4/`: `first_push_evidence.json`, `push.json`, historical `verify.json`, `request_plan.json`, `state.json`, and new `resolved_roundtrip.json`. Historical verification is retained and still records the earlier unresolved state; resolved_roundtrip is the later observation with its actual timestamp.

Comparison scope is the fields captured by historical evidence: IDs, frame, position, full initial message and resolved state. Prior owner/assignee fields were not captured, so an all-fields historical comparison is unavailable. Manual action is established by the user's report plus the observed state transition; there is no fabricated UI recording.

## Remaining limits

No human timing/efficiency result. No production-readiness claim. Multi-host concurrent writers and alternate frame layouts remain outside the prototype contract. Phase5A uses mock failures without damaging this live task.
