# Chạy Semi-Auto Video Tracking với CVAT

Runner tải frame của CVAT job, chạy detector/tracker, append predicted tracks, chạy Analyzer v2 và tạo CVAT Issues. Core runtime không cần ground truth và không tự sửa annotation của reviewer.

## 1. Chuẩn bị task và credential

1. Tạo CVAT task ảnh 2D, upload frame đúng thứ tự thời gian.
2. Tạo các rectangle label cần dùng, ví dụ `person`, `vehicle`, `laptop`, `cell_phone`.
3. Lấy `task_id` và `job_id` từ URL CVAT.
4. Copy `.env.example` thành `.env` và điền:

```ini
CVAT_URL=http://localhost:8080
CVAT_TOKEN=replace_with_local_cvat_token
```

`.env` đã được Git ignore. Runner vẫn safe-fail với sampled/deleted/included frames.

## 2. Cấu hình label

File mặc định là `configs/label_mappings.json`:

```json
{
  "labels": {
    "person": {"detector_classes": [0], "aliases": ["pedestrian"]},
    "vehicle": {"detector_classes": [2, 5, 7], "aliases": ["car", "bus", "truck"]},
    "cell_phone": {"detector_classes": [67], "aliases": ["phone", "mobile_phone"]}
  }
}
```

Runner đọc rectangle labels từ task rồi chỉ chạy những mapping được hỗ trợ. Alias `phone` dùng mapping `cell_phone` nhưng track vẫn được push vào đúng CVAT label ID tên `phone`. Hai CVAT labels cùng map một canonical label sẽ safe-fail vì output trở nên mơ hồ.

Label không có mapping không làm cả run crash. Dry-run và summary ghi `UNSUPPORTED_LABEL`, `INCORRECT_CVAT_LABEL_TYPE` hoặc lý do cụ thể khác.

Chọn một phần labels:

```powershell
.venv\Scripts\python.exe -X utf8 tools/run_cvat_pipeline.py --task-id 20 --job-id 18 --labels person,cell_phone --stage all --dry-run
```

Dùng config khác bằng `--label-config path\to\labels.json`. `--classes` là restriction bổ sung sau mapping; không dùng nó để map class vào nhãn khác.

## 3. Chạy một job

Dry-run không tải frame, chạy model hoặc mutate CVAT:

```powershell
.venv\Scripts\python.exe -X utf8 tools/run_cvat_pipeline.py --task-id 20 --job-id 18 --stage all --dry-run
```

Kiểm `annotation_summary`, `label_plan`, model/tracker hashes, frame range và `annotation_safety`. Sau đó chạy:

```powershell
.venv\Scripts\python.exe -X utf8 tools/run_cvat_pipeline.py --task-id 20 --job-id 18 --stage all --chunk-size 500
```

Chạy riêng stage:

```powershell
.venv\Scripts\python.exe -X utf8 tools/run_cvat_pipeline.py --task-id 20 --job-id 18 --stage annotate
.venv\Scripts\python.exe -X utf8 tools/run_cvat_pipeline.py --task-id 20 --job-id 18 --stage review
```

MOT local dùng frame 1-based và lưu detector class ở cột 8. CVAT frame mapping, class→label mapping và external→CVAT track mapping đều được khóa trong manifest.

## 4. Chạy tất cả jobs của task

```powershell
.venv\Scripts\python.exe -X utf8 tools/run_cvat_pipeline.py --task-id 123 --all-jobs --stage all --dry-run
.venv\Scripts\python.exe -X utf8 tools/run_cvat_pipeline.py --task-id 123 --all-jobs --stage all --chunk-size 500
```

Jobs được xử lý theo ID tăng dần. Mỗi job có workspace riêng; kết quả task nằm tại `outputs/runs/task_123_summary.json`. Một job lỗi được ghi `FAILED`, các job đã complete không bị xóa hoặc chạy lại ngầm. CLI trả exit code 2 nếu có partial failure.

## 5. Chunk và resume

Inference checkpoint nằm trong `predictions/chunks/`. Mỗi chunk lưu normalized detections và tracks cùng config/source hashes.

Khi resume:

- frame đã download và chunk detection hoàn tất không chạy detector lại;
- ByteTrack state không được serialize giả tạo;
- tracker mới replay cached detections từ đầu để tái dựng state, đối chiếu output với chunk đã khóa, rồi detector tiếp tục ở chunk đầu tiên chưa complete;
- config, frame inventory, chunk size, checkpoint hash hoặc replay khác nhau đều làm safe-fail.

Resume giảm model inference nhưng vẫn có chi phí tracking nhẹ trên phần đã complete. Frame được lưu trên disk; pipeline không giữ toàn video trong RAM.

## 6. An toàn annotation

Runner chỉ gọi append/create; không clear hay replace annotation. Job đã có annotation mà không có local verified state dừng trước download/inference, trừ khi người dùng chủ động truyền `--allow-existing-annotations`. Flag này vẫn chỉ append.

Sau human edit, current annotation hash khác hash sau prediction push; dry-run báo `CVAT_ANNOTATION_STATE_CHANGED_SINCE_PREDICTION_PUSH`, run thật dừng trước mutation. Retry read-back remote tracks/Issues để chống duplicate.

## 7. Review trong CVAT

Issue mới có comment dễ đọc:

```text
Possible tracking issue

Severity: HIGH
Priority score: 72
Label: vehicle
Primary track: CVAT 19 / external 10
Related tracks: CVAT 24 / external 14
CVAT anchor frame: 25
CVAT review context: 16-27

Reasons:
- track gap

Suggested action:
- Continuity check: inspect CVAT 19 / external 10 across CVAT frames 16-27 and decide whether missing shapes, occlusion, or a true exit caused the gap.
```

