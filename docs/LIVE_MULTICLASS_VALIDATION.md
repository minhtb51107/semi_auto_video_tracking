# Live multi-class validation

Validation date: 2026-09-28 (Asia/Saigon)

This report records a live, disposable CVAT validation of the configurable
multi-class pipeline. It is operational evidence, not a semantic-accuracy
benchmark and not a human-efficiency study. No external labels or ground truth
were used by inference.

## Environment

- `KAGGLE_AUTH=AVAILABLE`
- `CVAT_CONNECTION=OK`
- CVAT server: 2.75.1 at the locally configured server origin
- Kaggle and CVAT credentials were read from the ignored local `.env`; no
  credential is included in this report or a runtime artifact intended for Git.

## Dataset and subset

- Kaggle identifier: `origindatalab/bangladesh-urban-traffic-dataset-free-sample`
- Source URL: <https://www.kaggle.com/datasets/origindatalab/bangladesh-urban-traffic-dataset-free-sample>
- Kaggle listing size: 114,215,843 bytes
- Selected file: `Bangladesh_Urban_Traffic_Free_Sample_Kaggle_v1/blurred_clips/BD_URBAN_007.mp4`
- Selected file size: 4,348,980 bytes
- Source video: 450 frames, 30 fps, 1280 x 720, 15 seconds
- Validation subset: source frames 0-199, 200 consecutive JPEG frames named
  `000000.jpg` through `000199.jpg`
- Readability/order check: 200/200 readable; fixed resolution and chronological
  zero-padded order
- Chosen CVAT labels: `person` and `vehicle`

The source buyer index describes this clip as an intersection with 4 persons,
9 vehicle-class objects, large-vehicle presence, and a mixed-traffic score of
96.5. A six-frame contact-sheet inspection also showed persons and vehicles.
These source metadata are selection evidence only; they are not treated as
ground truth. The Kaggle entry declares license category `other`; the downloaded
free-trial license remains in the ignored runtime area and must be reviewed
before redistributing any source media.

The dataset was inspected through its metadata/file listing before download.
Only the README, license, buyer index, and one 4.35 MB clip were downloaded,
rather than the complete dataset.

## Single-job CVAT task

- Task: `38`
- Name: `SATV2-MULTICLASS-KAGGLE-BD-URBAN-007-20260928-181648`
- Job: `52`, CVAT frames 0-199
- Dimension/type: 2D annotation
- Rectangle labels: `person` (ID 192), `vehicle` (ID 193)
- Initial annotation state: empty
- Human inspection URL: <http://localhost:8080/tasks/38/jobs/52>

Dry-run discovered both configured labels with no unsupported label and passed
annotation safety. The live command was:

```powershell
.venv\Scripts\python.exe -X utf8 tools\run_cvat_pipeline.py `
  --task-id 38 --job-id 52 --stage all --chunk-size 100
```

Configuration was unchanged from the project default: `yolo26n.pt`, ByteTrack,
confidence 0.25, IoU 0.7, image size 960, and mappings `person -> [0]` and
`vehicle -> [2, 5, 7]`. Two 100-frame inference checkpoints were created.

### Results and read-back

| CVAT label | Raw detector detections | Tracked boxes | Tracks | Remote visible shapes |
|---|---:|---:|---:|---:|
| person | 104 | 47 | 9 | 47 |
| vehicle | 617 | 436 | 56 | 436 |
| **Total** | **721** | **483** | **65** | **483** |

The detector-class breakdown was 104 person, 55 car, 296 bus, and 266 truck
detections. CVAT read-back contained both label IDs and did not collapse tracks
to `vehicle`.

CVAT returned 631 track keyframes: 483 visible prediction shapes plus 148
generated `outside=true` boundary keyframes. This is internally consistent with
the 483 locked MOT boxes.

- Analyzer v2: 146 raw flags -> 122 review events
- CVAT Issues: 122 created, 122/122 read back
- Issue frames: all within 0-199
- Human-readable text: 122/122 include the issue heading and suggested action
- Audit metadata: 122/122 include deterministic event identity and JSON metadata
- Marker placement: 122/122 match the locked plan; 7 use the visible center of
  an image-boundary-clipped bbox
- Annotation hash remained unchanged during Issue creation

The first live attempt stopped safely after 159.010 seconds when Issue placement
rejected a partially off-image tracker box. Prediction annotations had already
been verified. After the conservative marker fix, `--stage review` reused the
locked MOT/inference artifacts and completed in 37.016 seconds. The exact full
command rerun completed in 18.081 seconds: inference artifact reuse took 0.020
seconds, 65 existing prediction tracks were skipped, 122 existing Issues were
skipped, and zero duplicates were created.

## Multi-job CVAT task

- Task: `39`
- Name: `SATV2-MULTIJOB-KAGGLE-BD-URBAN-007-20260928-183019`
- Input: first 120 consecutive subset frames
- Jobs: `53` (frames 0-59), `54` (frames 60-119)
- Workspaces: `outputs/runs/task_39_job_53/` and
  `outputs/runs/task_39_job_54/`
- Human inspection URL: <http://localhost:8080/tasks/39>

The first multi-job dry-run exposed a live CVAT 2.75 metadata assumption: the
job data endpoint returns job-local frame arrays while start/stop remain absolute
task frames. The runner was fixed to support this verified response and the
regression dry-run then passed both jobs before mutation.

```powershell
.venv\Scripts\python.exe -X utf8 tools\run_cvat_pipeline.py `
  --task-id 39 --all-jobs --stage all --chunk-size 100
```

