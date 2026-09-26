# External dataset: KITTI 0001

Kết quả và DontCare/identity audit cuối: [EXTERNAL_VALIDATION_RESULTS.md](EXTERNAL_VALIDATION_RESULTS.md). Audit giữ raw metric nguyên trạng; phân nhóm prediction riêng bằng max intersection/DontCare trên diện tích prediction. Xem `outputs/external_validation/kitti_0001/prediction_audit.csv` và `final_integrity.json`.

Phase B verified facts: **31 decoded images, all 1242×375; 463 valid 17-column rows across frames 0–30**. Evaluation retains **247 object-frame boxes / 15 distinct tracks**: Car 234 boxes / 14 tracks, Van 13 boxes / 1 track, Truck 0. Excludes 216 DontCare region rows (ID -1 is not an object track). No missing image indices or label-frame coverage. No synthetic data was substituted.

The pre-blind version of this protocol is preserved verbatim at `outputs/external_validation/kitti_0001/preblind_dataset_protocol.md`; its hash remains in `blind_lock.json`. This paragraph records post-lock inspection, not a change to the declared evaluation policy.

Local source root: `data/external_validation/kitti_0001/source/`; images under `data/KITTI/image_2/0001/`, label under `data/KITTI/label_2/0001.txt`. Converted GT: `data/external_validation/kitti_0001/gt/gt.txt`. Converter: `tools/kitti_tracking_to_mot.py`; `conversion_audit.json` preserves every source row's class, ID, bbox and inclusion decision. `frame_manifest.json` records PNG/JPEG checksums and frame mapping. `download_manifest.json` records all 36 downloaded files, URLs, sizes, SHA-256 and verified Git blob SHA-1. The full tree also lists point clouds not downloaded.

Original label SHA-256: `c69d6d5f94cbcc5a7c450e6d0bb37616643224a0a68146a47b427f8d96699d16`. The sample is held out from this project's prior two-clip validation; overlap with pretrained detector training data is UNKNOWN.

## Protocol locked before blind run

Source: https://github.com/HengLan/Visualize-KITTI-Objects-in-Videos
Commit: `f111c5afcdcbaff721fec02f5072ac6fcb024b56`.
The complete, non-truncated Git tree is saved in `data/external_validation/kitti_0001/source_tree.json`; commit metadata and downloaded-file SHA-256/Git blob SHA-1 are alongside it.

Direct tree inspection finds 31 consecutive PNGs, `data/KITTI/image_2/0001/000000.png` through `000030.png`, one `label_2/0001.txt` (66,219 bytes), calibration and 31 Velodyne files. No `gt.txt`. Images, label, calibration, README, LICENSE and KITTI.py downloaded at the pinned commit; point clouds are inventoried but not needed/downloaded for this 2D pipeline.

Upstream `KITTI.py:get_sequence_labels` documents and unpacks the 17-column tracking schema: frame, track ID, type, truncated, occluded, alpha, left, top, right, bottom, height, width, length, x, y, z, rotation_y. This verifies the intended format before inference without viewing actual annotations. Actual label parsing, field validation, frame coverage and object counts are deferred until Phase B; if inadequate, stop evaluation rather than invent labels. Downloading/checksumming label bytes is not semantic inspection or use by inference.

Phase A uses only images. Preserve YOLO26n weights, ByteTrack and runner default conf=0.25, NMS IoU=0.7, imgsz=960, classes COCO 2/5/7, device CPU, analyzer/config unchanged. Existing runner only accepts `img1/*.jpg`: prepare JPEG quality 95 using OpenCV (same encoding setting as existing video decoder), without resizing/sampling. PNG index n maps to JPEG/MOT frame n+1. Record original and derived checksums; JPEG is not pixel-identical to PNG. Freeze prediction and review hashes before Phase B.

### Evaluation policy declared before viewing labels

Custom project vehicle evaluation retains KITTI **Car, Van, Truck** as one class-agnostic vehicle group. Car/Truck overlap the runner's COCO car/truck; Van has no dedicated COCO class and may be detected as either. COCO bus is enabled in the unchanged runner but has no exact matching named KITTI class in this policy; taxonomy mismatch remains a limitation. Do not silently include Tram, Misc, Cyclist, Pedestrian or Person_sitting. Preserve original classes and IDs in an audit sidecar.

Map KITTI frame n to MOT n+1, KITTI track ID t to MOT t+1 (preserve inverse mapping; positive IDs), x=left, y=top, w=right-left, h=bottom-top; no +1 pixel adjustment, no clipping. Keep valid positive-area vehicle boxes at every occlusion/truncation state and size. No benchmark difficulty filter. Output confidence=1 and placeholders -1 in the last three MOT columns.

`DontCare` is excluded from target GT and preserved in the sidecar. Primary metrics use the existing evaluator unchanged with all frozen predictions; it does not suppress predictions overlapping DontCare or excluded classes. Therefore raw FP counts may include ignored/out-of-scope objects and must not be equated to confirmed hallucinations. Flag adjudication examines those cases separately and retains UNCERTAIN where necessary. This is **not official KITTI benchmark evaluation**: KITTI evaluates Car/Pedestrian with its own ignore/difficulty policy. No threshold tuning in this run.

Code license: upstream [LICENSE](../data/external_validation/kitti_0001/source/LICENSE) is MIT, copyright 2022 Fan Lab@UNT. Dataset origin: [KITTI tracking](https://www.cvlibs.net/datasets/kitti/eval_tracking.php), by KIT and TTI-C. Dataset license is separate: KITTI's [copyright statement](https://www.cvlibs.net/datasets/kitti/) specifies CC BY-NC-SA 3.0. Cite Geiger, Lenz, Urtasun, “Are we ready for Autonomous Driving? The KITTI Vision Benchmark Suite”, CVPR 2012. MIT code licensing does not relicense KITTI images/labels.
