# Semi-Auto Video Tracking — External Held-Out Sample Validation

Hoàn thiện từ artifact sẵn có; không tải lại dữ liệu, không chạy lại blind inference, không sửa tracker/evaluator/analyzer/threshold. Các nhãn dưới đây là adjudication sơ bộ của người phân tích qua reference và ảnh, chưa có annotator độc lập.

## Dataset

[EXTERNAL_DATASET.md](EXTERNAL_DATASET.md) ghi nguồn, license và mapping đầy đủ. Source: HengLan/Visualize-KITTI-Objects-in-Videos, commit `f111c5afcdcbaff721fec02f5072ac6fcb024b56`, sample KITTI tracking 0001. Có **31 PNG liên tiếp**, 1242×375, frame 000000–000030, label `label_2/0001.txt` dạng KITTI Tracking 17 cột, không có MOT gt.txt nguyên bản.

463 dòng label hợp lệ: **234 Car + 13 Van + 216 DontCare**. Policy khai báo trước evaluation giữ Car/Van/Truck làm nhóm vehicle: thực tế **247 object-frame boxes, 15 object tracks** (14 Car, 1 Van, 0 Truck). ID -1 của DontCare không phải một object track. 31 frame có label coverage đầy đủ; không giả lập dữ liệu.

Converter riêng [kitti_tracking_to_mot.py](../tools/kitti_tracking_to_mot.py): frame n→n+1, track t→t+1, x=left, y=top, w=right-left, h=bottom-top; giữ mọi size/occlusion/truncation, không clip bbox. DontCare và class ngoài policy chỉ lưu sidecar, không đưa vào target GT. G# trong ảnh/CSV là MOT ID, vì vậy KITTI ID=G#−1.

Upstream code MIT; KITTI dataset CC BY-NC-SA 3.0 theo nguồn đã lưu trong dataset doc. Đây là dữ liệu ngoài hai clip của project, không chứng minh chưa xuất hiện trong training của pretrained detector.

## Blind run và integrity

Run đã có: **228 predicted boxes / 22 tracks; 7 flags / 6 flagged frames**. Input PNG được chuyển thành JPEG quality95, không resize/sampling, vì runner chỉ đọc JPEG. YOLO26n + ByteTrack, conf .25, NMS IoU .7, imgsz960, classes2/5/7, CPU giữ nguyên.

[blind_lock.json](../outputs/external_validation/kitti_0001/blind_lock.json) chứa command/exit codes, hash code/model/config và raw outputs. Run khóa lúc **2026-09-22 17:25:58.433353 UTC**. [phase_b_started.json](../data/external_validation/kitti_0001/phase_b_started.json) ghi nhận semantic label read sau đó lúc **17:26:12.194464 UTC**. Timestamp thứ hai được ghi ngay sau thao tác đọc đầu tiên trong script, không phải access-log độc lập. Không sửa timestamp hoặc tạo lịch sử thiếu. Label đã tải/hash dưới dạng byte trước inference, không dùng cho detector/analyzer.

Kiểm tra tiếp tục phiên: tất cả hash đã khóa vẫn khớp; config và analyzer cũng khớp [validation hai clip cũ](../outputs/validation/summary.json). Tất cả checksum file tải đã kiểm lại; conversion chạy lại trong bộ nhớ trùng GT đã lưu. Protocol trước inference lưu nguyên bản trong [preblind_dataset_protocol.md](../outputs/external_validation/kitti_0001/preblind_dataset_protocol.md); dataset doc hiện tại có thêm kết quả kiểm tra sau run. [final_integrity.json](../outputs/external_validation/kitti_0001/final_integrity.json) ghi các kiểm tra này.

Không có timestamp conversion độc lập được lưu từ trước; không dùng mtime để thay thế chứng cứ. Log quá trình và record Phase B thể hiện conversion diễn ra sau lock; hash chứng minh artifact hiện tại không bị thay đổi, không tự nó chứng minh lịch sử mọi lần đọc file.

## Tracking evaluation: metric nguyên trạng

| Metric | Giá trị |
|---|---:|
| HOTA | 0.5193 |
| DetA / AssA / LocA | 0.4145 / 0.6589 / 0.7988 |
| IDF1 | 0.7074 |
| MOTA | 0.4453 |
| MOTP | 0.7586 |
| FP / FN / IDSW | 59 / 78 / 0 |
| IDTP / IDFP / IDFN | 168 / 60 / 79 |

