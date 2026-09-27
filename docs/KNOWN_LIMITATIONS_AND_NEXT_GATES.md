# Known Limitations and Next Gates

## Scope hiện tại

| Hạng mục | Trạng thái | Gate tiếp theo |
|---|---|---|
| Multi-label | Pipeline map COCO car/bus/truck vào đúng một CVAT rectangle label `vehicle`. Generic label mapping chưa có. | Chỉ thiết kế mapping khi có task thật cần nhiều label và policy conflict rõ. |
| Sampled/deleted/included frames | Unsupported và safe-fail. | Cần use case + kiểm chứng chính xác CVAT frame addressing trước khi mở. |
| Multiple jobs | Runner xử lý một `task_id/job_id` mỗi invocation và hỗ trợ job có frame offset; không batch toàn task. | Batch orchestration khi có task nhiều segment thật, kèm isolation/retry từng job. |
| Large scale | Chưa có evidence cho 1,000+ frame, nhiều task, concurrent run hay worker dài hạn. | Benchmark CPU/GPU, disk, timeout, crash recovery và concurrency lock. |
| Human efficiency | `HUMAN_REVIEW_STATUS = PREPARED_NOT_EXECUTED`. | Chạy held-out baseline vs assisted pilot với timing thật. Không claim time saving trước đó. |
| Semantic false positives | Track storefront task 20 đã được điều tra; Analyzer chỉ surface gap chứ không hiểu semantic. | Tập hợp nhiều adjudicated cases trước khi thử crop verifier. |
| False negatives | Vehicle không bao giờ được detector tạo box hoàn toàn vô hình với MOT-only Analyzer. | Thêm signal độc lập với final MOT; không giả lập missed-object rule. |
| Identity ambiguity | Geometry rules bắt gap/fragment/duplicate candidate; không chứng minh physical identity khi appearance giống/crossing. | Appearance/detector history chỉ nghiên cứu sau human evidence; chưa thêm ReID. |
| `possible_duplicate` | Experimental; không phải identity proof. | Human verdict trên held-out pilot và false-alert accounting. |
| Confidence trong CVAT | Có trong MOT/Issue metadata, không có native label attribute. | Quyết định schema trước khi tạo task mới nếu reviewer thực sự cần filter/sort. |
| Existing live Issues | 22 Issue task 20 dùng comment/position v1 `[10,10]`. | Không tự xóa/migrate. UX bbox-center áp dụng cho run mới; migration cần explicit live plan. |

## CVAT Issue UX v2

**IMPLEMENTED / MOCK_TESTED:** Khi external track đã map, Issue dùng tâm bbox ở anchor frame. Nếu anchor không có bbox, runner chọn detection gần nhất theo `(absolute frame distance, earlier frame)` và đặt Issue ở frame đó. Nếu track không map hoặc không có bbox, runner dùng frame-level marker `[10,10]` và ghi fallback mode. Geometry NaN, bbox âm hoặc vượt frame làm pipeline safe-fail.

Comment mới chứa event ID, reasons, CVAT track ID, external track ID, anchor/context, Analyzer version, experimental status, placement mode và structured metadata. CVAT Issue API vẫn không bind Issue trực tiếp vào object; spatial point + verified track mapping là giới hạn hiện tại.

Task 20 có local preview **22/22 `ANCHOR_BBOX_CENTER`** tại [task20_issue_placement_preview.json](evidence/task20_issue_placement_preview.json), nhưng live Issues cũ chưa được thay đổi. Trạng thái này là **NOT LIVE_TESTED** cho UX mới.

Safe migration strategy: giữ nguyên 22 Issue hiện tại làm integration evidence; kiểm UX mới trên task disposable tiếp theo. Nếu vẫn cần migration task 20, trước hết phải read-lock annotation/Issue state, dùng namespace UX version mới để không đụng marker cũ, preview toàn bộ payload rồi xin xác nhận live riêng. Không tự delete Issue cũ và không mutation trong lượt này.

## Workspace lifecycle

Frames là phần lớn dung lượng và đắt để tải lại; chúng cần cho resume nhanh nhưng có thể xóa sau khi cả prediction push và Issue read-back đã verify. MOT, review events, metadata, hashes và CVAT mappings là audit/resume evidence nên được giữ.

Cleanup từ chối chạy khi run incomplete, push chưa verify, annotation guard fail, manifest/hash mismatch hoặc có writer lock. `--cleanup-run` luôn preview trước, chỉ xóa khi confirmation bằng đúng workspace name, rồi chỉ giữ minimal audit manifest; vì vậy nó không còn resume được. Không có cleanup nào được chạy trên task 20 trong lượt implementation này.
