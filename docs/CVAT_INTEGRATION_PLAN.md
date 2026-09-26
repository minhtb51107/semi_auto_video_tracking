# CVAT Integration Prototype — plan before implementation

Date: 2026-09-25. HUMAN_REVIEW_STATUS = PREPARED_NOT_EXECUTED.

## Repository evidence

- `tools/review_tracks_v2.py`, `outputs/analyzer_v2_regression/*/v2/review_events.json`: schema_version=2; event ID, main/related external track IDs, temporal extent, anchor, context and reasons. KITTI0000 has12 events;0001 has7. IDs repeat between datasets: event_id alone is not an integration key.
- `tools/build_review_package.py`, `tools/human_review/`, `docs/HUMAN_REVIEW_PILOT_STATUS.md`: offline pilot, no human sessions. Preserve this package and all validation outputs.
- `CVAT_TASK_SPEC.md`: historical lab contract, ordered images and MOT1.1 export. It is not an API implementation or evidence of server frame numbering. No current CVAT adapter found in tools.
- No CVAT_* environment configuration present at audit. Server version, permissions, task/job IDs and actual UI round-trip are UNKNOWN.

## Official sources checked

- [Issues API](https://docs.cvat.ai/docs/api_sdk/sdk/reference/apis/issues-api/) and [request schema](https://docs.cvat.ai/docs/api_sdk/sdk/reference/models/issue-write-request/): issue has job, frame, position and initial message. Use one frame-level issue per event.
- [Comments API](https://docs.cvat.ai/docs/api_sdk/sdk/reference/apis/comments-api/): list comments by job/issue; recover structured event markers before creating anything.
- [Manual QA](https://docs.cvat.ai/docs/qa-analytics/manual-qa/): CVAT supplies issue navigation, comments and resolution. No new frontend needed.
- [Data metadata](https://docs.cvat.ai/docs/api_sdk/sdk/reference/models/data-meta-read/), [job schema](https://docs.cvat.ai/docs/api_sdk/sdk/reference/models/job-read/), [v2.76.0 frame implementation](https://github.com/cvat-ai/cvat/blob/v2.76.0/cvat-core/src/frames.ts): verify task-relative frame order against ordered image metadata, not filename arithmetic alone.
- [MOT format](https://docs.cvat.ai/docs/dataset_management/formats/format-mot/): annotation import/export is available but is a separate data-changing operation. Prototype will not import or modify annotations automatically.
- [PAT authentication](https://docs.cvat.ai/docs/api_sdk/access_tokens/): Bearer token from environment. No secret written to artifacts.
- [Server API](https://docs.cvat.ai/docs/api_sdk/api/): installed server `/api/docs` is authoritative. Online execution must inspect metadata; unsupported deployment uses navigation manifest fallback.

## Scope and decisions

Issue comment preserves every event field, analyzer v2 identification, source file hash, experimental duplicate status and external_track_id. No CVAT object association is asserted. Use a frame-level point marker, not a guessed object box. Attributes were considered but would modify annotation/schema; reject that path. SDK is supported officially, but a small standard-library REST client avoids a new dependency.

Support only a disposable, 2D image task containing the full sequence, start=0, step=1, no deleted frames, one annotation job covering the entire sequence. Match each project image basename to the corresponding CVAT metadata entry, validate count/order and dimensions. Derive a table MOT frame -> CVAT task frame from these entries; reject subsets, shuffled names, duplicate basenames, video and segmented contexts in this prototype. An offline snapshot is explicitly unverified, never enough to authorize push.

Idempotency uses a source-scoped event marker and remote issue/comment reconciliation, including resolved issues. Save event->issue map and compare payloads on repeat. Refuse changed payloads and duplicate remote markers. No automatic POST retries after ambiguous failures; next invocation reconciles first. Serialize local pushes with a lock; multi-host concurrent writers are outside prototype scope.

Dry-run has no mutation; online dry-run uses GET only, offline dry-run needs no credentials. Provide JSON request payloads and Markdown navigation fallback. Push verifies remote readback and hashes job annotations before/after; verify mode reads resolved status without changing it.

## Exact file diff planned

| File | Why / input -> output |
|---|---|
| `tools/cvat_integration.py` (new) | v2 event JSON + local image inventory + snapshot or live metadata -> validated mapping, issue payloads, navigation, idempotent push/readback evidence |
| `tests/test_cvat_integration.py` (new) | synthetic metadata/API fixtures -> parsing/mapping/failure/dry-run/idempotency tests; no human data |
| `docs/CVAT_INTEGRATION_GUIDE.md` (new) | disposable-task setup, credentials, dry-run, push, resolve/verify instructions |
| `docs/CVAT_INTEGRATION_RESULTS.md` (new) | actual test/dry-run evidence and missing-server blocker |
| `outputs/cvat_integration/` (new) | preservation hashes, explicitly synthetic server snapshots, real-event dry-run requests/navigation and test logs |

No existing analyzer, tracker, evaluator, threshold, annotation or human-pilot artifact will be edited. Existing38 tests must stay. Live round-trip remains pending if URL/token/test task are unavailable; never label a mock result as live CVAT.

## Implementation notes after the initial plan

The adapter uses a canonical JSON content SHA-256 for the event source (rather than whitespace-sensitive file bytes). Preservation evidence independently uses file-byte hashes. Two optional MOT display ZIPs were prepared under the new output directory for manual initialization of disposable tasks; only copies of predictions are packaged, never imported by the adapter. The guide includes the exact regeneration recipe and import limitations. Native frame query handling is additionally evidenced by [v2.76.0 getJobAsync](https://github.com/cvat-ai/cvat/blob/v2.76.0/cvat-ui/src/actions/annotation-actions.ts#L984); installed UI behavior still requires live smoke verification.
