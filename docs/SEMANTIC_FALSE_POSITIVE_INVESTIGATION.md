# Semantic False-Positive Investigation — task 20/job 18

## Kết luận và mức bằng chứng

**OBSERVED_LIVE / HUMAN-VISUAL CANDIDATE.** Candidate là external ByteTrack **10**, mapped CVAT track **19**. Bbox bám vào một quầy/cửa hàng sáng bên kia đường thay vì một road vehicle. Việc xem nhiều frame hỗ trợ kết luận đây là candidate semantic false positive, nhưng task không có ground truth độc lập nên không dùng case này như benchmark truth.

Evidence số đã khóa tại [task20_storefront_track10.json](evidence/task20_storefront_track10.json). MOT SHA-256 là `1b3ba9916290191e43d6a0b238582d818d927debd513d2844aefad6b96ed68a8`.

## Track và bbox

- Frame span: **17–116**, tức 100 frame thời gian.
- Detector thực sự tạo bbox tại **42 frame**; coverage 42%.
- Confidence: min `0.2506`, median `0.3363`, mean `0.3481`, max `0.5142`.
- Tâm bbox chỉ dịch chuyển tổng cộng `3.02 px`; median step giữa các detection liên tiếp là `1.14 px`.
- Center x nằm trong `542.08–546.305`, center y trong `240.41–246.035`.
- Có **17 gap intervals**. Danh sách frame và bbox/confidence đầy đủ nằm trong evidence JSON và MOT đã khóa.
- Không có `possible_duplicate` liên quan track 10.

Visual inspection trên các detection rải đều từ frame 17 đến 116 cho thấy bbox lặp lại trên cùng mảng storefront/quầy sáng, kể cả khi xe thật đi ngang qua cảnh. Không có chuyển động kiểu một phương tiện đi qua scene.

## Analyzer v2 có thấy gì?

Analyzer tạo **20 raw flags** cho track 10, gộp thành **17 review events**:

- 17 `track_gap`;
- 3 trong số đó đồng thời có `track_reappeared` vì gap đủ dài.

Vì vậy Analyzer không hoàn toàn bỏ qua track này: nó surface nhiều đoạn rời rạc. Tuy nhiên reason chỉ mô tả continuity. Analyzer không có class logits, crop semantics, background model hay reference để kết luận bbox không phải vehicle.

```text
tracking consistency != semantic correctness
```

Một track có thể ổn định về vị trí/ID nhưng sai object class. Ngược lại, “static” không đủ làm rule false-positive vì parked vehicle cũng có thể đứng yên.

## Root cause và phân loại blind spot

- Root cause trực tiếp: YOLO tạo vehicle detections có confidence thấp đến vừa trên texture/cấu trúc storefront.
- ByteTrack nối các detection gần cùng vị trí thành external track 10; tracker không chịu trách nhiệm xác minh semantics.
- Analyzer v2 chỉ nhận MOT output, nên chỉ thấy geometry, frame, ID và confidence đã ghi; các rule hiện tại kiểm continuity/geometry.
- Blind spot: **semantic detector false positive, partially surfaced by temporal gaps but not semantically identified**.

## Giới hạn

- Chỉ có một candidate live và human visual observation, chưa có adjudication độc lập.
- Confidence thấp là tín hiệu nghiên cứu, không phải bằng chứng; tăng threshold riêng cho task 20 sẽ có nguy cơ bỏ xe thật.
- Motion gần zero không chứng minh false positive.
- Chưa chọn hoặc đánh giá semantic verifier trên held-out false-positive set.
