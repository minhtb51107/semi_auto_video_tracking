# External validation 02 — KITTI Tracking 0000

## Preregistered before image download / semantic GT access

Source dataset: https://www.cvlibs.net/datasets/kitti/eval_tracking.php

Public source archives:

- https://s3.eu-central-1.amazonaws.com/avg-kitti/data_tracking_image_2.zip
- https://s3.eu-central-1.amazonaws.com/avg-kitti/data_tracking_label_2.zip

Sequence: **training 0000**, previously absent from this project. ZIP central directory confirms **154 consecutive PNG members**, expected image payload **132,349,805 bytes (132.35 MB)**. Archive size is15,813,146,295 bytes but only member ranges will be downloaded. Metadata inspection transferred2,129,588 bytes. Source is KITTI archive rather than a Git repository; commit N/A. Image archive ETag: `5eed58a54608975e5c81b610b8461f2b-1886`. Member CRC32/size list: `data/external_validation/kitti_0000/images_inventory.json`; downloaded members will add SHA-256. HTTP requests require206 and bounded ranges, reject full-body fallback.

Selection rationale: full154-frame sequence gives longer trajectories and entry/exit opportunity than31-frame 0001, with modest local storage/CPU load. More Car, occlusion, Van/DontCare and higher density/crossing are desired characteristics, **not yet confirmed**; no semantic GT has been read for selection. Do not choose another sequence after seeing analyzer performance. This is held out from project development, not a claim about pretrained-model training data.

Dataset attribution/license: KITTI (Geiger, Lenz, Urtasun, CVPR2012), CC BY-NC-SA3.0 per https://www.cvlibs.net/datasets/kitti/ . Selective download does not change data license. No third-party Git code is imported.

Blind policy: unchanged YOLO26n weights, ByteTrack, runner defaults conf0.25/NMS0.7/imgsz960/COCO2,5,7/CPU, analyzer and review config. Prepare JPEG quality95 from PNG in order, no resize/sampling; source frame0→MOT frame1. Lock original PNG/JPEG manifests, all core/model/config hashes, prediction and review outputs before reading/converting label.

Phase B: reuse existing converter Car+Van+Truck for raw project evaluation; use unchanged KITTI Car-aware adapter separately (assume classless predictions are Car). Neither path is an official KITTI score. Keep raw/adapted policies identical to external0001. No threshold tuning or analyzer changes. Record individual flags and group equal track/interval events; unresolved semantics remain UNCERTAIN. Systematic missed-issue candidates require visual evidence before TRUE_ISSUE.

## Verified after blind lock — FACT

The preregistration above is preserved byte-for-byte in `outputs/external_validation/kitti_0000/preblind_dataset_protocol.md`; this section was added during evaluation. No sequence reselection, redownload, or inference rerun occurred during continuation.

- 154 original PNG images, 1242×375, source indices 000000–000153; 154/154 frames have label coverage.
- `images_download.json`: per-entry size, ZIP CRC32 and SHA-256; 134,489,095 HTTP bytes transferred for selective acquisition, not the 15.8 GB archive. Metadata inventory was a separate request.
- Label source: the public label archive URL above, entry `training/label_02/0000.txt`. Archive size 2,259,128 bytes; selected entry 38,838 compressed / 154,115 uncompressed bytes; HTTP transfer 40,567 bytes. CRC32 `a032bf79`, SHA-256 `97f772a27181dfc7ef51b3e64b86bd42e682753b6855fdc58d259ecbed501fd4`. ETag `d6017790d39ba180ad09eaf450e48f1f`; commit N/A (archive, not Git).
- Label metadata and checksum: `data/external_validation/kitti_0000/labels_download.json`. CRC verified on extraction; SHA-256 verified on continuation. ETag is an archive identifier, not a claim that the entire archive was downloaded and SHA-hashed.
- Format: original KITTI Tracking GT, 17 fields (`frame track_id type truncated occluded alpha left top right bottom ...`), 1,089 rows. No source MOT `gt.txt` was assumed.
- Blind lock: `2026-09-23T20:14:54.480435+00:00`; recorded Phase B start: `2026-09-23T20:15:46.8830922Z`. Label download occurred after lock, as opaque bytes before conversion. These are local process records, not an independently certified access history.

