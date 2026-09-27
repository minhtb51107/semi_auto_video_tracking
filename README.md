# Semi-Auto Video Tracking

Validation sơ bộ: [VALIDATION_RESULTS.md](docs/VALIDATION_RESULTS.md), [nhãn từng flag](outputs/validation/flag_labels.csv), [lỗi bỏ sót và ứng viên](outputs/validation/missed_issues.csv). Evidence đổi tên và chạy lại độc lập: [RENAME_VERIFICATION.md](docs/RENAME_VERIFICATION.md). Helper `tools/validate_review_flags.py` chỉ xuất evidence offline; không thay đổi analyzer hoặc threshold.

External KITTI 0001: [held-out results](docs/EXTERNAL_VALIDATION_RESULTS.md), [KITTI evaluation adapter](docs/KITTI_EVALUATION_ADAPTER.md) và [adjusted audit results](docs/KITTI_EVALUATION_RESULTS.md). Raw project metrics và KITTI-aware adjusted metrics được giữ song song; adjusted metrics không phải official KITTI score.

CVAT live integration đã kiểm chứng trên task6/job4: tạo20 issues, retry0 duplicate, Resolve thủ công issue1 và read-back thành công; annotation hash giữ nguyên. Xem [live verification](docs/CVAT_LIVE_VERIFICATION.md), [robustness tests](docs/ROBUSTNESS_RESULTS.md), [integration guide](docs/CVAT_INTEGRATION_GUIDE.md). Task6 chỉ là integration/regression sandbox. `HUMAN_REVIEW_STATUS=PREPARED_NOT_EXECUTED`; [Human Pilot V2](docs/HUMAN_PILOT_V2_PLAN.md) mới là specification cho dữ liệu reviewer chưa xem.

Để tự chạy auto-annotation và auto-review trên một CVAT task mới, xem [workflow dành cho người dùng](docs/USER_WORKFLOW.md).
Audit task20: [semantic false positive](docs/SEMANTIC_FALSE_POSITIVE_INVESTIGATION.md), [pipeline consistency](docs/PIPELINE_CONSISTENCY_AUDIT.md) và [limitations/next gates](docs/KNOWN_LIMITATIONS_AND_NEXT_GATES.md).

Project này phát triển từ **Day03 VideoTracking lab**, repo nguồn:
https://github.com/minhtb51107/K4-L2-DAY03-TRANBINHMINH-2A202602174-VideoTracking

Mục tiêu: `video → YOLO26n + ByteTrack → MOT result → review analyzer → review_flags.csv/json`.
Các flags là gợi ý để người dùng xem lại frame/track, không phải ground truth và không tự sửa annotation.

Đây là bản tách độc lập để phát triển đề tài 2. Source, input, weights và môi trường Python nằm trong project này; không cần giữ repo lab ở đường dẫn cũ. Không copy `.git`, không tạo commit/push. `.venv` vẫn dùng Python nền đã cài trên máy; khi chuyển máy cần tạo lại môi trường, không di chuyển nguyên `.venv` Windows.

## Phần được reuse từ lab

| File | Chức năng reuse |
|---|---|
| `tools/run_tracker.py` | YOLO26n + ByteTrack trên `img1/*.jpg`, giữ trạng thái tracker, xuất MOT 10 cột |
| `tools/motlib.py` | Det, parser MOT, grouping, IoU, HOTA/CLEAR/Identity metrics |
| `tools/check_mot_labels.py` | Kiểm format, duplicate, bounds, gap/static/short track |
| `tools/evaluate_tracking.py` | Chấm tracker với reference; diagnostics IDSW/fragmentation/ghost/missed |
| `tools/visualize_tracks.py` | Vẽ bbox/ID ở frame cần review |
| `assets/guide/clip-*-preview.mp4`, `data/clips/` | Hai video và JPEG/seqinfo/reference gốc của lab |
| `annotations/clip_*/gt.txt`, `gold/clip_01/gt.txt` | Fixtures annotation và reference; chỉ đọc, không tự sửa |
| `yolo26n.pt` | Weights local đã dùng cho lần chạy MVP; không train mới |

Năm module Python lab ở trên được copy nguyên trạng. `GUIDELINE_MINI.md`, `CVAT_TASK_SPEC.md`, `data/README.md`, `THIRD_PARTY_NOTICES.md` giữ ngữ cảnh annotation và nguồn dữ liệu. `evidence/pre-gold/` giữ snapshot lịch sử.

## Phần mới của đề tài 2

- `tools/review_tracks.py`: dùng parser/IoU cũ; xuất CSV/JSON cho track_gap, track_reappeared, large_motion_jump, abnormal_size_change, low_consecutive_iou, possible_fragmentation.
- `configs/review_thresholds.json`: thresholds **thử nghiệm, chưa hiệu chỉnh**.
- `tools/video_to_clip.py`: MP4 → JPEG/seqinfo/source hash để gọi tracker cũ.
- `tests/test_review_tracks.py`, `tests/test_video_to_clip.py`: parser/continuity, 10 bản sao cố ý sai trên hai annotation, CLI và video decode.
- `tools/reproduce_mvp.py`: bổ sung khi tách project; chạy tests và cả hai pipeline, lưu command/exit/log/hash/dependency origin. Không thay thuật toán tracking/review.
- `requirements-lock.txt`: phiên bản thực tế của môi trường chạy; `.venv` riêng.

