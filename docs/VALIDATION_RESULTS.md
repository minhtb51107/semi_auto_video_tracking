# Semi-Auto Video Tracking — Validation Results

Validation sơ bộ trên hai clip hiện có, ngày 2026-09-23. Không phải benchmark chuẩn hoặc nghiên cứu có annotator độc lập. Không chỉnh logic tracker/analyzer, threshold hay ground truth.

## Kết quả chính

**FACT:** Đã phân loại đủ 29 flag, kiểm tra ảnh của 22 sự kiện khác nhau. Cả 29 được gán TRUE_ISSUE theo phạm vi sự kiện; 25 flag liên quan hai track nhận nhầm vật thể tĩnh, 7 reappeared trùng gap. Analyzer bỏ sót ID switch của GT5 tại frame 94, clip 01. Không thể suy ra chất lượng tổng quát từ precision trên mẫu nhỏ này.

**FACT:** Đổi tên project và chạy lại pipeline trước validation đã thành công: 10/10 tests, 14 lệnh subprocess exit 0, cả hai MOT giống SHA-256 trước đổi tên. Xem [RENAME_VERIFICATION.md](RENAME_VERIFICATION.md) và [acceptance.json](../outputs/runs/renamed_verified/acceptance.json). Không thiếu file trong inventory cũ; lab giữ nguyên. Không commit/push.

## Dữ liệu và phương pháp

| Clip | Video | Reference dùng đánh giá | Frames | Pred boxes / tracks | Flags / anchor frames |
|---|---|---|---:|---:|---:|
| 01 | assets/guide/clip-01-preview.mp4 | gold/clip_01/gt.txt | 190 | 622 / 12 | 27 / 20 |
| 02 | assets/guide/clip-02-preview.mp4 | data/clips/clip_02/gt/gt.txt | 60 | 226 / 7 | 2 / 2 |

Tracking và CSV/JSON review lấy từ `outputs/runs/renamed_verified/clip_*/`. Hai `annotations/clip_*/gt.txt` là fixtures annotation dùng tests, không thay thế reference trên. Không cộng lại flags trong các run lịch sử hoặc dữ liệu cố ý làm sai.

[review_tracks.py](../tools/review_tracks.py), hàm analyzer, chỉ dùng MOT; không dùng GT. [review_thresholds.json](../configs/review_thresholds.json) giữ nguyên: gap >=1 frame thiếu, reappeared >=5; các cặp frame liền nhau được kiểm tra motion/đường chéo >1.5, tỷ lệ size hai chiều >2, IoU <0.1. Fragmentation yêu cầu endpoint cách 1–5 frame và IoU >=0.3, giữa các track không chồng thời gian.

[motlib.py](../tools/motlib.py), `clear_mot`, ưu tiên cặp nối từ frame trước rồi Hungarian với IoU >=0.5; lịch sử identity dùng để đếm switch. [evaluate_tracking.py](../tools/evaluate_tracking.py), `diagnose`, bổ sung coverage/ghost/fragmentation theo best IoU; đây không hoàn toàn là phép matching một-một của CLEAR. Loose box được chẩn đoán khi 0.5 <= best IoU <0.60; báo cáo evaluator gốc chỉ giữ top 30. Helper validation xuất đủ danh sách, kiểm tra top 30 trùng evaluator và kiểm tra trace CLEAR trùng FP/FN/MOTP cùng IDSW đã lưu.

[validate_review_flags.py](../tools/validate_review_flags.py) chỉ tạo evidence offline, reuse parser/IoU/evaluator và hàm vẽ hiện có. Nhãn do tôi đối chiếu reference và ảnh, lưu riêng trong [adjudications.json](../outputs/validation/adjudications.json); không phải kết luận tự động của heuristic hay đánh giá độc lập của con người. Nếu chạy helper không có adjudications, nhãn mặc định là UNCERTAIN.