Nguồn: [evaluation.json](../outputs/external_validation/kitti_0001/evaluation.json), evaluator của project với CLEAR IoU≥0.5. **Không phải official KITTI metrics**: evaluator không áp dụng DontCare, ignored classes hoặc difficulty rules KITTI. Gate bài lab còn xuất trong JSON không phải acceptance gate cho external validation. Không diễn giải 0 IDSW thành identity hoàn hảo.

## DontCare audit riêng

[prediction_audit.csv](../outputs/external_validation/kitti_0001/prediction_audit.csv) liệt kê cả 228 predictions, IoU tốt nhất với GT, CLEAR match và overlap DontCare. Overlap là **max intersection / diện tích prediction** với một vùng DontCare trong cùng frame, không phải bbox IoU. Ngưỡng mô tả audit 0.5 chỉ để phân nhóm, không thay review threshold hoặc metric.

| Nhóm | Số box | Ý nghĩa |
|---|---:|---|
| MATCHED_TARGET | 169 | CLEAR match với target GT; ưu tiên nhóm này dù có overlap vùng ignore |
| DONTCARE_OVERLAP | 50 | Không match, ít nhất 50% diện tích nằm trong một DontCare |
| AMBIGUOUS | 4 | Không match, có overlap nhưng dưới 50% |
| REGULAR_FP | 5 | Không match, không overlap DontCare; FP theo reference, chưa tự động là hallucination |

Như vậy **50/59 raw FP** overlap mạnh DontCare. Không trừ 50 rồi công bố MOTA mới: đó chưa phải KITTI preprocessing chuẩn. 9 predicted tracks không là best-IoU owner của GT được liệt kê ở [false_positive_track_candidates.csv](../outputs/external_validation/kitti_0001/false_positive_track_candidates.csv). Nhiều track nằm trên xe thật trong DontCare; không phải 9 ghost được xác nhận. Điều tra tiếp xác nhận **P85 là duplicate prediction**, cập nhật nhãn trong bảng và issue_events.csv; các candidate khác chưa đủ evidence để gọi ghost ngữ nghĩa.

## Toàn bộ review flags

[flag_labels.csv](../outputs/external_validation/kitti_0001/flag_labels.csv) giữ 7 dòng raw, thêm event_id, association/IoU, DontCare overlap tại anchor và context image. Gap/reappeared cùng P64 dùng một event_id. Raw CSV/JSON trong `review/` không sửa.

| Frame | P | Reason | Event | Nhãn | Evidence |
|---:|---:|---|---|---|---|
| 4 | 8 | track_gap | P8_1_4 | TRUE_ISSUE | G6 còn thấy và có GT ở frame2–3, prediction thiếu |
| 7 | 8 | track_gap | P8_4_7 | TRUE_ISSUE | G6 còn thấy và có GT ở5–6 |
| 19 | 8 | track_gap | P8_17_19 | TRUE_ISSUE | G6 còn thấy và có GT ở18 |
| 29 | 92 | track_gap | P92_26_29 | BENIGN_EVENT | Xe nhỏ ở DontCare, chưa có target GT trong khoảng này |
| 30 | 64 | track_gap | P64_17_30 | UNCERTAIN | Hai box ở biên; frame30 có98.4% diện tích trong DontCare, không có GT identity tương ứng |
| 30 | 64 | track_reappeared | P64_17_30 | UNCERTAIN | Trùng sự kiện gap, không thêm issue độc lập |
| 31 | 92 | track_gap | P92_29_31 | BENIGN_EVENT | Frame30 là DontCare; G12 xuất hiện31, prediction match IoU0.858 |

Tổng **3 TRUE_ISSUE, 2 BENIGN_EVENT, 0 FALSE_ALERT, 2 UNCERTAIN**, 6 sự kiện. BENIGN ở đây phụ thuộc policy target/DontCare đã khai báo; không có nghĩa detector liên tục hoàn hảo trên mọi xe nhìn thấy. TRUE_ISSUE gán cho khoảng sự kiện, không yêu cầu box ở anchor sai.

Ảnh: [P8 context](../outputs/external_validation/kitti_0001/images/P8_context.jpg), [P64](../outputs/external_validation/kitti_0001/images/P64_context.jpg), [P92](../outputs/external_validation/kitti_0001/images/P92_context.jpg); ảnh từng sự kiện và toàn bộ31 frame ở `images/`.

