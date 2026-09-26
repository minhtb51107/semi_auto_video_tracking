# Phase 5A — Integration robustness plan

Phase 4 resolved round-trip passed on task6/job4; Phase5A starts after that gate. Task6 is an integration/regression sandbox with existing annotations, never a human-efficiency benchmark. HUMAN_REVIEW_STATUS=PREPARED_NOT_EXECUTED.

| Failure mode | Classification | Required response / evidence |
|---|---|---|
| Server unavailable | SAFE FAIL | Stop, no automatic write retry |
| Timeout before response | MUST HANDLE | Stop and reconcile remote on rerun |
| HTTP401/403 expired/invalid token | SAFE FAIL | Report sanitized endpoint/status; preserve state |
| Task missing /404 | SAFE FAIL | No POST |
| Job belongs to another task | SAFE FAIL | Validate IDs before writes |
| Frame count mismatch | SAFE FAIL | Reject before mutation |
| Image order/name mismatch | SAFE FAIL | Reject before mutation |
| Sampled/deleted/missing frames | SAFE FAIL | Unsupported layout rejected |
| POST committed but response lost | MUST HANDLE | Discover remote marker, do not repeat POST |
| Partial push7/20 then network failure | MUST HANDLE | Retry skips7, creates13, total20 unique |
| Crash/retry | MUST HANDLE | Atomic state; remote reconciliation; stale lock inspected manually |
| Local state missing, remote survives | MUST HANDLE | Recover marker mapping, including resolved items |
| Corrupt local state | SAFE FAIL | Keep original bytes; no silent reset |
| Remote event unknown locally | MUST HANDLE | Reconcile by namespace/event and exact payload |
| Duplicate event ID | SAFE FAIL | Reject entire input |
| Source artifact/hash changed | SAFE FAIL | Compare locked plan/source bytes before writes; no rebaselining |
| Malformed event | SAFE FAIL | No POST |
| Frame outside sequence | SAFE FAIL | No POST |
| Unexpected CVAT schema | SAFE FAIL | Explicit error, no partially trusted reconciliation |
| Parallel writers on different machines | OUT OF SCOPE | Single writer required; no server uniqueness primitive |
| Arbitrary video/subsample/segmented frame mapping | OUT OF SCOPE | Separate verified adapter extension required |
| Server markers and all local evidence both deleted | OUT OF SCOPE | Cannot reconstruct identity safely |

## Minimal changes

- `tools/cvat_integration.py`: strict response/state validation; reject orphan namespace markers; preserve approved plan and source-byte lock; acquire local lock before writing artifacts; checkpoint recovered mappings before new POSTs; sanitized failures. No analyzer/tracker changes.
- `tests/test_cvat_robustness.py`: synthetic fault injection and CLI guards, especially7/20 retry, state loss/corruption, source drift, API failures and unexpected schemas. Retain58 existing tests.
- `docs/ROBUSTNESS_RESULTS.md`: exact test coverage/results, separate TESTED_WITH_MOCK and LIVE_TESTED.
- `docs/CVAT_LIVE_VERIFICATION.md` and `outputs/cvat_integration/live_task_6_job_4/resolved_roundtrip.json`: resolved GET evidence without changing historical push records.
- `docs/HUMAN_PILOT_V2_PLAN.md`: held-out pilot specification only; no sessions.

Use mock/fault injection for destructive failure scenarios. Live task6 receives GET only in this phase. Lock source canonical content, raw input bytes, local image inventory and validated task/frame mapping. Legacy live request_plan remains unchanged and is checked during migration to the additional lock. Missing state may recover from remote; corrupt state requires manual inspection and must not be silently reset. No claim of production reliability from mock tests.
