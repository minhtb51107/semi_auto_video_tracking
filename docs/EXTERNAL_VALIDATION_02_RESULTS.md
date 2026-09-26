# Semi-Auto Video Tracking — External held-out sample validation #2

## Kết quả và phạm vi

KITTI Tracking **0000, 154 frame**. Reuse blind artifacts đã khóa; không tải lại ảnh, chạy lại tracker, tune hoặc sửa core. Đây là **external held-out sample validation**, không phải official KITTI score hay bằng chứng tổng quát hóa.

- Blind: **534 boxes / 27 predicted tracks / 15 raw flags / 12 flagged frames**.
- 15 flags → 12 nhóm tự động theo track/khoảng → **11 review events** sau khi gộp handoff R009/R010.
- Raw flag verdict: **11 TRUE_ISSUE / 0 BENIGN / 0 FALSE / 4 UNCERTAIN**.
- Event verdict: **8 TRUE_ISSUE / 0 BENIGN / 0 FALSE / 3 UNCERTAIN**.
- **4 confirmed missed events**, sau loại trùng: một severe undercoverage, một duplicate, hai lần fragmentation/đổi ID của cùng G1. Không lấy FP+FN làm số issue.
- **25/25 tests PASS**: giữ 22 baseline, thêm ba test integrity/event consolidation. Analyzer v2 chưa được implement.

Verdict là adjudication sơ bộ qua reference và ảnh bởi trợ lý, chưa có annotator độc lập. TRUE_ISSUE ở đây theo phạm vi annotation vehicle Car+Van của project. Sáu trong tám true review events liên quan Van: không được diễn giải chúng thành lỗi Car trong KITTI benchmark. Hai true events còn lại là reuse ID trên Car. Các trường hợp amodal/visible-only hoặc identity chưa phân giải giữ UNCERTAIN.

## Integrity và khôi phục phiên

Nguồn và protocol: [EXTERNAL_VALIDATION_02_DATASET.md](EXTERNAL_VALIDATION_02_DATASET.md). Blind lock được tạo `2026-09-23T20:14:54.480435+00:00`; Phase B record `2026-09-23T20:15:46.8830922Z`. Phiên tiếp tục phát hiện label, conversion và evaluation đã tồn tại; dùng lại thay vì tải/convert lại. Không tự tạo timestamp lịch sử.

`blind_lock.json` ghi đầy đủ model/config/source/output hashes và snapshot hash của toàn bộ outputs vòng 1. `integrity_verified.json` kiểm **397 mục**: protected files, outputs khóa, outputs 0001, protocol/manifests, 154 PNG và 154 JPEG. Tất cả khớp. Hash xác nhận tính nguyên vẹn hiện tại; thứ tự blind/GT dựa trên protocol và log cục bộ, không phải chứng nhận độc lập.

| Artifact | SHA-256 |
|---|---|
| review_tracks.py | cc035e26bfb111f6b0fd3c0acd1c24b57d5a431796df2731df0a305a8a6cccfd |
| review_thresholds.json | 1e5fc143bcc7213fc45067059cd323a38b5e14ab7e9158013196c5a800a1155e |
| run_tracker.py | 00e6095a67ae227aacf7e063bd83385f4cf98fd067b3fab4224b6c738cb2ada1 |
| ByteTrack YAML | 395701d947a749179dee3e327b1181b730c4ca98e7cac5a2ab05280aae573b8b |
| yolo26n.pt | 9b09cc8bf347f0fc8a5f7657480587f25db09b34bf33b0652110fb03a8ad4fef |
| tracks.txt | 419dae1474f9903c08cafbf8274e7673c700f80c5320348b87e3c4ae0d0fdac9 |
| review_flags.json | 5f2a8f447cc112b7cc3e950ed5205b0a7e8712b7a4c4b2197927066b9127d779 |
| review_flags.csv | 87383ca721ce5a3e7e641d37024bf811d8b55db2f73f310959af3ff1d7ff1e5a |
| image acquisition manifest | ec6a166d225b279f9002c75e8652940ce54fa72c3da064722d6767399ad36eaa |
| PNG/JPEG frame manifest | 397f773139dfdaa8b49b547d96563a7ed6668f9635f5711f67faadca76305cd9 |

Raw evaluator, converter, motlib và adapter hashes cũng được kiểm theo lock. Threshold vẫn `experimental_uncalibrated`, đúng config vòng trước. Hai evaluator được chạy lại vào thư mục `recheck/`, không ghi đè kết quả cũ hoặc blind artifacts; metrics trùng bản lưu.

## Raw → KITTI-aware

