# Chạy Semi-Auto Video Tracking với CVAT

Workflow này dành cho một CVAT task ảnh 2D có label rectangle tên `vehicle`. Một lệnh sẽ tải ảnh của job, chạy YOLO26n + ByteTrack, append predicted tracks vào CVAT, chạy Analyzer v2, rồi tạo CVAT Issues tại các review event.

## 1. Chuẩn bị CVAT task

1. Mở CVAT và tạo task mới.
2. Tạo label rectangle tên chính xác là `vehicle`.
3. Upload ảnh theo đúng thứ tự thời gian.
4. Mở task và ghi lại `task_id` trên URL.
5. Mở job và ghi lại `job_id` trên URL.

Runner hỗ trợ job ảnh 2D liên tục. Task dùng sampling, deleted frame hoặc danh sách included frame sẽ dừng an toàn vì mapping frame không còn đơn giản.

## 2. Cấu hình một lần

Tại root project, copy `.env.example` thành `.env`, rồi điền URL và token thật:

```ini
CVAT_URL=http://localhost:8080
CVAT_TOKEN=replace_with_local_cvat_token
```

`.env` đã được Git ignore. Không đưa token vào command, tài liệu hoặc log. `--task-id` và `--job-id` trên command là nguồn chính cho target; không cần sửa hai ID mẫu trong `.env.example`.

## 3. Kiểm tra trước bằng dry-run

Trong PowerShell tại root project:

```powershell
.venv\Scripts\python.exe -X utf8 tools/run_cvat_pipeline.py --task-id 20 --job-id 18 --stage all --dry-run
```

Dry-run chỉ đọc metadata, labels và annotation hiện có. Nó không tải ảnh, không chạy model, không tạo annotation và không tạo Issue. Vì vậy, ở lần đầu số predicted tracks và review events hiện là `null`; các số này chỉ có sau inference thật hoặc khi artifact local hợp lệ đã tồn tại.

Kiểm tra các trường sau trong output:

- `annotation_summary`: task mới phải có 0 tag, 0 shape và 0 track;
- `frame_count` và `frame_range`;
- label `vehicle`;
- model, model hash, ByteTrack config và config hash;
- `annotation_safety: PASS`.

## 4. Chạy toàn bộ workflow

Khi dry-run đúng target và task còn trống:

```powershell
.venv\Scripts\python.exe -X utf8 tools/run_cvat_pipeline.py --task-id 20 --job-id 18 --stage all
```

Lệnh thực hiện hai stage:

1. **annotate**: tải frame vào workspace riêng, chạy YOLO26n với các class COCO car/bus/truck và ByteTrack, ghi MOT 1-based, rồi append rectangle tracks bằng CVAT `action=create`;
2. **review**: chạy Analyzer v2 trên đúng MOT artifact, tạo review events và tạo CVAT Issues idempotent.

Runner không gọi API xóa/replace annotation. Confidence vẫn nằm trong MOT và manifest local. Task hiện không có attribute confidence nên runner không tự thay label schema. External ByteTrack ID được đối chiếu với CVAT track ID sau read-back và lưu trong manifest; hai loại ID không được coi là giống nhau.

## 5. Chạy từng stage

Chỉ auto-annotation:

```powershell
.venv\Scripts\python.exe -X utf8 tools/run_cvat_pipeline.py --task-id 20 --job-id 18 --stage annotate
```

Sau khi annotation stage đã verify, chạy hoặc chạy lại auto-review:

```powershell
.venv\Scripts\python.exe -X utf8 tools/run_cvat_pipeline.py --task-id 20 --job-id 18 --stage review
```

`--stage review` yêu cầu MOT, manifest và prediction push state hợp lệ trong workspace của cùng task/job.

## 6. Xem kết quả trong CVAT

1. Reload job trong CVAT để thấy rectangle tracks.
2. Mở **Issues** trong job.
3. Chọn một Issue để tới anchor frame.
4. Comment của Issue ghi `event_id`, reason, external track ID, related track IDs và context range.
5. Mở rộng trước/sau context khi cần và tự quyết định chỉnh annotation. Runner không tự sửa, merge, đổi ID hoặc xóa box.

## 7. Resume và chạy lại

Mỗi target dùng workspace:

```text
outputs/runs/task_<task_id>_job_<job_id>/
├── metadata.json
├── frames/
├── predictions/
├── mot/
├── review_events.json
├── cvat_push/
└── run_summary.json
```

Chạy lại đúng command. Runner kiểm hash metadata, frames, model/config, MOT và Analyzer config để bỏ qua stage đã hoàn tất. Nó read-back CVAT trước khi retry; prediction tracks và Issues đã tồn tại sẽ không được tạo trùng. Nếu artifact khác nguồn hoặc bị hỏng, runner dừng thay vì âm thầm dùng lại.

Nếu task đã có annotation không thuộc run hiện tại, stage `annotate` và `all` dừng trước khi tải frame. Chỉ append có chủ ý bằng:

```powershell
.venv\Scripts\python.exe -X utf8 tools/run_cvat_pipeline.py --task-id 20 --job-id 18 --stage all --allow-existing-annotations
```

Flag này chỉ cho phép append; nó vẫn không xóa annotation cũ. Hãy dùng flag này sau khi đã backup/review task và xác nhận target đúng. Không dùng nó để khắc phục task/job mismatch hoặc frame mapping lỗi.

## 8. Khi gặp lỗi

- `Task/job mismatch`: kiểm lại hai ID trên cùng một URL job.
- `Require exactly one rectangle label`: tạo hoặc chọn đúng label `vehicle`; runner không tự sửa label schema.
- `CVAT job is not empty`: dùng task mới, hoặc tự quyết định append bằng flag rõ ràng ở trên.
- `Existing ... does not match`: artifact local khác source/config đã khóa; giữ workspace để audit thay vì sửa JSON bằng tay.
- HTTP/auth error: kiểm tra CVAT đang chạy, `CVAT_URL` và token trong `.env`.

Để bắt đầu một task khác, chỉ thay `--task-id` và `--job-id`; URL vẫn lấy từ `CVAT_URL` trong environment hoặc `.env`.
