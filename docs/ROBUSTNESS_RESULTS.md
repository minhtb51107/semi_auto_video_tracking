# Phase5A — Integration robustness results

IMPLEMENTED: integration-only source locking, strict remote/state validation, preservation of approved plans, recovered-state checkpointing and refusal of orphan namespace markers. Analyzer, tracker and thresholds are unchanged.

Full suite: **74/74 PASS**, comprising58 existing tests and16 new robustness tests; no removed/skipped/relaxed baseline tests. Tests use synthetic transport, no live failure injection. See `tests/test_cvat_robustness.py` and `tests/test_cvat_integration.py`.

| Failure simulated | Expected | Actual | Evidence level |
|---|---|---|---|
|20 events,7 POSTs commit, network fails before8th|persist7; retry skip7/create13|PASS;20 unique markers/issues, unchanged annotations|TESTED_WITH_MOCK|
|POST commits, response lost before ID checkpoint|remote discovery, no duplicate|PASS; first existing skipped, remaining19 created|TESTED_WITH_MOCK|
|state deleted after successful push|recover20 IDs from remote|PASS;0 new, resolved status preserved|TESTED_WITH_MOCK|
|state JSON malformed/null/wrong scope|safe fail, preserve bytes|PASS;0 POST|TESTED_WITH_MOCK|
|event source changed before first push|reject against approved plan|PASS; plan unchanged,0 POST|TESTED_WITH_MOCK|
|source raw bytes changed, semantic JSON same|reject raw SHA-256 change|PASS;0 POST|TESTED_WITH_MOCK|
|source lock corrupt / push without dry-run|stop; do not reset lock|PASS|TESTED_WITH_MOCK|
|source drops previously pushed event|detect remote namespace orphan|PASS; reconciliation rejects|TESTED_WITH_MOCK|
|job/task mismatch, count/order/filter/deleted/missing frames|reject before POST|PASS|TESTED_WITH_MOCK|
|server unavailable, timeout,401/403/404|sanitized failure, no auto retry|PASS;one HTTP attempt|TESTED_WITH_MOCK|
|metadata API fails during CLI|preserve existing approved plan|PASS;0 POST|TESTED_WITH_MOCK|
|unexpected issue/comment/task metadata schema|safe fail|PASS;0 POST|TESTED_WITH_MOCK|
|malformed, duplicate-ID, out-of-range event|reject entire source|PASS;0 POST|TESTED_WITH_MOCK|
|stale lock after interrupted process|stop for inspection|PASS; lock/plan unchanged|TESTED_WITH_MOCK|
|local image inventory digest changes|stop source integrity mismatch|PASS;0 POST|TESTED_WITH_MOCK|

Existing integration tests additionally cover first/middle/last/context mapping, credential fallback, dry-run/no annotation writes, URL/auth errors, resolved-state preservation, duplicate remote markers and bounded pagination behavior.

## Live evidence and boundaries

LIVE_TESTED: task6/job4 creation20/read-back20, repeat push0 duplicates, issue1 manually resolved then read back true, remaining19 still false, exact initial messages and annotation SHA-256 unchanged. See `CVAT_LIVE_VERIFICATION.md` and `resolved_roundtrip.json`. The task was annotated previously and is not a human-efficiency benchmark. No outage, token invalidation or partial failure was injected into task6.

Additional Phase5A GET-only check: rebuilt current task/image/source mapping matches the historical plan; strict reconciliation finds20 existing events even when no local mapping is passed. Annotation stability and resolved state pass. `outputs/robustness/live_readonly.json` captures this real-server evidence. The actual disk state was not deleted and no POST was issued; missing-file retry with remaining creations is tested only with mocks.

NOT_YET_EXECUTED: controlled multi-client concurrency, process-kill/OS-power-loss testing, alternate deployed CVAT versions, sampled/video/segmented task support, human-efficiency pilot. Atomic replace protects against a partially written JSON state at application level; no power-loss durability claim. A stale writer lock requires operator inspection rather than automatic deletion. Cross-host writers remain unsupported.

Legacy plans are compared semantically before adopting the added byte lock. Retrospective raw byte integrity before that migration is unavailable. Both source and local mapping loss can still recover remote events while their structured comments survive. Deletion of both all local evidence and server markers is not recoverable. Identity-based remote reconciliation is necessary but does not provide a server-enforced uniqueness constraint for competing writers.

HUMAN_REVIEW_STATUS = PREPARED_NOT_EXECUTED. Mock tests are software failure checks, not production or human-study evidence.