| Metric | Raw project | KITTI-aware adjusted audit |
|---|---:|---:|
| HOTA | 0.4400 | 0.4794 |
| DetA | 0.4933 | 0.4684 |
| AssA | 0.3952 | 0.5101 |
| LocA | 0.7708 | 0.7328 |
| IDF1 | 0.5650 | 0.6172 |
| MOTA | 0.5140 | 0.4047 |
| MOTP | 0.7318 | 0.6885 |
| FP | 124 | 53 |
| FN | 125 | 65 |
| IDSW | 11 | 10 |
| GT boxes / tracks | 535 / 12 | 215 / 9 |
| Predicted boxes / tracks | 534 / 27 | 203 / 17 |

Nguồn: `evaluation.json`, `kitti_semantics/evaluation.json`. MOTA giảm dù FP/FN giảm: target denominator và class mix đổi, Van tương đối dễ theo dõi bị loại. Không so sánh hai cột như cùng một population được cải thiện thuật toán. MOTP ở đây là mean matched IoU; raw JSON làm tròn bốn số, adapter lưu số thực đầy đủ.

331 prediction bị bỏ: 244 matched Van, 16 matched ignored Car, 67 chỉ DontCare, 1 chỉ small-box, 3 cả DontCare và small-box. Tổng DontCare **70**, small-box **4**, giao **3**; không cộng 70+4 như hai tập rời nhau. GT bỏ 292 Van distractor và 28 truncated Car; còn 215 Car boxes. Các class khác không là target.

Sensitivity trong adapter sẵn có: tắt riêng DontCare nhưng vẫn small-box → FP120, FN65, IDSW8; policy đầy đủ → FP53, FN65, IDSW10. **Marginal DontCare effect −67 FP**, khác với 70 prediction có overlap ignore vì ba box còn bị small-box loại. Việc rematching có thể đổi IDSW; không sửa metric để ép kết quả tốt hơn. Tắt riêng small-box khi DontCare vẫn bật giữ lại thêm một box. Tất cả là audit policy hiện có, không tuning.

## Từng flag và event

`flag_labels.csv` có đủ 15 dòng: raw frame/track/reason/observed/threshold/previous frame, raw_group_id, final event_id, best GT/type/IoU, KITTI status, DontCare IoA, context và evidence. `association_by_frame.csv` chứa cả 534 prediction, nên association ở anchor không bị đánh đồng với toàn khoảng gap. `review_events.csv` là 11 event; `raw_review_groups.csv` giữ 12 nhóm trước adjudication.

| Event | Track; khoảng MOT frame | Reasons | Verdict | Evidence và ý nghĩa |
|---|---|---|---|---|
| R001 | P26; 24–26 | gap | TRUE | G4 Van thấy được, thiếu box25 |
| R002 | P26; 26–28 | gap | TRUE | Thiếu box27 trên G4 |
| R003 | P26; 29–31 | gap | TRUE | Thiếu box30 trên G4 |
| R004 | P26; 31–33 | gap | TRUE | Thiếu box32 trên G4 |
| R005 | P26; 35–38 | gap | TRUE | G4 vẫn thấy qua occlusion ở36–37 |
| R006 | P112; 103–105 | gap | UNCERTAIN | Cyclist che G1; chưa thống nhất visible/amodal correction |
| R007 | P152; 112–122 | gap + reappeared | UNCERTAIN | DontCare trước G7 entry, sau đó occlusion; không gán cả gap là lỗi |
| R008 | P112→P322; 135–137 | fragmentation | TRUE | White Van G1 còn thấy136 nhưng thiếu; ID mới137 |
| R009 | P187/P319; 129–146 | gap + reappeared | TRUE | P187 từ xe bên phải sang G14 bên trái; P319 bị ngắt cùng handoff. Gộp R010 |
| R011 | P229; 133–148 | gap + reappeared | TRUE | P229 reuse từ xe bên phải sang G14 bên trái148 |
| R012 | P363; 150–152 | gap | UNCERTAIN | G11/G15 chồng box, chưa rõ duplicate hay chuyển ownership |

Ảnh tương ứng `images/R001.jpg`…`R012.jpg`; R009 dùng cả R009/R010. Có full-resolution annotated context cho **154 frame** trong `images/frames/`. Green=GT, red=prediction, gray=excluded source rows; màu gray không thay thế status đầy đủ của KITTI adapter. R-label ở ảnh là raw group, final event mapping ở CSV. Nhiều khoảng gap cùng G4 được giữ thành các interruption riêng, không gộp cả lifetime thành một lỗi.