| Rule | Flags | True | Benign | False | Uncertain | Nhận định |
|---|---:|---:|---:|---:|---:|---|
| track_gap | 6 | 3 | 2 | 0 | 1 | Vẫn tìm được gap cần sửa; precision trên5 trường hợp resolved=3/5, chưa là benchmark |
| track_reappeared | 1 | 0 | 0 | 0 | 1 | Trùng gap, chưa có lợi ích độc lập |
| large_motion_jump | 0 | 0 | 0 | 0 | 0 | Chưa đo được precision |
| abnormal_size_change | 0 | 0 | 0 | 0 | 0 | Không bắt được duplicate/localization ổn định |
| low_consecutive_iou | 0 | 0 | 0 | 0 | 0 | Liên tục geometry không bảo đảm đúng identity |
| possible_fragmentation | 0 | 0 | 0 | 0 | 0 | Không bắt association conflict; candidate G7 không phải split đã xác nhận |

Không đủ cơ sở nói bốn rule không kích hoạt đã “fail” toàn diện. Chúng không phát hiện các sự kiện cần review được liệt kê dưới đây trong sample này.

## Identity analysis

[identity_P54_by_frame.csv](../outputs/external_validation/kitti_0001/identity_P54_by_frame.csv) là trace đầy đủ; [P54_identity_context.jpg](../outputs/external_validation/kitti_0001/images/P54_identity_context.jpg) thể hiện box/ảnh. G95=KITTI94; G96=KITTI95.

| MOT frame | Best GT | Best IoU | CLEAR GT |
|---:|---:|---:|---:|
|16|96|0.6036|96|
|17|96|0.6508|96|
|18|96|0.6107|96|
|19|96|0.6244|96|
|20|96|0.6434|96|
|21|96|0.7531|96|
|22|96|0.5579|96|
|23|95|0.7145|95|
|24|95|0.7246|95|
|25|96|0.7817|95 (IoU0.5965)|
|26|96|0.6357|96|

**FACT:** một P54 được associate với hai GT identities. Best IoU chuyển ở23 và25; CLEAR chuyển ở23 và26 do ưu tiên nối cặp frame trước. G95 sống10–25, G96 sống8–28, nên đây không phải đơn giản GT mới thay GT đã kết thúc tại23.

Trong [motlib.py](../tools/motlib.py), `clear_mot` đếm khi **một GT đổi predicted ID** so với match gần nhất. G96 trước/sau vẫn P54; G95 khi match cũng chỉ P54. Vì thế IDSW=0 dù một predicted ID dùng cho nhiều GT. Báo `possible_identity_merge` / reference association conflict là phù hợp hơn việc ép IDSW tăng. Box GT chồng lấn, occlusion và độ khít khác nhau làm bản chất identity vật lý còn **UNCERTAIN**; không tuyên bố đã xác nhận hai xe bị nối chỉ từ IoU.

G7 fragmentation diagnostic dùng P5 và P60, nhưng P5 vẫn CLEAR-match G5 suốt31 frame và cùng tồn tại P60 từ17–31. Đây có thể là best-IoU ambiguity với xe gần nhau, **không có switch/split temporal được xác nhận**. Xem [G7_context.jpg](../outputs/external_validation/kitti_0001/images/G7_context.jpg).

## Missed issues: sự kiện, không cộng mọi FP/FN

[missed_issues.csv](../outputs/external_validation/kitti_0001/missed_issues.csv) chứa **2 sự kiện TRUE_ISSUE + 3 ứng viên UNCERTAIN không được flag trên track liên quan**. [issue_events.csv](../outputs/external_validation/kitti_0001/issue_events.csv) thêm trường hợp P64 đã được flag để kiểm tra ghost/reuse. [reference_issues.csv](../outputs/external_validation/kitti_0001/reference_issues.csv) giữ toàn bộ chẩn đoán frame-box riêng; không dùng số dòng của nó làm số lỗi thật.

1. **Confirmed missed track G10/KITTI9:** xe hiện diện20–31, 12 GT boxes không match prediction, không flag; [ảnh G10](../outputs/external_validation/kitti_0001/images/G10_context.jpg).
2. **Confirmed duplicate P85:** hai box ở23–24 trùng xe G93 với P77 đã có; CLEAR ghép P77, P85 thừa. Không flag; [frame24](../outputs/external_validation/kitti_0001/images/frames/000024.jpg). Đây là false-positive duplicate track, không phải vật thể ma.
3. **UNCERTAIN:** possible_identity_merge P54 nói trên.
4. **UNCERTAIN:** fragmentation candidate G7 nói trên.
5. **UNCERTAIN:** P7 frame1 box nhỏ ở biên, không match, cần xác định target extent trước gọi large localization error hoặc ghost; [ảnh candidates](../outputs/external_validation/kitti_0001/images/fp_candidates.jpg).