| Source class | Object-frame boxes | Distinct object tracks | Raw vehicle GT | KITTI Car policy |
|---|---:|---:|---|---|
| Car | 243 | 9 | Keep | 215 eligible, 28 truncated/ignored |
| Van | 292 | 3 | Keep | Distractor |
| Truck | 0 | 0 | Keep if present | Excluded |
| Cyclist | 154 | 1 | Exclude | Excluded |
| Pedestrian | 22 | 2 | Exclude | Excluded |
| DontCare | 378 region-frame rows | Not object tracks | Sidecar only | Ignore regions |

Raw target set: **535 boxes / 12 tracks**. Adapted target set: **215 boxes / 9 Car tracks**. DontCare ID −1 is not a physical track. Source GT statistics: `outputs/external_validation/kitti_0000/dataset_statistics.json`; row-level evidence: `conversion_audit.json` and `kitti_semantics/gt_preprocessing_audit.csv`.

## Sequence characteristics

**FACT from labels:** mean 3.474 vehicle boxes/frame, peak 10; mean 1.578 Car boxes/frame, peak 8. Car occlusion codes 0/1/2: 83/55/105 rows; Van codes 0/1/2/3: 147/69/70/6 rows. Car truncation codes 0/1/2: 215/21/7. Thus all 28 removed Car GT rows are truncated; no Car has occlusion >2. No Car/Van GT box has height ≤25 pixels. Four unmatched predictions meet the adapter small-box rule; GT size and prediction size are different quantities.

**FACT from temporal labels:** 11 of 12 target IDs first appear after frame 1, and five end before frame 154 (G4, G5, G6, G7, G8). These label boundaries do not alone prove physical entry/exit: occlusion and annotation policy also affect first/last labels. G1 Van persists all 154 frames.

**Visual observations:** cyclist crosses/occludes vehicles near the intersection; moving camera passes parked cars on both sides; orange Van and white Van overlap; late frames contain several closely overlapping parked vehicles. Context images R005, R007, M004_extended, M005_extended and R009/R011 provide evidence. This sequence is longer and has more sustained occlusion/identity transitions than sample 0001. It is **not denser on average**: 3.47 raw targets/frame versus 7.97 in 0001, and has fewer unique Car tracks (9 versus 14). The desired higher-density criterion was not fully met; do not rewrite selection rationale after seeing GT.

## Conversion and immutable policy

Reuse `tools/kitti_tracking_to_mot.py` unchanged: source frame n → MOT n+1, source nonnegative ID t → t+1, LTRB → `(left, top, right-left, bottom-top)`, keep Car/Van/Truck in custom classless MOT, preserve all rows in audit sidecar. Raw conversion does not apply KITTI ignore/difficulty policy. G# in visualizations is MOT ID, so original KITTI ID is G#−1.

Reuse `tools/evaluate_kitti_semantics.py` unchanged from 0001: Car target, Van distractor; Hungarian IoU≥0.5 before ignore; Car truncation >0 or occlusion >2 ignored; unmatched height≤25 or DontCare intersection/prediction-area>0.5 ignored. It rematches with project metrics after filtering and assumes all classless predictions are Car. This is a **KITTI-aware adjusted audit, not an official KITTI score**; see `KITTI_EVALUATION_ADAPTER.md` for original policy sources and limitations.

PNG → JPEG quality95/no resize was used by the existing blind runner. All original PNG and prepared JPEG hashes are retained in `frame_manifest.json`. COCO vehicle classes 2/5/7 do not map exactly to KITTI Car/Van taxonomy; predicted class was not retained in MOT. No GT was used to tune or rerun inference.

Source attribution/license remains KITTI CC BY-NC-SA 3.0; no third-party source-repository code/license was imported. Public archive access does not imply a public-domain dataset or commercial permission.