| Rule | Raw flags | TRUE | BENIGN | FALSE | UNCERTAIN | Kết luận sơ bộ |
|---|---:|---:|---:|---:|---:|---|
| track_gap | 11 | 8 | 0 | 0 | 3 | Hữu ích nhất; 7 true events sau gộp handoff |
| track_reappeared | 3 | 2 | 0 | 0 | 1 | Cả 3 trùng gap; 0 event mới |
| possible_fragmentation | 1 | 1 | 0 | 0 | 0 | Bắt G1 split135–137; chưa bắt các split dài hơn |
| large_motion_jump | 0 | 0 | 0 | 0 | 0 | Không đủ dữ liệu đánh giá precision |
| abnormal_size_change | 0 | 0 | 0 | 0 | 0 | Không đủ dữ liệu đánh giá precision |
| low_consecutive_iou | 0 | 0 | 0 | 0 | 0 | Không đủ dữ liệu đánh giá precision |

Confirmed fraction 11/15 raw flags, 8/11 events. Trong phần resolved không có benign/false, nhưng không được suy ra precision thật 100%: sample nhỏ, verdict phụ thuộc policy, còn uncertain và chưa có reviewer độc lập. Không có lý do tune threshold lúc này.

## Tìm lỗi ngoài flags

Screening toàn bộ GT/prediction 154 frame sinh **47 candidate rows**, mặc định UNCERTAIN: 1 severe undercoverage, 2 duplicate candidates, 11 CLEAR switches, 3 multi-GT predicted IDs, 5 GT fragmentation summaries, 9 no-CLEAR-owner/ghost candidates, 16 low-IoU pair candidates. Không có candidate continuation sau lifetime của majority GT theo check hiện tại. Đây không chứng minh không có mọi loại false continuation.

`track_coverage.csv` đo từng GT, `association_by_frame.csv` ghi từng pred, `issue_candidates.csv` giữ mọi candidate và verdict/evidence, `missed_issues.csv` giữ candidates chưa được analyzer nhắm tới (có cả UNCERTAIN/BENIGN), còn **`confirmed_missed_events.csv` mới là bốn event xác nhận**:

| ID | Loại | GT / Pred | Khoảng và evidence | KITTI semantics |
|---|---|---|---|---|
| U001 | Severe track undercoverage | G12 / không có stable owner | Lifetime131–154: raw CLEAR0/24; any-IoU≥.5 chỉ2/24. Ảnh M001,M043–M046 cho thấy dark Car giữa G9 và G14 không được bao phủ ổn định | Bỏ6 truncated rows131–136; **18 eligible rows137–154 vẫn 0 adjusted match** |
| U002 | Duplicate | G4 / P26+P140 | Frame99, gần như hai box đồng nhất trên orange Van. M002 và M025 cùng issue | DC IoA0; P26 match Van bị ignore, P140 unmatched còn lại là adjusted FP |
| U003 | Fragmentation / ID replacement | G1 / P1→P73 | P1 đến47, thiếu48–54, P73 từ55; M004_extended | Van distractor; lỗi annotation vehicle, không phải Car IDSW |
| U004 | Fragmentation / ID replacement | G1 / P73→P112 | P73 đến84, P112 từ88 sau occlusion; CLEAR rematch95; M005_extended | Van distractor; không đếm mỗi frame occluded thành một lỗi |

“Missed” nghĩa analyzer không nhắm vào vấn đề/track đó, không nhất thiết nằm ngoài mọi context window: U001 có thể tình cờ nhìn thấy khi reviewer mở context của event khác. M025 duplicate/ghost trùng U002, M019 lifetime summary trùng các split G1, không cộng thêm. Four là **lower bound của các event xác nhận trong audit**, không phải tổng lỗi thật hoặc recall denominator đầy đủ.

**Không xác nhận thêm:** ghost candidates P78/P109/P356 nằm trên xe thật trong DontCare, không phải hallucination; P192 near-exit localization bị truncated/ignore semantics và amodal ambiguity; G11/G15/P331 ownership/localization còn UNCERTAIN. Hình và status theo frame được giữ để reviewer kiểm tra. Không coi mọi FN/FP, best-IoU assignment hay CLEAR switch là annotation error.

## Identity analysis

| Predicted ID | Association evidence | Kết luận |
|---|---|---|
| P187 | CLEAR G10 f121–129; best GT f129 là G11 IoU.559 nhưng continuity giữ G10. Sau gap, G14 f145 IoU.760, f146 .671 | Ảnh R009 cho thấy chuyển xe từ bên phải sang bên trái: confirmed physical ID reuse, đã bị gap flag |
| P229 | CLEAR G11 f125–132, G15 f133 IoU.694; f148 best G14 IoU.559, raw CLEAR không gán vì cạnh tranh, adjusted gán G14 | Chuyển bên đường là confirmed reuse R011; chuyển G11/G15 trước đó chưa tách thành physical issue riêng |
| P331 | Best G15 f139–142; G11 f143–154; CLEAR G15 f142, G11 f150–152 | Association conflict FACT; physical identity merge UNCERTAIN do xe liền kề/box amodal chồng nhau |