Kiểm tra căn frame bằng ảnh decode so với JPEG gốc: 189/190 frame clip 01 và 60/60 clip 02 có sai khác nhỏ nhất ở cùng index trong lân cận ±1. Frame 48 clip 01 gần frame 49 hơn rất nhẹ (MAE 2.027 so với 2.060 trên thang 255); không thấy dịch frame có hệ thống, nhưng đây không phải chứng minh ảnh bitwise giống nhau. Xem [alignment_check.json](../outputs/validation/alignment_check.json).

## Nhãn từng flag

[flag_labels.csv](../outputs/validation/flag_labels.csv) chứa đủ frame_id, track_id, reason, observed_value, threshold, nhãn, reference liên quan, khoảng thiếu và đường dẫn ảnh. Đơn vị gán nhãn là sự kiện trên cùng track từ previous_frame_id đến frame_id, không chỉ box ở frame cảnh báo.

- TRUE_ISSUE: có lỗi box/identity/missing cần sửa trong sự kiện.
- BENIGN_EVENT: hiện tượng hợp lệ không gây sai annotation đáng kể.
- FALSE_ALERT: không có vấn đề đáng review.
- UNCERTAIN: chưa đủ evidence; không ép thành true/false.

| Clip / predicted track | Flags | Kết luận và evidence |
|---|---:|---|
| 01 / P2 | 1 | TRUE_ISSUE: taxi GT3 vẫn hiện diện nhưng thiếu prediction ở 14–16; trở lại 17. |
| 01 / P12 | 18 | TRUE_ISSUE: box trên cấu trúc/quầy biển ven đường, không phải xe; 50 box không match reference, max IoU với GT 0.08072. |
| 01 / P44 | 7 | TRUE_ISSUE: vật đánh dấu đường đỏ-trắng cố định bên trái, không phải xe; 33 box không match reference, max IoU 0.02003. |
| 01 / P47 | 1 | TRUE_ISSUE: phần xe GT6 còn nhìn thấy sau xe bus ở 119, reference có box nhưng prediction mất. |
| 02 / P9 | 2 | TRUE_ISSUE: xe đen GT5 còn hiện diện ở 31–32 và 34 nhưng prediction thiếu. |

P12/P44 cần loại bỏ hoặc sửa track nhận nhầm, **không** điền thêm box vào gap. Đây là lý do một gap flag có thể dẫn tới lỗi thật khác với tên rule. Tổng cộng 0 BENIGN_EVENT, 0 FALSE_ALERT, 0 UNCERTAIN trong 29 flag đã xem. Không có tập negative độc lập để chứng minh rule không gây false alert; các ứng viên ngoài flags vẫn có trường hợp UNCERTAIN.

## Thống kê và quyết định từng rule

Precision sơ bộ = TRUE_ISSUE / (TRUE_ISSUE + BENIGN_EVENT + FALSE_ALERT), bỏ UNCERTAIN; chỉ có ý nghĩa trên tập flag được xem này. Sự kiện lặp và đánh giá bởi cùng người phân tích làm mẫu kém độc lập.

| Reason | Flags | TRUE | BENIGN | FALSE | UNCERTAIN | Precision mẫu | Bắt được / giới hạn / đề xuất |
|---|---:|---:|---:|---:|---:|---:|---|
| track_gap | 22 | 22 | 0 | 0 | 0 | 22/22 | 4 gap của xe thật và 18 sự kiện trên ghost; hữu ích nhất. Không bắt entry/exit bị thiếu hoặc đổi ID. Giữ. |
| track_reappeared | 7 | 7 | 0 | 0 | 0 | 7/7 | Tất cả trùng gap của P12/P44; không thêm sự kiện mới. Nên nghiên cứu gộp hiển thị với gap; chưa sửa. |
| large_motion_jump | 0 | 0 | 0 | 0 | 0 | N/A | Chưa có evidence chất lượng; không bắt switch giữa hai ID. Chưa đủ cơ sở bỏ/chỉnh. |
| abnormal_size_change | 0 | 0 | 0 | 0 | 0 | N/A | Chưa chứng minh hữu ích; box rộng sai nhưng ổn định có thể không kích hoạt. Giữ để validation thêm. |
| low_consecutive_iou | 0 | 0 | 0 | 0 | 0 | N/A | Độ liên tục pred không đảm bảo box đúng với GT; chưa đủ cơ sở bỏ/chỉnh. |
| possible_fragmentation | 0 | 0 | 0 | 0 | 0 | N/A | Bỏ sót GT5 do endpoint IoU thấp. Cần tập độc lập trước thay threshold. |

