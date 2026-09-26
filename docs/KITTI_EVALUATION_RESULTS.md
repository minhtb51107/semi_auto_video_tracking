# KITTI Evaluation Adapter — Results on 0001

Kết quả này là **KITTI-aware adjusted audit** trên external held-out sample 0001. Không phải official KITTI score, generalization proof hoặc production validation. Không tune analyzer/tracker/threshold.

## Input và integrity

Adapter dùng đúng prediction vòng 1: 228 boxes/22 tracks và raw review output 7 flags/6 frames. Hash prediction, raw evaluation và label được lưu trong [evaluation.json](../outputs/external_validation/kitti_0001/kitti_semantics/evaluation.json). Hash khóa trong `blind_lock.json` vẫn khớp sau lần chạy; artifact vòng 1 nằm nguyên vị trí.

Semantics và nguồn chính thức được ghi trong [KITTI_EVALUATION_ADAPTER.md](KITTI_EVALUATION_ADAPTER.md). Sau preprocessing Car:

- GT: 247 boxes/15 tracks custom vòng 1 → **203 Car boxes/14 tracks**.
- Loại 13 Van boxes làm distractor và 31 Car boxes do truncation >0 hoặc occlusion >2.
- Prediction: 228 boxes/22 tracks → **146 boxes/14 tracks**.
- Loại 82 prediction: 11 match Van, 19 match invalid Car, 50 thỏa DontCare, 50 có height <=25; hai nhóm cuối chồng nhau 48 boxes.

## Raw và adjusted project metrics

| Metric | Raw project | KITTI-aware adjusted | Thay đổi |
|---|---:|---:|---:|
| HOTA | 0.5193 | 0.5909 | +0.0716 |
| DetA | 0.4145 | 0.4975 | +0.0830 |
| AssA | 0.6589 | 0.7112 | +0.0523 |
| LocA | 0.7988 | 0.8067 | +0.0079 |
| IDF1 | 0.7074 | 0.7966 | +0.0892 |
| MOTA | 0.4453 | 0.6502 | +0.2049 |
| MOTP | 0.7586 | 0.7676 | +0.0090 |
| FP | 59 | 7 | −52 |
| FN | 78 | 64 | −14 |
| IDSW | 0 | 0 | 0 |

MOTA thay đổi nhiều nhất vì FP giảm 88.1% và denominator/target GT cũng đổi. IDF1, DetA và HOTA tăng rõ; localization chỉ đổi nhẹ. Đây không phải phép “sửa score”: raw và adjusted trả lời hai policy khác nhau.

## DontCare và small-box decomposition

Trong 52 unmatched predictions bị bỏ bởi hợp hai quy tắc:

- 50 có DontCare IoA >0.5;
- 50 có height <=25;
- 48 thỏa cả hai;
- 2 chỉ DontCare và 2 chỉ small-box.

| Adjusted policy | FP | MOTA | IDF1 | HOTA |
|---|---:|---:|---:|---:|
| Full KITTI-like preprocessing | 7 | 0.6502 | 0.7966 | 0.5909 |
| Không DontCare ignore, vẫn bỏ box nhỏ | 9 | 0.6404 | 0.7920 | 0.5863 |
| Không small-box ignore, vẫn dùng DontCare | 9 | 0.6404 | 0.7920 | 0.5863 |
| Không cả hai unmatched-ignore rules | 59 | 0.3941 | 0.6933 | 0.5228 |

Vì overlap lớn, không được gán toàn bộ −52 FP riêng cho DontCare. DontCare đánh dấu 50 predictions; **marginal effect là −2 FP** khi small-box rule vẫn bật. Hợp hai rule làm FP 59→7.

## Association behavior

Sau preprocessing có 139 CLEAR matches, IDSW=0 và không predicted ID nào match nhiều valid Car GT. Điều này khác raw audit vì invalid/distractor GT đã bị loại trước metric.

### P54

Raw audit thấy P54 chuyển best association G96→G95 ở frame 23–24, rồi về G96. Adapter cho thấy:

- frame 16–22: P54 được giữ và match G96;
- frame 23–24: P54 match G95 nhưng G95 đang occlusion 3, nên cả GT và matched prediction bị ignore;
- frame 25–26: P54 match G96 nhưng G96 lúc này thuộc invalid occlusion/truncation segment, nên cũng bị ignore.

Do đó `possible_identity_merge` vẫn là quan sát hữu ích ở raw visual audit, nhưng **không còn là identity conflict trong evaluable Car set**. Adjusted IDSW=0 không chứng minh identity vật lý hoàn hảo; nó nói các frame gây xung đột nằm ngoài policy chấm.

### P85

G93 là KITTI track 92, class Van. P77 có IoU cao hơn và được Hungarian match vào Van distractor rồi bỏ. P85 trùng cùng Van ở frame 23–24 nhưng là duplicate thứ hai, không được distractor hấp thụ; height >25 và DontCare IoA <0.5 nên vẫn được giữ và đóng góp **2 adjusted FP**.

Kết luận vòng 1 “duplicate prediction” giữ nguyên. Diễn giải chính xác hơn: duplicate trên một Van distractor; KITTI-like preprocessing bỏ một detection, nhưng duplicate còn lại vẫn bị phạt.

### G10

G10 là KITTI Car track 9, truncation 0, occlusion 2, 12 boxes ở frame 20–31. Nó vẫn là target hợp lệ và không có match. Kết luận **missed GT track** không đổi; 12 boxes tiếp tục đóng góp FN.

## Evaluable errors sau preprocessing

- FP=7: gồm 2 P85 duplicate boxes và 5 unmatched kept boxes khác; “FP” vẫn là metric event, không tự động là 7 hallucinated objects.
- FN=64: gồm toàn bộ G10 và các đoạn Car hợp lệ khác không match.
- IDSW=0; raw P54 association conflict bị ignore theo policy.
- Một distractor/ignore region chỉ hấp thụ một prediction; duplicate vẫn có thể lộ thành FP.

[prediction_preprocessing_audit.csv](../outputs/external_validation/kitti_0001/kitti_semantics/prediction_preprocessing_audit.csv) và [adjusted_clear_matches.csv](../outputs/external_validation/kitti_0001/kitti_semantics/adjusted_clear_matches.csv) là evidence theo frame.

## Evaluator cũ gây hiểu nhầm ở đâu

Raw evaluator không sai theo contract MOT class-agnostic của project, nhưng dễ bị đọc sai khi áp vào KITTI:

1. Nó coi Van là target thay vì distractor trong custom GT vòng 1.
2. Nó tính prediction trong DontCare, box nhỏ và prediction match invalid GT như dữ liệu bình thường.
3. FP=59 trông giống 59 hallucinations; thực tế phần lớn thuộc ignore policy.
4. IDSW chỉ đo GT→pred ID changes; không phát hiện pred→nhiều GT merge. Sau KITTI preprocessing, P54 conflict lại nằm ngoài evaluable set.
5. So sánh raw MOTA với KITTI leaderboard sẽ không hợp lệ.

Vì thế cả hai output được giữ song song và đặt tên khác nhau, không ghi đè.

## Tests và kết luận

[test_evaluate_kitti_semantics.py](../tests/test_evaluate_kitti_semantics.py) kiểm Van distractor, invalid Car, class exclusion, malformed/nonfinite label, thứ tự matching, small-box boundary `<=25`, DontCare strict `>0.5`, duplicate Hungarian và deterministic preprocessing. Toàn bộ suite được chạy sau cùng; log ở `outputs/external_validation/kitti_0001/kitti_semantics/tests.log`.

External sequence thứ hai là bước tiếp theo hợp lý. Adapter đã tách policy khỏi analyzer, nên sequence mới có thể kiểm tra xem tỷ lệ overlap DontCare, P54-like ambiguity và hiệu quả gap có lặp lại hay không mà không tune theo 0001. Nên chọn một sequence đủ dài, có Car/Van/DontCare và occlusion; khóa prediction trước khi xem GT như vòng 1.