Trace đủ từng frame/IoU có trong `association_by_frame.csv` và `kitti_semantics/adjusted_clear_matches.csv`. Pred→nhiều GT không tương đương GT→pred IDSW; raw IDSW11 và adjusted10 không thể tóm tắt tất cả các hướng conflict. Không sửa evaluator. So với P54/0001: conflict dạng assignment lặp lại, nhưng P54 bị ignore trong evaluable Car set; chưa thể nói physical merge được xác nhận trên cả hai sequence.

## Candidate review scope

12/154 flagged anchor frames = **7.79%**. Dùng toàn khoảng previous→current cho gap và context ±2 như vòng1: hợp **[22,40], [101,107], [110,124], [127,154]**, 4 đoạn, **69/154 = 44.81%** frame. Potential review reduction = **55.19%**, không phải thời gian tiết kiệm; người review có thể cần context dài hơn và phải kiểm thêm missed issues. Không khuyến nghị bỏ qua toàn bộ frame không flag.

## Tái lập phần evaluation, không inference/download

Từ project root, các lệnh dưới dùng prediction/GT đã lưu. Converter được giữ nguyên; không cần chạy lại converter vì file đã tồn tại.

```powershell
Set-Location 'D:\LCOM108_NMLT\code\100_bai_code\tep_chua_python\semi_auto_video_tracking'
.venv\Scripts\python.exe -X utf8 tools/validate_external_sequence.py --sequence 0000
.venv\Scripts\python.exe -X utf8 tools/evaluate_tracking.py --pred outputs/external_validation/kitti_0000/tracks.txt --gt data/external_validation/kitti_0000/gt/gt.txt --seqinfo data/external_validation/kitti_0000/clip/seqinfo.ini --mode model --no-gate --output outputs/external_validation/kitti_0000/recheck/evaluation.json
.venv\Scripts\python.exe -X utf8 tools/evaluate_kitti_semantics.py --labels data/external_validation/kitti_0000/source/training/label_02/0000.txt --pred outputs/external_validation/kitti_0000/tracks.txt --raw-evaluation outputs/external_validation/kitti_0000/evaluation.json --out-dir outputs/external_validation/kitti_0000/recheck/kitti_semantics
.venv\Scripts\python.exe -X utf8 -m unittest discover -s tests -v
```

`adjudications.json` là quyết định có evidence, không sinh verdict tự động từ metric. Rerun helper tái lập derived CSV/images, không ghi raw MOT/flags. `final_tests.log`: 25 tests, OK, exit0. Lần thử sandbox bị quyền ghi Windows Temp; chạy suite ở môi trường thường đã pass. Một lỗi cú pháp trong helper context mới đã được sửa trước lần suite cuối; không bỏ test nào. FFmpeg “moov atom not found” thuộc test video không hợp lệ có chủ đích.

File/tooling mới của external #2: fetch_kitti_sequence, run_external_blind, validate_external_sequence; tests acquisition/adjudication; ba docs external02/comparison và kế hoạch v2; dataset/artifacts riêng0000. Continuation chỉ hoàn thiện helper adjudication/integrity, tests, verdict/evidence/docs. README thay đổi có sẵn trước continuation được giữ nguyên. Không sửa lab gốc hoặc protected core, không commit/push.

## Giới hạn và quyết định

Hai external sequences tổng185 frame, một source domain, #2 chỉ154 frame và ít Car identities hơn0001; chưa là benchmark. JPEG conversion, classless MOT/Van mismatch, amodal reference, occlusion, camera motion và policy rematching ảnh hưởng kết luận. Visual review tập trung mọi candidate/event và context, không phải người annotator gán nhãn độc lập toàn bộ video. Không có human timing hoặc semantic GT access log được bên thứ ba chứng thực.

**ANALYZER_V2_READY = YES — chỉ cho thiết kế hạn chế**: duplicate trên cùng vehicle lặp ở0001 và0000, với reference-free pairwise signals có sẵn; gap/reappearance redundancy cũng lặp. Xem [ANALYZER_V2_PLAN.md](ANALYZER_V2_PLAN.md). Không đủ cơ sở tune thresholds, tạo rule phát hiện đối tượng hoàn toàn chưa có prediction bằng MOT alone, hoặc khẳng định runtime identity-merge detector đã được biện minh. Chưa implement v2.