Không rule nào được chứng minh là gây nhiều FALSE_ALERT nhất. `track_reappeared` gây dư thừa nhiều nhất về số lần review, khác với cảnh báo sai. Không bỏ rule nào trong phase này.

## Lỗi bị bỏ sót và ứng viên cần kiểm tra

[reference_issues.csv](../outputs/validation/reference_issues.csv) chứa 249 chẩn đoán frame-box. [missed_issues.csv](../outputs/validation/missed_issues.csv) chứa 229 dòng không có flag đúng frame và cùng predicted track (`analyzer_flagged=False`), kèm các cột bắt buộc và trạng thái evidence. Với missing prediction, helper dùng các predicted ID liên quan GT để kiểm tra phạm vi cùng track.

| Loại chẩn đoán | Tổng | Không flag đúng frame/track |
|---|---:|---:|
| missed_detection | 71 | 71 |
| ghost_false_positive | 87 | 69 |
| unmatched_prediction | 30 | 30 |
| loose_box | 57 | 55 |
| id_switch | 1 | 1 |
| fragmentation | 1 | 1 |
| false_continuation_candidate | 2 | 2 |

Đây là các **dòng chẩn đoán có thể chồng lặp**, không phải 249 lỗi độc lập hoặc recall chuẩn. Gap flag nằm ở frame trở lại, vì vậy các frame thiếu bên trong gap có thể thuộc danh sách trên nhưng vẫn nằm trong context review. CSV phân biệt `same_track_context` và `any_review_context`; không đồng nhất exact flag với khả năng người xem context nhận ra lỗi.

Trong 229 dòng: 74 TRUE_ISSUE (65 frame ghost P12/P44, 7 frame thiếu trong gap đã xem, 2 dòng IDSW/fragmentation cùng một nguyên nhân); 6 UNCERTAIN; 149 REFERENCE_DIAGNOSTIC chưa được adjudicate từng frame bằng mắt. Nhóm cuối là bằng chứng sai lệch so với reference, không tuyên bố mọi dòng đều là lỗi ngữ nghĩa đã xác nhận.

**FACT:** CLEAR clip 01 có FP=102, FN=53, IDSW=1; clip 02 FP=17, FN=18, IDSW=0. Không có GT track bị bỏ lỡ hoàn toàn theo coverage evaluator; có 71 frame-box GT không match. Ghost tĩnh vẫn có nhiều frame không flag khi box tồn tại liên tục. Loose box ổn định và prediction không match vẫn bị analyzer bỏ qua. Ví dụ GT8/P56 clip 01 có box rộng, xem gallery; IoU với GT thấp không tự động chứng minh reference hoàn hảo.

**UNKNOWN:** P66 ở 169–170 clip 01 còn có phần xe đỏ ở mép ảnh nhưng reference GT8 kết thúc 168; không đủ cơ sở gọi là ghost thật hay switch mới. P4 ở 1–2 clip 02 là vùng cắt sát biên. P7 ở 57–58 clip 02 tồn tại sau GT4 kết thúc 56, nhưng vẫn có phần vật thể tại biên. Sáu dòng này giữ UNCERTAIN; không xác nhận false continuation chỉ vì GT kết thúc. Không tìm được thêm lỗi identity chắc chắn ngoài GT5.