Đã kiểm ID switch: CLEAR0 và chưa xác nhận switch độc lập khác. Đã kiểm ghost: không đủ evidence xác nhận hallucinated-object track; DontCare không thể dùng làm bằng chứng ghost. Đã kiểm localization: evaluator có12 loose-box diagnostics, các trường hợp còn phụ thuộc occlusion/box convention; không tự gán tất cả thành lỗi cần sửa. **2 là số missed events xác nhận tối thiểu, không phải tổng lỗi thực tế hay recall chuẩn**. Lỗi có thể tình cờ thấy trong context track khác, nhưng không coi analyzer đã nhắm đúng lỗi.

## So sánh và phạm vi review

Hai clip cũ:29 raw flags đều gán TRUE_ISSUE, nhưng25 tập trung trên hai static ghost và7 reappeared trùng gap. Sample ngoài: chỉ3/7 true,2 benign theo DontCare,2 uncertain. Gap vẫn hữu ích; annotation policy, camera di động và xe nhỏ tạo khác biệt rõ. Không so precision trực tiếp như cùng phân phối; cũng không kết luận chất lượng giảm bao nhiêu phần trăm tổng quát.

Anchor scope6/31=19.35%. Với toàn khoảng gap cộng±2 frame, gộp thành [1,9] và[15,31]: **26/31=83.87%**, potential review reduction **16.13%**. Chưa đo thời gian người dùng; scope nhỏ hơn không bảo đảm không bỏ lỗi.

## Tests, tái lập audit và limitations

**13/13 tests PASS, 2.132s**, gồm10 test cũ và3 converter tests: frame base/ID offset, LTRB→xywh, mọi class giữ/bỏ, DontCare, malformed/duplicate/nonfinite/missing inputs, output lặp và thứ tự dòng. [final_tests.log](../outputs/external_validation/kitti_0001/final_tests.log). Dòng FFmpeg invalid-video do test âm tính; suite exit0.

Tái lập phần audit trên artifact đã khóa (không inference/download):

```powershell
Set-Location 'D:\LCOM108_NMLT\code\100_bai_code\tep_chua_python\semi_auto_video_tracking'
.venv\Scripts\python.exe -X utf8 tools/audit_kitti_evaluation.py
.venv\Scripts\python.exe -X utf8 -m unittest discover -s tests -v
```

Helper cũ `validate_kitti_sample.py` tạo visualization/statistics ban đầu; nếu chạy lại helper đó, chạy `audit_kitti_evaluation.py` sau cùng để xuất lại event-level missed_issues và flag labels có event_id. Converter không ghi đè file đã tồn tại; final audit kiểm conversion trong bộ nhớ. Không thay đổi raw MOT/flags/evaluation.

Giới hạn:31 frame/một sequence, sample rút gọn từ mirror, không xác thực độc lập lại toàn bộ annotation KITTI, JPEG conversion, COCO bus không có class tương ứng và Van không có class riêng, GT class-agnostic custom policy, không official DontCare semantics, không human timing/adjudicator độc lập. Timestamp là process evidence cục bộ. Không tune threshold và không train.

## Kết luận

Đây là **external held-out sample validation**. Nó tăng niềm tin vào khả năng tái lập và khả năng tìm gap; giảm niềm tin vào việc dùng riêng flags để bao phủ đủ lỗi annotation. Chưa đủ evidence để tune threshold. Bước kỹ thuật tiếp theo hợp lý là một evaluation adapter tách biệt xử lý KITTI ignore policy theo chuẩn, kiểm chứng matching/identity và nhãn với annotator độc lập, rồi thêm sequence giữ riêng. Không sửa analyzer chỉ để làm đẹp sample31 frame này.

File mới của phase: converter, converter tests, hai helper validation/audit, hai docs EXTERNAL, data/external_validation và outputs/external_validation. Thay đổi hiện tại chỉ hoàn thiện tests/evidence/docs; lab gốc không sửa, không commit/push.