| Job | Frames | Detector detections (person / vehicle) | Tracks (person / vehicle) | Review events / Issues |
|---|---:|---:|---:|---:|
| 53 | 60 | 22 / 147 | 2 / 18 | 23 / 23 |
| 54 | 60 | 11 / 253 | 2 / 23 | 56 / 56 |

Initial task orchestration completed 2/2 jobs and 0 failures in 166.056 seconds.
The exact rerun completed 2/2 jobs in 24.050 seconds, created zero Issues, and
skipped the 23 and 56 existing Issues respectively. Completed jobs remained
independently represented in the task summary and per-job workspaces.

ByteTrack state is intentionally independent per CVAT job, so identity continuity
is not promised across job boundaries.

## Defects found and fixed

1. The minimal `.env` loader allowed only `CVAT_*` keys, so it ignored the local
   `KAGGLE_API_TOKEN`. The allowlist now includes this key while retaining
   environment-first precedence and no secret logging.
2. Issue placement rejected a bbox that intersected the image but had a negative
   coordinate. Marker placement now uses the center of the visible clipped
   intersection and still rejects wholly off-frame or invalid geometry. Track
   annotation geometry is not changed.
3. Nonzero multi-job segments were validated as if job metadata contained a
   task-global frame array. The mapping now supports verified job-local metadata
   while preserving absolute CVAT frame numbers and older task-scoped snapshots.

Each defect has a regression test. No detector, tracker, Analyzer threshold, or
semantic rule was changed.

## Capability matrix

| Capability | Status | Evidence |
|---|---|---|
| Configurable label mapping | **LIVE_VERIFIED** | CVAT labels 192/193 mapped independently |
| Multi-class prediction | **LIVE_VERIFIED** | person and vehicle detections/tracks in task 38 |
| Class identity preservation | **LIVE_VERIFIED** | two remote label IDs; 9/56 tracks by class |
| CVAT annotation push | **LIVE_VERIFIED** | 65 tracks; 483 visible shapes read back |
| Issue UX | **LIVE_VERIFIED** | 122 readable comments, audit metadata, verified markers |
| Chunking | **LIVE_VERIFIED** | two locked 100-frame checkpoints on job 52 |
| Resume/idempotency | **LIVE_VERIFIED** | exact rerun: 0 tracks and 0 Issues created |
| Multi-job orchestration | **LIVE_VERIFIED** | task 39: 2/2 jobs complete, isolated state and aggregate summary |

The configuration, adapters, chunk/resume path, and multi-job runner remain
**IMPLEMENTED** and covered by unit/integration-style mocks. This report adds the
specific **LIVE_VERIFIED** evidence above; it does not upgrade semantic quality,
tracking accuracy, or human workflow efficiency claims.

## Limitations and requested human inspection

- This is one 200-frame subset from one external source; it is not a
  generalization result.
- API counts establish class preservation and integrity, not semantic correctness.
- Source privacy blurring and dense occlusion may affect detector behavior.
- Analyzer events are heuristic candidates, not ground truth.
- Confidence remains in local/MOT artifacts and is not a CVAT label attribute.
- No cross-job identity continuity is claimed.
- No human timing or time-saving claim was made.

Please inspect task 38 in CVAT, including at least one `person` track, one
`vehicle` track, cross-class label correctness, track continuity, and several
suspicious Issues. Human visual adjudication remains pending.