### ID switch đã biết: clip 01, frame 94

**FACT:** GT5 liên tục từ 79–138; P28 match ở 89–90, P33 bắt đầu ở 94 rồi tiếp tục tới 138. Evaluator đếm ID switch tại 94; chẩn đoán fragmentation cùng GT là cùng nguyên nhân, không đếm thành hai lỗi độc lập.

P28(frame 90) → P33(frame 94) cách 4 frame, nằm trong giới hạn 5, nhưng endpoint IoU = **0.158001**, thấp hơn **0.3**. Do đó possible_fragmentation không kích hoạt; track_gap chỉ xem cùng ID nên không bắt việc thay ID này. Xem [ảnh 89–96](../outputs/validation/images/clip_01/id_switch_G5_P28_P33.jpg).

Frame 94 tình cờ nằm trong context của gap P12. CSV ghi exact flag=False, same-track context=False, any-context=True. Đây là khả năng nhìn thấy tình cờ, không phải analyzer đã phát hiện ID switch.

## Candidate review scope

Chọn chính sách validation cố định: xem toàn bộ khoảng từ previous_frame_id đến frame_id, thêm 2 frame trước/sau, cắt theo clip, gộp các khoảng chồng nhau hoặc liền nhau. Không chỉ lấy ±2 quanh anchor rồi bỏ qua giữa gap. [review_contexts.csv](../outputs/validation/review_contexts.csv) lưu 5 đoạn hợp nhất.

| Clip | Tổng frame | Anchor có flag | Candidate ratio | Đoạn context | Frame trong context | Review span | Potential review reduction |
|---|---:|---:|---:|---:|---:|---:|---:|
| 01 | 190 | 20 | 10.53% | 4 | 147 | 77.37% | 22.63% |
| 02 | 60 | 2 | 3.33% | 1 | 10 | 16.67% | 83.33% |
| Tổng | 250 | 22 | 8.80% | 5 | 157 | 62.80% | 37.20% |

Clip 01: [11,65], [74,107], [116,166], [169,175]; clip 02: [28,37], endpoints tính cả hai đầu. Với padding 0, scope vẫn là 129/250=51.6% (8 đoạn); padding 5 là 183/250=73.2% (4 đoạn). Tỷ lệ phụ thuộc context policy. **Không gọi đây là thời gian tiết kiệm**: chưa đo thao tác người dùng, còn lỗi ngoài scope, và không thể dùng kết quả để đảm bảo chất lượng khi chỉ review phần được flag.

## Visualization và evidence

Mỗi sự kiện có ảnh toàn cảnh, ROI phóng lớn, predicted box/ID P#, reference nét đứt xanh G#, reason và frame trước/sau. 29 dòng flag trỏ vào 22 sheets; reappeared dùng chung sự kiện gap. Có ảnh từng frame trong `images/clip_*/context_frames/` để xem đầy đủ khoảng dài.

- [Tất cả anchor clip 01](../outputs/validation/images/clip_01/flag_anchor_atlas.jpg), [clip 02](../outputs/validation/images/clip_02/flag_anchor_atlas.jpg).
- [Missing entry GT5](../outputs/validation/images/clip_01/missing_entry_G5.jpg), [loose/unmatched GT8](../outputs/validation/images/clip_01/loose_or_unmatched_G8.jpg).
- [P66 biên ảnh](../outputs/validation/images/clip_01/unflagged_ghost_P66.jpg), [P4 biên ảnh](../outputs/validation/images/clip_02/unflagged_ghost_P4.jpg), [P7 continuation chưa chắc chắn](../outputs/validation/images/clip_02/uncertain_continuation_P7.jpg).
- [summary.json](../outputs/validation/summary.json), [rule_summary.csv](../outputs/validation/rule_summary.csv), [integrity_checks.json](../outputs/validation/integrity_checks.json).

