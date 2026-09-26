# CVAT Integration Prototype — results

Date:2026-09-25. **Offline prototype acceptance PASS; live CVAT round-trip BLOCKED by missing server configuration/test task.**

**HUMAN_REVIEW_STATUS = PREPARED_NOT_EXECUTED.** No human results, annotation corrections or efficiency measurements were generated.

## Delivered and reused

New `tools/cvat_integration.py` reads existing v2 event JSON and exact clip JPEG inventories. It emits validated MOT/CVAT mappings, request payloads and navigation Markdown; online modes support Issues creation/reconciliation and read-only verification. New `tests/test_cvat_integration.py` exercises the adapter. Plan/guide/results are separate from historical reports. All outputs are under `outputs/cvat_integration/`.

Reused unchanged: Analyzer v2 events for KITTI0000/0001, their image sequences and raw predictions. No analyzer/threshold/tracker/evaluator modifications. Existing README changes and untracked prior work were present before this task and retained. No commit/push.

## Executed dry-runs

| Real input sequence | Frames | Events / request payloads | Experimental duplicate events | Mapping first/last |
|---|---:|---:|---:|---|
| KITTI0000 |154|12|0|MOT1/154 -> CVAT0/153|
| KITTI0001 |31|7|1|MOT1/31 -> CVAT0/30|

All events have task/job, anchor/context, external main/related IDs, reasons, v2 provenance and experimental metadata. `kitti_*_dry_run/request_plan.json`, `dry-run.json` and `navigation.md` contain every record. Server metadata in these runs is **explicitly synthetic**, derived from real local image inventories. `cvat.example.invalid` and task/job10000/20000,10001/20001 are placeholders. No request was sent to them. Mapping is validated against the supported metadata contract; it is not a claim of observed numbering on an actual task.

Separate `kitti_*_mock_api_evidence.json` uses a synthetic in-memory transport with the real event lists. First simulated push creates12/7 issues; second creates0 and skips12/7. Before/after synthetic annotation hashes match. These files are **not live CVAT evidence** and contain no human verdicts.

Two manual-import display archives were packaged separately, preserving prediction columns1–6. ZIP readback assertions verified534 boxes/27 tracks for0000 and228 boxes/22 tracks for0001. Confidence columns are converted to MOT annotation import fields, with placeholder visibility1; archives are not ground truth. `*_import_provenance.json` records source/archive hashes. Actual importer geometry/ID/interpolation behavior remains untested and is documented in the guide. Adapter itself never uploads these ZIPs.

## Test result

**56/56 PASS = all38 existing tests +18 new tests.** See `outputs/cvat_integration/tests.log`.

Coverage: schema and duplicate-event rejection; malformed intervals/IDs; first/middle/last and context mapping; invalid task/job, shuffled names, dimensions, subsampling, deleted frames and out-of-range rejection; unavailable object mapping; experimental reason; source namespaces; dry-run GET-only; second-run idempotency; resolved-status preservation; simulated timeout after server commit; remote payload conflicts/deleted markers; missing credentials; HTTP/network error without secret leakage or automatic retry; annotation-write prohibition; pagination; CLI offline artifacts/push guard; local writer lock.

Initial sandbox run failed only when Windows blocked TemporaryDirectory operations. The unchanged tests were rerun with approved filesystem access and all56 passed. The existing FFmpeg invalid-video negative test emits its expected diagnostic. No test was skipped or removed.

## Integrity and API boundary

`preservation_before.json` and `integrity.json` verify628 pre-existing files unchanged, including prior validation/regression outputs, human package, tools and configs. Human `collected/` remains empty. No old artifact was overwritten. The REST client only permits GET and POST `/api/issues`; there is no annotation PATCH/PUT/DELETE/import path.

Sequential idempotency is tested including recovery from a lost POST response. Marker scope is sequence+event within job; source content changes cause a conflict instead of silently modifying an issue. Existing local state guards against recreation of deleted mapped issues. Keep state and the initial marker comment. There is no server-side unique constraint for these custom markers: simultaneous writers across different hosts/output folders are unsupported. One writer and a consistent namespace/output folder are required.

## What remains UNKNOWN / blocked

- No CVAT_URL/CVAT_TOKEN environment variables were available. Local8080/8081 probes did not return an accessible CVAT about endpoint; this does not prove no CVAT exists elsewhere.
- Installed CVAT version, auth/permissions, actual disposable task/job IDs, import behavior, live image identity, link navigation, issue creation/readback and actual resolved-status transitions are unverified.
- API schemas and frame semantics were checked against official docs/source, linked in the plan/guide. Fake transport tests do not prove compatibility with an unknown deployed version.
- Restriction to full image sequences and one job is deliberate. Video, subsets, arbitrary frame steps, deleted frames and segmented context require a separately verified mapping extension.
- Project track IDs are **not** mapped to CVAT object IDs. Issues are frame-level, with external IDs in metadata. No GT is used.

## Next manual action

Follow `docs/CVAT_INTEGRATION_GUIDE.md`: create disposable KITTI0001 task, upload31 exact JPEGs, optionally import prepared prediction ZIP, inspect display fidelity, set URL/PAT and task/job IDs, run live dry-run, push, rerun, review/Resolve in CVAT and run `--verify`. Preserve first-push evidence before the second invocation. Live acceptance requires readback match, no duplicate issues, stable annotations during each invocation and actual UI navigation/resolution. No production or human-efficiency conclusion is justified yet.
