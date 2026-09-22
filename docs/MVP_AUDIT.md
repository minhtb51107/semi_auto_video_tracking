# MVP audit — 2026-09-22, trước khi triển khai

FACT = kiểm tra file/code hoặc chạy thật; INFERENCE = suy luận; UNKNOWN = chưa xác nhận.

## Phạm vi và nguồn

- FACT: audit bản local tại `D:/LCOM108_NMLT/code/100_bai_code/K4-DAY03-TRANBINHMINH-2A202602174`, HEAD `f38406d716e6b7863da072f6338d9ce7eac28ccd`. `git remote -v` trỏ đúng URL người dùng cung cấp. Không khẳng định đồng bộ HEAD mới nhất trên GitHub.
- FACT: trước thay đổi, `git status --short` chỉ có `.vscode/` và `annotations.xml` untracked. Không tìm thấy AGENTS.md trong cây `D:/LCOM108_NMLT/code` bằng rg.
- FACT: đã đọc sáu module Python trong `tools/`, tất cả source cell notebook (0–21), config, tài liệu root/docs/reports/data/annotations, JS hướng dẫn; kiểm tra HTML/CSS, XML và output JSON/MOT. Media và weights là binary, không phải source code: kiểm tra metadata/decode và load model khi chạy. `.git/` và dependency `.venv/` không được coi là source dự án.
- FACT: không có thư mục tests, requirements hay pyproject trong danh sách file dự án trước audit. Notebook cell 3 pin `ultralytics==8.4.145`, `lap==0.5.13`.

## Mười kết luận chính

| # | Loại | Kết luận và bằng chứng |
|---|---|---|
| 1 | FACT | Pipeline hiện tại bắt đầu từ JPEG đã cắt sẵn: `img1/*.jpg` → YOLO.track(persist=True) → boxes có ID → MOT. `tools/run_tracker.py:33–77`. Không có video decoder/extractor trong sáu module hoặc notebook. `data/README.md` mô tả clip đã cắt sẵn. |
| 2 | FACT | Detector mặc định `YOLO('yolo26n.pt')`, local weights tồn tại; classes 2,5,7; conf .25, NMS IoU .7, imgsz 960. `run_tracker.py:29–59,80–103`, notebook cell 8 và `outputs/model_run_config.json`. |
| 3 | FACT | ByteTrack mặc định qua Ultralytics `bytetrack.yaml`; BoT-SORT ReID tùy chọn qua `configs/trackers/botsort-reid.yaml` (with_reid true, model auto, gmc none). Tracker implementation nằm trong dependency, không có tracker tự viết trong repo. |
| 4 | FACT | CLI `run_tracker.py --clip ... --out ...`, notebook cell 8 gọi cùng `track_clip` và `write_mot`; validator `check_mot_labels.py`, evaluator `evaluate_tracking.py`, renderer `visualize_tracks.py`. Notebook cell 18 đã xếp hạng disagreement khi có hai bản nhãn. |
| 5 | FACT | Writer ghi 10 cột `frame,id,x,y,w,h,confidence,-1,-1,-1`, bbox pixel left/top/width/height, frame 1-based theo thứ tự tên JPEG, tọa độ 2 số lẻ, confidence 4 số lẻ. Nhãn annotation/reference thực tế 9 cột. `write_mot`, tất cả gt.txt và output chạy mới. Không có class/appearance/occluded trong Det hoặc model output. |
| 6 | FACT | Đã có `motlib.parse_mot` (dòng 50), Det, by_frame, by_track, iou. Parser đọc >=6 cột, chấp nhận BOM/comment/dấu chấm phẩy, bỏ conf=0 mặc định và conf<min_conf; không giữ cột sau confidence. Parser ép int(float(...)), chưa chặn nonfinite, bbox âm/kích thước 0 hay duplicate; validator kiểm một phần riêng. |
| 7 | FACT | `evaluate_tracking.py:56` diagnose đã có ID switch, fragmented GT, ghost, loose box, missed/partial GT; cần reference. `check_mot_labels.py:105–144` đã có short/static/gap/missing-frame warnings nhưng chỉ in text, gap tối đa 3/track. Không có structured review_flags cho một tracking result độc lập. |
| 8 | FACT | `motlib.hota:203`, `clear_mot:304`, `identity:371`: HOTA, DetA, AssA, LocA (19 alpha .05–.95); MOTA, MOTP, IDSW, FP, FN, GT/PRED_boxes; IDF1, IDTP/FP/FN. Evaluator có gate IDF1 .80/MOTA .75/MOTP .70 và JSON. Đây là implementation repo; tính tương đương hoàn toàn TrackEval chưa được kiểm chứng trong audit này (UNKNOWN). |
| 9 | FACT | Có thể gọi nguyên trạng parser/grouping/IoU, tracker/writer, evaluator/reference diagnostics, visualization với --only-frames. Đã chạy validator, evaluator và ByteTrack CPU thành công. Không cần parser, tracker hoặc metric engine mới. |
| 10 | FACT | Thiếu CLI analyzer một-file → flags CSV/JSON, config thresholds, regression/mutation tests, và bước MP4 → img1 để dùng tracker cũ. Bằng chứng: inventory source và các entrypoint trên. INFERENCE: bổ sung hai CLI nhỏ và tests đủ cho MVP offline; chưa cần web/API/database. |