## Threshold và bước tiếp theo

**INFERENCE:** Gap hữu ích để hướng người xem tới track có vấn đề, nhưng lặp trên ghost có thể làm tăng khối lượng review. Reappeared nên được xem như thông tin bổ sung cùng gap trong thử nghiệm tương lai; chưa thay output hiện tại.

Không chỉnh threshold ngay. Nếu thử ngưỡng endpoint IoU 0.15, cặp GT5 nói trên sẽ qua điều kiện IoU; đây chỉ là giả thuyết phát sinh từ một lỗi, dễ nối nhầm hai xe gần nhau. Cần so sánh 0.15 với 0.3 trên clip giữ riêng trước áp dụng. Chưa có evidence đề xuất giá trị mới cho motion/size/IoU liên tiếp. Config cũ giữ nguyên hash.

Ưu tiên tiếp theo: annotator độc lập xác nhận bảng nhãn, thống nhất quy tắc occlusion/biên ảnh, lấy thêm clip độc lập và mẫu frame không flag; sau đó đánh giá event-level precision/coverage và các trường hợp switch/fragmentation. Chỉ khi có tập giữ riêng mới thử threshold; human timing là bước đo riêng sau đó. Trước CVAT vẫn cần quy ước frame/ID, đối chiếu import/export và quy trình sửa/kiểm tra của annotator; phase này chưa tích hợp.

Giới hạn: hai clip cùng bối cảnh, 250 frame; ghost tĩnh chiếm đa số flags; không có negative sample đủ rộng; reference có bất định tại biên; phần lớn chẩn đoán ngoài flags chưa được xem từng frame; không có human timing hay người gán nhãn độc lập. Số liệu là FACT tính từ file; nhãn là adjudication sơ bộ có evidence; hiệu quả trên dữ liệu khác là UNKNOWN.

## Tái lập và kiểm tra

PowerShell từ project mới, môi trường và input/weights local theo README:

```powershell
Set-Location 'D:\LCOM108_NMLT\code\100_bai_code\tep_chua_python\semi_auto_video_tracking'
.venv\Scripts\python.exe -X utf8 -m unittest discover -s tests -v
.venv\Scripts\python.exe -X utf8 tools/reproduce_mvp.py
.venv\Scripts\python.exe -X utf8 tools/validate_review_flags.py --run-dir outputs/runs/renamed_verified --adjudications outputs/validation/adjudications.json
```

Runner tạo run mới, không ghi đè `renamed_verified`; muốn validation run mới, thay `--run-dir` và dùng `--out-dir` khác để giữ evidence hiện tại. Nhãn adjudication chỉ tái sử dụng nếu các sự kiện vẫn giống nhau; với dữ liệu mới phải review lại.

Helper đã chạy exit 0; assertions kiểm tra matching/evaluator và hash đầu vào pass. [Integrity evidence](../outputs/validation/integrity_checks.json) xác nhận 645 file lab không đổi, 7 module production được kiểm tra cùng config không đổi, không thiếu file inventory. Test/pipeline gate được lưu ở run mới, không dùng kết quả run cũ để tuyên bố pass sau rename.

Sau khi thêm helper và báo cáo validation, chạy lại toàn bộ tests: **10/10 PASS, 1.647 s**, exit 0; [regression_tests.log](../outputs/validation/regression_tests.log). Dòng FFmpeg `moov atom not found` đến từ test video không hợp lệ, test đó vẫn PASS.

File mới: helper validation, báo cáo này, RENAME_VERIFICATION.md, dữ liệu/ảnh/log trong outputs/validation và archive evidence/rename. File sửa: README và các tham chiếu đường dẫn được liệt kê trong evidence/rename/path_updates.json; venv activation/launcher được tạo lại. Không thêm feature sản phẩm, model, training, frontend, API hoặc tự sửa annotation.
