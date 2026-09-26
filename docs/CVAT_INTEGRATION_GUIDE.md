# CVAT Integration Prototype — disposable task guide

HUMAN_REVIEW_STATUS = PREPARED_NOT_EXECUTED. This workflow surfaces analyzer candidates; it does not measure human time or correct annotations.

## What is supported

Analyzer v2 events -> frame-level CVAT Issues with structured initial comments. Native CVAT Issues UI supplies navigation, discussion and Resolve. `navigation.md` is the fallback if Issues are unavailable. No object IDs are guessed; the point near the top-left denotes the frame, not a bbox/object. `external_track_id`, related IDs, all reasons, MOT/CVAT context, source digest, analyzer_version=2 and experimental status remain in the comment.

The prototype supports a **full, ordered 2D JPEG sequence, start0, step1, no deleted frames, one annotation job covering all frames**. It rejects other layouts, rather than guessing offsets or clipping context. Expected project images are `000001.jpg` through `N.jpg`. Metadata checks confirm basename order, dimensions and count, then enumerate the CVAT frame table. Under this checked contract MOT1 -> CVAT0; MOT154 -> CVAT153 (0000); MOT31 -> CVAT30 (0001). Anchor and every context boundary use that table. Matching names/dimensions does not prove identical pixels: upload the exact files and visually confirm first/middle/last frames.

## 1. Create a disposable task and upload data

Use a new personal/sandbox CVAT task, e.g. `SAT-PROTOTYPE-KITTI0001-DISPOSABLE`. Do not use a valuable task. Create a Rectangle label named `vehicle`. Upload exactly the JPEGs from `data/external_validation/kitti_0001/clip/img1/`, sorted lexicographically, with no frame sampling. Set segment size large enough for one job and zero overlap. Verify31 images and one job. For0000 use the analogous directory and154 images. Do not upload reference/GT labels.

For predicted boxes, manually import the prepared `outputs/cvat_integration/kitti_0001_predictions_for_manual_import.zip` using **MOT1.1** (the installed UI may call it MOT). This initializes only the disposable task; the adapter never imports annotations. The archive contains `gt/gt.txt` and `gt/labels.txt`. The conventional `gt/` name is required by the format: these are **predictions, not ground truth**.

Preparation preserves columns1–6 (frame, external ID, x/y/w/h) exactly. It sets not_ignored=1, class=1 mapped to `vehicle`, visibility=1 as an import placeholder, **not a measured visibility**. Tracker confidence is not represented in these columns. Raw tracker files remain unchanged. Do not use this display archive for evaluation. MOT import can interpolate tracks across missing observations; imported display is not guaranteed to reproduce raw missing-box gaps. Keep raw MOT and event metadata as the source of gap evidence. Live import fidelity, track interpolation and any importer coordinate conventions must be checked in the disposable task before drawing conclusions.

After import, inspect first/middle/last frames and export a backup. Import may reassign CVAT IDs. No external-to-CVAT object ID mapping is asserted, even if numbers happen to match.

Recreate the import archive if needed (PowerShell, project root; only writes the named integration archive):

```powershell
@'
import csv,zipfile
from pathlib import Path
seq='0001'
rows=list(csv.reader(Path(f'outputs/external_validation/kitti_{seq}/tracks.txt').read_text().splitlines()))
with zipfile.ZipFile(f'outputs/cvat_integration/kitti_{seq}_predictions_for_manual_import.zip','w',zipfile.ZIP_DEFLATED) as z:
    z.writestr('gt/gt.txt',''.join(','.join(r[:6]+['1','1','1'])+'\n' for r in rows))
    z.writestr('gt/labels.txt','vehicle\n')
'@ | .venv/Scripts/python.exe -
```

## 2. Obtain task/job IDs and credentials

Open the job. Its URL contains `/tasks/<task_id>/jobs/<job_id>`. Check the installed server's `/api/docs` for GET tasks/jobs/data/meta/annotations, GET issues/comments and POST issues. The source audit used official current docs and v2.76.0 frame code; the installed version is not yet known.