Mọi frame trong phần dành cho người đọc đều ghi rõ theo CVAT 0-based. Structured `METADATA_JSON` vẫn giữ MOT 1-based fields và deterministic marker để audit/idempotency. Marker dùng tâm suspect bbox; nếu anchor thiếu bbox, nó dùng bbox gần nhất. `[10,10]` chỉ là fallback khi object mapping/bbox không khả dụng. Plan/Issues cũ giữ nguyên comment và position khi rerun.

Mặc định runner vẫn tạo Issue cho mọi event như phiên bản trước. Để giới hạn scope review, dùng một hoặc cả hai tùy chọn:

```powershell
.venv\Scripts\python.exe -X utf8 tools/run_cvat_pipeline.py --task-id 20 --job-id 18 --stage all --min-review-severity HIGH
.venv\Scripts\python.exe -X utf8 tools/run_cvat_pipeline.py --task-id 20 --job-id 18 --stage all --max-review-events 25
```

Priority là heuristic giải thích được, không phải xác suất lỗi. Event ID và raw Analyzer reason không đổi sau khi xếp hạng.

Để lấy mẫu QA từ frame ngoài context của mọi Analyzer event:

```powershell
.venv\Scripts\python.exe -X utf8 tools/run_cvat_pipeline.py --task-id 20 --job-id 18 --stage all --qa-sample-count 20 --qa-seed 42
```

Các Issue này bắt đầu bằng `QA-SAMPLE|`, có severity `LOW`, và chỉ yêu cầu kiểm tra vùng tưởng như sạch. Resolve một QA Issue sau khi đã xem frame đó; việc lấy mẫu không khẳng định frame là đúng.

## 8. Final validation và release gate

Sau khi sửa annotation và Resolve Issues trong CVAT, chạy validation read-only:

```powershell
.venv\Scripts\python.exe -X utf8 tools/run_cvat_pipeline.py --task-id 20 --job-id 18 --stage final-validate
.venv\Scripts\python.exe -X utf8 tools/run_cvat_pipeline.py --task-id 20 --job-id 18 --stage release-check
```

`final-validate` kiểm tra schema, label/frame, bbox hữu hạn và hợp lệ, thứ tự shape, exact duplicates, impossible jump, mapping orphan và trạng thái Issue/QA. Nó đọc annotation trước/sau để xác nhận stage không mutate CVAT. Nó không chứng minh semantic correctness hoặc tìm object detector chưa bao giờ thấy.

`release-check` chỉ đưa quyết định; không export dữ liệu:

- `BLOCKED`: structural validation thất bại.
- `REVIEW_REQUIRED`: còn CRITICAL/HIGH chưa resolve, QA chưa hoàn thành, hoặc mapping orphan.
- `READY_FOR_EXPORT`: structural checks pass, không còn blocker theo `configs/qa_policy.json`, và QA bắt buộc đã hoàn thành.

Các kết quả nằm ở `final_validation.json`, `release_check.json` và `review_state.json` trong workspace.

## 9. Workspace và observability

```text
outputs/runs/task_<task_id>_job_<job_id>/
├── metadata.json
├── frames/manifest.json + JPEG
├── predictions/manifest.json
├── predictions/chunks/
├── mot/predictions.txt
├── review_events.json
├── review_events_prioritized.json
├── review_events_selected.json
├── qa_samples.json
├── review_state.json
├── final_validation.json
├── release_check.json
├── cvat_push/
└── run_summary.json
```

`run_summary.json` giữ task/job, labels/config, model/tracker hashes, frame count, boxes/tracks theo class, Analyzer flags/events, Issues created/skipped, elapsed time tổng/per-stage và status. `failure_summary.json` ghi lỗi/endpoint khi command một job dừng.

Kiểm dung lượng read-only và cleanup:

```powershell
.venv\Scripts\python.exe -X utf8 tools/run_cvat_pipeline.py --task-id 20 --job-id 18 --workspace-status
.venv\Scripts\python.exe -X utf8 tools/run_cvat_pipeline.py --task-id 20 --job-id 18 --cleanup-frames
.venv\Scripts\python.exe -X utf8 tools/run_cvat_pipeline.py --task-id 20 --job-id 18 --cleanup-run
.venv\Scripts\python.exe -X utf8 tools/run_cvat_pipeline.py --task-id 20 --job-id 18 --cleanup-run --confirm-cleanup-run task_20_job_18
```

`--cleanup-frames` giữ audit/resume artifacts. Cleanup toàn run chỉ giữ `minimal_audit_manifest.json` và không còn resume được.

Chạy regression fixtures nhỏ, không cần CVAT hoặc dataset lớn:

```powershell
.venv\Scripts\python.exe -X utf8 tools/run_golden_qa.py
```

Fixture synthetic chỉ kiểm tra hành vi rule; các case observed trong manifest chỉ trỏ tới evidence thật hiện có và không được coi là ground truth tự tạo.

## 10. Giới hạn hiện tại

- Default runtime là `UltralyticsYOLODetector` + `ByteTrackTracker`; chưa expose BoT-SORT trong CVAT CLI.
- Analyzer v2 vẫn dựa trên MOT geometry. Duplicate/fragmentation chỉ so sánh cùng class khi cả hai class đã biết; dữ liệu legacy thiếu class giữ hành vi cũ.
- Chưa benchmark 1,000+ frame hoặc concurrent runs trên live CVAT.
- Semantic VLM verifier, detector-level missed-object discovery và training nằm ngoài iteration này.
- `READY_FOR_EXPORT` là gate integrity/workflow, không phải chứng nhận semantic correctness.
- `HUMAN_REVIEW_STATUS = PREPARED_NOT_EXECUTED`; không có claim time saving.
