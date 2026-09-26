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
