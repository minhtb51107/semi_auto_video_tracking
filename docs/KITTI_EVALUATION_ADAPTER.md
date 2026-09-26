# KITTI Evaluation Adapter

Adapter này tạo một đường evaluation riêng cho KITTI, bên cạnh evaluator của project. Nó không thay `motlib.py`, `evaluate_tracking.py`, tracker, analyzer, threshold, prediction hay review flags.

## Nguồn quy tắc

Đã đối chiếu ngày 2026-09-24 với:

- [KITTI Tracking benchmark](https://www.cvlibs.net/datasets/kitti/eval_tracking.php): benchmark hiện chấm riêng Car và Pedestrian, bbox 2D 0-based, chỉ xét object/detection cao hơn 25 px, Van không bị tính là FP cho Car; evaluator hiện dùng TrackEval.
- [KITTI format do TrackEval lưu](https://github.com/JonathonLuiten/TrackEval/blob/master/docs/KITTI-format.txt): schema 17/18 cột và ý nghĩa DontCare.
- [TrackEval KITTI dataset adapter](https://github.com/JonathonLuiten/TrackEval/blob/12c8791b303e0a0b50f753af204249e622d0281a/trackeval/datasets/kitti_2d_box.py), HEAD được kiểm tra bằng `git ls-remote`: commit `12c8791b303e0a0b50f753af204249e622d0281a`.
- [TrackEval CLEAR](https://github.com/JonathonLuiten/TrackEval/blob/12c8791b303e0a0b50f753af204249e622d0281a/trackeval/metrics/clear.py): matching ưu tiên tiếp tục cặp ở frame liền trước; IDSW so với predicted ID gần nhất từng match của mỗi GT.

TrackEval hiện đặt cho KITTI Tracking: `max_occlusion=2`, `max_truncation=0`, `min_height=25`. Đây là preprocessing cố định của tracking adapter, không phải ba difficulty tier easy/moderate/hard của KITTI object detection.

## Semantics được tái hiện

Adapter [evaluate_kitti_semantics.py](../tools/evaluate_kitti_semantics.py) chạy Car view:

1. Đọc trực tiếp KITTI Tracking GT; không dùng `gt.txt` custom của vòng 1 để quyết định ignore.
2. Xét Car và Van khi preprocessing. Car với `occluded <= 2` và `truncated == 0` là target; Van là distractor. Truck và class khác không thuộc Car evaluation.
3. Gán tất cả prediction MOT là Car, vì `run_tracker.py` đã bỏ class detector khi xuất MOT. Đây là giả định bắt buộc và là lý do kết quả chưa official.
4. Trong từng frame, Hungarian match prediction với Car+Van bằng IoU >= 0.5.
5. Xóa prediction đã match Van, Car có occlusion >2 hoặc truncation >0.
6. Với prediction chưa match, xóa nếu height <=25 hoặc nếu `intersection(prediction, DontCare) / area(prediction) > 0.5`. Dấu `>` là strict, giống TrackEval.
7. Xóa distractor/invalid GT, sau đó chạy lại các metric hiện có của project trên Car GT và prediction đã giữ.

Thứ tự rất quan trọng: prediction đã match target Car không bị xóa chỉ vì nhỏ hoặc overlap DontCare. Một distractor chỉ hấp thụ được một prediction qua Hungarian; duplicate thứ hai có thể vẫn là FP.

## Hai output song song

`outputs/external_validation/kitti_0001/evaluation.json` là raw project evaluation vòng 1, giữ nguyên. Adapter xuất vào thư mục con mới:

- `kitti_semantics/evaluation.json`: raw metrics được copy theo hash và KITTI-aware adjusted project metrics.
- `gt_preprocessing_audit.csv`: quyết định cho từng GT/DontCare row.
- `prediction_preprocessing_audit.csv`: quyết định giữ/bỏ từng prediction, match preprocessing, best relevant GT và DontCare IoA.
- `adjusted_clear_matches.csv`: association sau preprocessing.

Adapter còn chạy ba counterfactual audit: bỏ DontCare ignore, bỏ small-box ignore, và bỏ cả hai. Chúng chỉ phân rã nguyên nhân thay đổi FP; không phải score thay thế.

## Vì sao chưa gọi là official KITTI score

- Raw prediction không chứa class; COCO car/bus/truck đã bị gộp và nay đều phải giả định là KITTI Car.
- Input prediction là MOT 10 cột, không phải KITTI result 18 cột có class và confidence semantics tương ứng.
- Adapter reuse HOTA/Identity/CLEAR implementation của project sau preprocessing, không chạy toàn bộ official TrackEval pipeline/output aggregation.
- Chỉ một sequence rút gọn 31 frame từ training sample, không phải split benchmark.

Tên đúng của output là **KITTI-aware adjusted audit metrics**.

## Lệnh chạy

```powershell
.venv\Scripts\python.exe -X utf8 tools/evaluate_kitti_semantics.py `
  --labels data/external_validation/kitti_0001/source/data/KITTI/label_2/0001.txt `
  --pred outputs/external_validation/kitti_0001/tracks.txt `
  --raw-evaluation outputs/external_validation/kitti_0001/evaluation.json `
  --out-dir outputs/external_validation/kitti_0001/kitti_semantics

.venv\Scripts\python.exe -X utf8 -m unittest discover -s tests -v
```

Adapter chỉ đọc artifact vòng 1 và ghi thư mục `kitti_semantics/`; không ghi lại prediction, flags hoặc evaluator raw.