Create a Personal Access Token in CVAT user settings > Security; a write-capable token is needed for Issues. Set environment variables in your shell; never place the token in a file or this repository. `CVAT_USERNAME` is unnecessary for PAT authentication. Current PAT uses Bearer; old installations with legacy API keys may require `CVAT_AUTH_SCHEME=Token` after checking their documentation. No automatic authentication downgrade.

```powershell
$env:CVAT_URL = Read-Host 'CVAT origin, e.g. https://your-cvat-host'
$cvatSecret = Read-Host 'CVAT PAT' -AsSecureString
$env:CVAT_TOKEN = [System.Net.NetworkCredential]::new('', $cvatSecret).Password
$env:CVAT_AUTH_SCHEME = 'Bearer'
$cvatTask = [int](Read-Host 'Disposable task ID')
$cvatJob = [int](Read-Host 'Disposable job ID')
```

HTTPS is required except localhost/127.0.0.1/::1; URLs must be origins, with no embedded credentials/path/query. The client blocks redirects and never logs authentication headers. There is no SDK install requirement; use the existing project environment (Pillow is already used by the project).

## 3. Dry-run

All commands below run from the project root. Use a fresh, dedicated output directory for the live task, separate from the shipped offline demonstration. Choose the same namespace/output directory on every rerun.

```powershell
$cvatArgs = @('--events','outputs/analyzer_v2_regression/kitti_0001/v2/review_events.json',
  '--images','data/external_validation/kitti_0001/clip/img1',
  '--sequence','kitti_0001','--task',"$cvatTask",'--job',"$cvatJob",
  '--out',"outputs/cvat_integration/live_task_$cvatTask")
.venv/Scripts/python.exe tools/cvat_integration.py @cvatArgs --dry-run
```

Live dry-run sends **GET only**. It produces `snapshot.json`, `request_plan.json`, `navigation.md`, `dry-run.json`: target, full frame mapping, event count, CREATE/SKIP_EXISTING actions and validation errors. If unsupported Issues API/permissions fail after metadata validation, request/navigation artifacts remain usable. If frame validation fails, fix the task setup; do not force an offset.

No credentials needed for the shipped **offline** example:

```powershell
.venv/Scripts/python.exe tools/cvat_integration.py --events outputs/analyzer_v2_regression/kitti_0001/v2/review_events.json --images data/external_validation/kitti_0001/clip/img1 --sequence kitti_0001 --task 10001 --job 20001 --snapshot outputs/cvat_integration/kitti_0001_offline_snapshot.json --out outputs/cvat_integration/kitti_0001_dry_run --dry-run
```

IDs10001/20001 and `cvat.example.invalid` are deliberately synthetic. Links are not live. `--snapshot` is rejected for push/verify. Offline duplicate counts depend only on the supplied snapshot; they do not describe a real server.

## 4. Push, then repeat to verify idempotency

After reviewing the live dry-run, execute on the disposable task:

```powershell
.venv/Scripts/python.exe tools/cvat_integration.py @cvatArgs --push --confirm-test-task $cvatTask
Copy-Item "outputs/cvat_integration/live_task_$cvatTask/push.json" "outputs/cvat_integration/live_task_$cvatTask/first_push_evidence.json"
.venv/Scripts/python.exe tools/cvat_integration.py @cvatArgs --push --confirm-test-task $cvatTask
```

Expected second run: all SKIP_EXISTING and unchanged issue count. `state.json` maps event_id to issue_id, scoped to server/task/job/sequence/source/images. Each comment begins `SATV2|<sequence>|<event_id>`. Before writes, remote comments/issues (including resolved issues) are reconciled; metadata drift, conflicting or duplicate markers stop execution. Keep this first comment intact; add reviewer comments separately.

