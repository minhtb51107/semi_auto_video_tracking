# Pipeline Consistency Audit — task 20/job 18

## 607 MOT boxes và 642 CVAT track shapes

Kết luận: **EXPECTED**.

Evidence tái lập: [task20_shape_count_audit.json](evidence/task20_shape_count_audit.json).

| Thành phần | Số lượng |
|---|---:|
| MOT visible detections | 607 |
| CVAT visible rectangle keyframes (`outside=false`) | 607 |
| Gap-boundary keyframes (`outside=true`) | 21 |
| Terminal keyframes (`outside=true`) | 14 |
| Tổng explicit `outside=true` | 35 |
| Tổng CVAT REST track shapes | 642 |

Runner thêm một `outside=true` keyframe tại frame đầu tiên của mỗi gap để CVAT không nội suy bbox qua khoảng detector không có output. Nó cũng thêm terminal `outside=true` sau track kết thúc trước frame cuối của job. Vì thế `607 + 21 + 14 = 642`.

Read-back live cho thấy 607 visible shapes, 35 outside shapes và mọi track signature đều khớp payload đã push. Không có duplicate geometry trong phần chênh 35. CVAT có interpolation semantics giữa keyframes, nhưng con số 642 ở đây là explicit REST keyframes do runner gửi, không phải 35 vehicle detections mới do CVAT tự sinh.

## Post-human-edit behavior

Trước thay đổi này, run có local verified state nhưng remote annotation đã bị người dùng sửa có thể đi tiếp đến reconciliation và append lại prediction bị thiếu. Đây là hành vi không đủ an toàn.

**IMPLEMENTED:** mọi non-dry rerun hiện so sánh current CVAT annotation hash với `annotation_hash_after` đã khóa sau prediction push. Nếu khác, runner dừng trước mutation với:

```text
CVAT annotation state changed since prediction push
```

Dry-run chỉ báo `CVAT_ANNOTATION_STATE_CHANGED_SINCE_PREDICTION_PUSH`. Runner không tự coi human-edited annotation là generated state, không overwrite và không reconcile trong phase này.

## Confidence visibility

Confidence vẫn nằm trong MOT và local manifest. Task 20 không có confidence attribute; runner không tự đổi label schema. Issue payload mới ghi confidence tại marker và min/median/max của external track trong structured metadata. Đây là cách ít xâm lấn để reviewer xem tín hiệu mà không biến confidence thành CVAT annotation attribute.

| Cách | Lợi ích | Trade-off |
|---|---|---|
| Giữ trong Issue metadata | Không đổi schema; audit được | CVAT UI không lọc/sort như native attribute |
| Tạo immutable label attribute từ đầu task | Hiện cạnh object | Phải thiết kế task schema trước import; migration phức tạp |
| Chỉ dùng report ngoài CVAT | Dễ phân tích | Reviewer phải đổi context |

## Nghiên cứu giải pháp semantic false positive

Không phương án nào dưới đây đã được implement hoặc benchmark.

| Phương án | Storefront→vehicle | False-alert risk | Compute/latency | GPU/dependency | Reference-free | Integration |
|---|---|---|---|---|---|---|
| Raw detector confidence | Yếu; candidate này thường confidence thấp | Cao với xe nhỏ/che khuất | Rất thấp | Không thêm | Có | Thấp |
| Temporal confidence aggregation | Surface track yếu dai dẳng | Trung bình-cao | Thấp | Không thêm | Có | Thấp |
| Geometry/context rules | Không hiểu semantics; static rule sai với parked car | Cao | Thấp | Không thêm | Có | Thấp |
| Crop re-classifier | Có thể phân biệt vehicle/non-vehicle | Phụ thuộc domain/crop | Trung bình | Thêm classifier; GPU tùy model | Có | Trung bình |
| Second detector/classifier | Cross-check trực tiếp | Model errors có thể tương quan | Trung bình-cao | Thêm weights/dependency | Có | Trung bình-cao |
| Vision-language verifier | Hiểu “storefront” và context tốt hơn | Prompt/model instability | Cao hơn | GPU hoặc service/model mới | Có | Cao |
| Multi-signal combination | Có thể giảm alert đơn lẻ | Dễ overfit nếu sample nhỏ | Trung bình-cao | Tùy thành phần | Có | Cao |

**DESIGNED_ONLY MVP candidate:** một review-only multi-frame crop verifier dùng image-text/vision-language model nhỏ, lấy vài crop bbox cộng context và aggregate theo track. Nó chỉ tạo reason semantic candidate, không xóa annotation. Đây là lựa chọn trực tiếp nhất cho lỗi storefront; confidence và temporal persistence chỉ làm supporting signals. Evidence hiện tại chưa đủ để chọn model/threshold hoặc implement mà không overfit một case.

## False-negative blind spot

Nếu vehicle thật không được YOLO detect ở bất kỳ frame nào, Analyzer hiện **không thể biết object tồn tại**. Input runtime của nó chỉ là MOT predictions. Không có record thì không có track, gap, bbox hay confidence để phân tích.

Signals tương lai có thể nghiên cứu gồm second proposal stream, detector-before-threshold outputs, periodic scene coverage review, motion/foreground proposals hoặc semantic VLM scan. Đây là **NOT_YET_SOLVED**, không phải Analyzer rule có thể thêm bằng MOT hiện tại.