Chỉ chỉnh đường dẫn output mutation trong bản test mới sang `outputs/standalone_mutations` để giữ nguyên evidence mutation cũ. Không sửa source trong repo lab.

## Chạy với project đã chuẩn bị trên máy này

PowerShell:

```powershell
Set-Location 'D:\LCOM108_NMLT\code\100_bai_code\tep_chua_python\semi_auto_video_tracking'
.venv\Scripts\python.exe -X utf8 tools/reproduce_mvp.py
```

Runner tự tạo run ID mới theo thời gian UTC, dừng nếu thư mục run đã tồn tại, và dừng ngay khi một lệnh lỗi. Nó chạy `pip check`, toàn bộ tests, decode/tracker/analyzer/validator/evaluator/visualizer trên **cả hai** MP4. Logs và kết quả nằm ở `outputs/runs/<run-id>/`; `acceptance.json` chứa trạng thái, command, package locations, hash weights/input/output và đối chiếu output với lần MVP trước.

Runner bỏ PYTHONPATH/PYTHONHOME khỏi môi trường subprocess, tắt user-site, yêu cầu `.venv` của chính project và kiểm đường dẫn import của Torch/Ultralytics/OpenCV/NumPy/lap/Pillow. Cache settings và file tạm của tests đặt tại `.runtime/` trong project.

Để chỉ chạy tests:

```powershell
.venv\Scripts\python.exe -X utf8 -m unittest discover -s tests -v
```

## Tạo môi trường từ đầu

Môi trường đã kiểm chứng: Windows, Python **3.14.6**, torch runtime **2.14.0+cpu**, Ultralytics **8.4.145**, lap **0.5.13**, OpenCV **5.0.0**, NumPy **2.5.3**. Không yêu cầu GPU.

Trên máy có Python phù hợp, trong root project:

```powershell
py -3.14 -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements-lock.txt
.venv\Scripts\python.exe -m pip check
.venv\Scripts\python.exe -X utf8 tools/reproduce_mvp.py
```

Lần tách này tạo venv mới bằng Python nền, copy **file package thực** từ môi trường đã chạy sang site-packages mới (không junction/symlink), rồi chạy pip check/tests/pipeline. Không copy Scripts/activation từ venv cũ. Cài lại từ package index bằng lệnh pip ở trên **chưa được thử qua mạng**; phụ thuộc các phiên bản trong lock còn có wheel phù hợp. File lock không chứa đường dẫn repo cũ. Giữ `yolo26n.pt` local đã copy để tái lập đúng weights; hash trong acceptance. Runner không tải/train weights mới.

## Chạy từng bước cho video riêng

Chọn thư mục output **chưa tồn tại** cho bước decode:

```powershell
.venv\Scripts\python.exe -X utf8 tools/video_to_clip.py --video assets/guide/clip-01-preview.mp4 --out outputs/my_run/clip_01
.venv\Scripts\python.exe -X utf8 tools/run_tracker.py --clip outputs/my_run/clip_01 --model yolo26n.pt --tracker bytetrack.yaml --device cpu --out outputs/my_run/clip_01/tracks.txt
.venv\Scripts\python.exe -X utf8 tools/review_tracks.py --tracks outputs/my_run/clip_01/tracks.txt --config configs/review_thresholds.json --out-dir outputs/my_run/clip_01/review
```

MOT frame bắt đầu từ 1, bbox pixel `left,top,width,height`. Flags có `frame_id,track_id,reason,observed_value,threshold` và frame/track liên quan. Với video riêng không có reference, chỉ cần ba lệnh này; không dùng reference lab để chấm video khác.

## Evidence và giới hạn

- [Kết quả tách project](docs/PROJECT_SEPARATION.md), [danh sách file đầy đủ](docs/FILE_INVENTORY.md).
- [Audit](docs/MVP_AUDIT.md), [kế hoạch](docs/MVP_PLAN.md), [nghiệm thu MVP trước khi tách](docs/MVP_RESULTS.md) được giữ nguyên như tài liệu lịch sử của repo nguồn. Các đường dẫn tuyệt đối trong đó/metadata cũ là provenance, không phải dependency của code mới.
- `outputs/mvp_*` và các output evaluator/model cũ là evidence lịch sử; `outputs/runs/` là lần chạy mới; `outputs/standalone_mutations/` là bản sao cố ý sai mới.
- Đã bỏ khỏi bản copy: Git history, notebook, VS Code config, CVAT XML, giao diện HTML/CSS/JS và ảnh minh họa lab, lock_pre_gold script không dùng, config ReID không chạy, JPEG decode cũ có thể tạo lại. Giữ video gốc, JPEG gốc, nhãn, weights, MOT/flags/metrics/logs và ảnh review quan trọng.
- Heuristic không bảo đảm phát hiện mọi lỗi: MVP trước bỏ sót ID switch frame 94 của clip 01 theo evaluator. Thresholds chưa tune; chưa đo thời gian người review tiết kiệm. CSV/JSON chưa phải định dạng import CVAT.

Xem [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md) và [data/README.md](data/README.md) về nguồn software/media; việc copy local không thay đổi provenance hay quyền sử dụng.