Local `push.lock` prevents simultaneous writers in the same output directory. **Run one writer only**, including other machines/output directories: CVAT does not supply a server-side uniqueness constraint for our marker, so cross-host racing writers are outside this prototype. On a POST timeout, do not manually re-post: rerun this tool so reconciliation can recover a server-created issue. If a previously mapped issue is deleted, the tool stops instead of silently recreating it. After an interrupted process, inspect state/server before removing a stale lock.

The request client allows GET and POST `/api/issues` only. Every push hashes job annotations before/after and reads back event/frame/position/message; `push.json` contains evidence. A readback/API failure makes the run unsuccessful; earlier successful issue creations may remain. State is checkpointed after each POST. Do not allow annotation editing concurrently with the push verification.

## 5. Review and verify resolved status

Open `navigation.md` links or the CVAT job's Review workspace/Issues tab. Each event has anchor and context-start/end links; the comment contains full ranges and related external IDs. `possible_duplicate` is experimental, not a confirmed duplicate. Use native issue navigation, inspect context, add a verdict/note and choose Resolve when appropriate. The script never resolves/accepts/rejects or changes annotations for you.

```powershell
.venv/Scripts/python.exe tools/cvat_integration.py @cvatArgs --verify
Remove-Item Env:CVAT_TOKEN
```

`verify.json` reads back `resolved` for every mapped event and checks annotation stability during this read-only operation. `verified=true` means all items exist and match, **not that all issues are resolved**: inspect each `readback[].resolved`. Human edits between runs are allowed; the before/after hash only tests stability during the individual invocation. Actual UI URL/deep-link behavior must be smoke-tested on your installed version; if it differs, native CVAT Issues navigation still addresses the issue frame.

## References and limits

### Phase5A robustness update

Credential lookup now uses process environment first, then root `.env` for missing keys only. `.env` is Git-ignored; `.env.example` contains placeholders. The minimal parser supports blank/comment lines, KEY=value, optional `export` and matching quotes; it performs no shell expansion or interpolation. Task/job IDs can come from CVAT_TASK_ID/CVAT_JOB_ID; explicit CLI IDs win. No dependency was added.

A fresh push now requires an existing dry-run plan. `request_plan.json`, first `snapshot.json` and `source_lock.json` are preserved on retry. The source lock includes raw event-file SHA-256 and the full validated plan identity (source content, image inventory, target and frame mapping). A changed file, even whitespace-only, requires review in a new integration directory; do not delete the lock to bypass a mismatch. Remote namespace conflicts still block a changed source in a new directory. A legacy plan can gain a byte lock only after its prior semantic identity matches; historical raw byte identity cannot be retrospectively established.

Missing local state recovers from remote markers; malformed/mismatched state stops without overwriting it. Recovered IDs are checkpointed before remaining POSTs. Failure tests cover7 successes out of20 followed by retry:7 skipped,13 created,0 duplicates. Lock/state/schema changes affect only the integration layer. See `ROBUSTNESS_RESULTS.md` and `CVAT_LIVE_VERIFICATION.md` for current evidence; the original offline limitations below describe the initial implementation stage.

- [CVAT Issues](https://docs.cvat.ai/docs/api_sdk/sdk/reference/apis/issues-api/), [Comments](https://docs.cvat.ai/docs/api_sdk/sdk/reference/apis/comments-api/), [Manual QA](https://docs.cvat.ai/docs/qa-analytics/manual-qa/).
- [Official MOT import/export layout](https://docs.cvat.ai/docs/dataset_management/formats/format-mot/), [PAT](https://docs.cvat.ai/docs/api_sdk/access_tokens/), [server schema](https://docs.cvat.ai/docs/api_sdk/api/).

No live server was available during implementation. Mock transport tests are not API compatibility proof. No automatic task creation, GT upload, object matching, bbox correction, annotation attributes, stage changes, frontend, deployment or human-efficiency claim is included. Keep the separate human pilot PREPARED_NOT_EXECUTED until real reviewer sessions are collected.