## Dữ liệu thật và chạy thử

FACT: có năm file tên gt.txt; hai file người dùng trong annotations được dùng làm fixtures chính, không coi tự động là gold:

| File | Rows | Tracks | Frame | Gap nội bộ | SHA-256 |
|---|---:|---:|---|---:|---|
| annotations/clip_01/gt.txt | 638 | 8 | 1–190 | 0 | ab0240b264729513159d883d2eb3405f63f923a37db660c7777f55b601f62dd6 |
| annotations/clip_02/gt.txt | 242 | 7 | 1–60 | 0 | be693ef16ee2d638f6af3a837b466bd4403fc42df83be8d6d6b29db0a5548b11 |
| gold/clip_01/gt.txt | 573 | xem parser | xem seqinfo | chưa đo trong audit | 94a2bd34aa00348b49cd3ec48e85dbfeaf00504b97349e343363d40e4d1f9d79 |
| data/clips/clip_02/gt/gt.txt | 227 | 6 | 1–60 | chưa đo trong audit | 892f036f1acc0a590218b092384748dac18c199f0d19903eb7ad812ab7a51976 |
| evidence/pre-gold/clip_01/gt.txt | 638 | 8 | 1–190 | 0 | bằng annotation clip_01 |

FACT: `annotations.xml` untracked có 8 track/644 box XML (có thể bao gồm outside); không dùng để ghi đè MOT. `reports/REPORT.md` và manifest là evidence lịch sử, không phải lần chạy mới.

FACT: lệnh đã chạy từ root, Python `.venv/Scripts/python.exe -X utf8`:

```powershell
.venv/Scripts/python.exe -X utf8 tools/check_mot_labels.py --clip data/clips/clip_01 --tracks annotations/clip_01/gt.txt
.venv/Scripts/python.exe -X utf8 tools/check_mot_labels.py --clip data/clips/clip_02 --tracks annotations/clip_02/gt.txt
.venv/Scripts/python.exe -X utf8 tools/evaluate_tracking.py --pred annotations/clip_02/gt.txt --gt data/clips/clip_02/gt/gt.txt --seqinfo data/clips/clip_02/seqinfo.ini --output outputs/mvp_audit_eval_clip_02.json
.venv/Scripts/python.exe -X utf8 tools/run_tracker.py --clip data/clips/clip_02 --model yolo26n.pt --tracker bytetrack.yaml --device cpu --out outputs/mvp_audit_bytetrack_clip_02.txt
```

- FACT: validator exit 0 cả hai; clip_01 có 1 static warning; clip_02 có 2 static + 1 short warning. Gap tính trực tiếp bằng by_track là 0 cả hai.
- FACT: evaluator exit 0; clip_02 IDF1 .9680, MOTA .9339, MOTP .8193, FP15/FN0/IDSW0 (`outputs/mvp_audit_eval_clip_02.json`).
- FACT: ByteTrack chạy hết 60 JPEG, exit 0, 228 box/7 track; không dùng output cũ để nhận là chạy mới.
- FACT: import thành công Python 3.14.6, torch 2.14.0+cpu, ultralytics 8.4.145, lap .5.13, cv2 5.0.0; CUDA False.
- FACT: OpenCV mở được `assets/guide/clip-{01,02}-preview.mp4`: lần lượt 190/60 frame, 12.5 fps, 960×540. Chưa khẳng định MP4 decode bằng pixel với JPEG gốc; re-encoding có thể đổi detection (INFERENCE).

## Cổng quyết định

| Điều kiện | Trạng thái | Bằng chứng |
|---|---|---|
| Lấy tracker output ở đâu | FACT, PASS | --out; file mới outputs/mvp_audit_bytetrack_clip_02.txt |
| Format | FACT, PASS | write_mot + output 10 cột |
| Chạy pipeline hiện tại | FACT, PASS | 60 JPEG → YOLO/ByteTrack → MOT đã chạy; MP4 input là chức năng còn thiếu xác định rõ |
| Phần mới cần thêm | FACT về khoảng thiếu; thiết kế là INFERENCE | analyzer/config/tests + adapter MP4 → layout img1 hiện có |
| Không trùng chức năng | FACT, PASS với giới hạn | Reuse parser/IoU/evaluator; gap là khả năng đã có, chỉ bổ sung structured export, không tuyên bố thuật toán mới. Không viết lại reference-based diagnostics. |

Quyết định: đủ thông tin để thiết kế và triển khai MVP offline. Không có UNKNOWN chặn kiến trúc. Chưa nghiệm thu MVP tại thời điểm audit.

UNKNOWN còn lại: precision/recall heuristic trên lỗi thật, thời gian review tiết kiệm, mapping CVAT task/job hiện tại, hoạt động ReID trong phiên mới, tính tương đương tuyệt đối evaluator với TrackEval. Không dùng các giả định này làm điều kiện triển khai.
