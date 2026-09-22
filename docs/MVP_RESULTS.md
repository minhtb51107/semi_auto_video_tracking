# Kết quả nghiệm thu MVP offline — 2026-09-22

FACT: đã chạy `MP4 → JPEG → YOLO26n + ByteTrack → MOT → review analyzer → CSV/JSON` trên cả hai video preview trong repo. Bộ test mới pass 10/10. Đạt phạm vi MVP kỹ thuật offline trong [MVP_PLAN.md](MVP_PLAN.md); chưa chứng minh giảm thời gian sửa annotation hoặc độ chính xác cảnh báo trên lỗi thật.

Audit có trước implementation: [MVP_AUDIT.md](MVP_AUDIT.md). Tất cả số liệu dưới đây là lần chạy mới, không chép số từ report cũ. Bằng chứng máy đọc: [mvp_acceptance.json](../outputs/mvp_acceptance.json), mỗi thư mục run có `source.json`, `tracker_run.json`, `tracks.txt`, `evaluation.json`, `review/review_flags.{csv,json}`.

## File reuse / sửa / mới

FACT — reuse nguyên trạng:

- `tools/run_tracker.py:33,69`: `track_clip`, `write_mot`, CLI; detector local `yolo26n.pt` và ByteTrack từ Ultralytics. Không train model.
- `tools/motlib.py:50,95,108`: parser, grouping, IoU; `clear_mot` dùng trong mutation test đổi ID; metrics dùng qua evaluator.
- `tools/evaluate_tracking.py:216`: evaluator với reference, không thay bằng heuristic.
- `tools/check_mot_labels.py:46`: kiểm nhãn và MOT mới.
- `tools/visualize_tracks.py:69`: xuất 6 ảnh frame 13,17,32,39,122,149 vào `outputs/mvp_video_clip_01/vis_review`; đã mở kiểm ảnh frame 39.
- `assets/guide/clip-01-preview.mp4`, `clip-02-preview.mp4`, hai annotation và reference local chỉ đọc.

FACT — không sửa file có sẵn. `.vscode/` và `annotations.xml` là untracked từ trước, không thuộc thay đổi MVP. SHA-256 của cả năm `gt.txt` khớp trước/sau, được assert trong lần kiểm nghiệm thu (`outputs/mvp_acceptance.json`).

FACT — file source/docs mới:

1. `tools/review_tracks.py`: sáu reason, CLI CSV/JSON; validation đầu vào bảo vệ những trường hợp parser cũ ép kiểu quá rộng.
2. `tools/video_to_clip.py`: decode đúng thứ tự, không sampling; output mới, không overwrite; metadata/hash nguồn.
3. `configs/review_thresholds.json`: toàn bộ thresholds có trạng thái `experimental_uncalibrated`.
4. `tests/test_review_tracks.py`, `tests/test_video_to_clip.py`: unit/CLI/fixture/mutation/decode tests.
5. `docs/MVP_AUDIT.md`, `docs/MVP_PLAN.md`, `docs/MVP_RESULTS.md`.

Artifact mới: `outputs/mvp_audit_bytetrack_clip_02.txt`, `outputs/mvp_audit_eval_clip_02.json`, `outputs/mvp_acceptance.json`; các thư mục `outputs/mvp_video_clip_01`, `mvp_video_clip_02`, `mvp_mutations`, `mvp_review_annotation_01`, `mvp_review_annotation_02`, `mvp_review_audit_02`. Thư mục con outputs bị Git ignore theo .gitignore hiện có; chưa commit/push. Muốn chia sẻ kết quả, cần chuyển/gói artifact có chủ đích; không đưa weights/reference vào commit.

## Lệnh tái lập

Chạy từ root repo local. Python sử dụng `.venv/Scripts/python.exe -X utf8` để in tiếng Việt đúng trên Windows. Môi trường đã có đủ dependency, không cài mới: Python 3.14.6, ultralytics 8.4.145, torch runtime 2.14.0+cpu, lap .5.13, OpenCV runtime 5.0.0 (distribution 5.0.0.93). `torch.cuda.is_available()` là False. Notebook cell 3 là nguồn pin Ultralytics/lap.

```powershell
# Tests (tạo/dọn thư mục Temp của Windows và ghi mutation evidence dưới outputs/)
.venv/Scripts/python.exe -X utf8 -m unittest discover -s tests -v

# Pipeline đã chạy. --out của video_to_clip phải là thư mục chưa tồn tại.
# Khi tái chạy decode, dùng một tên mới và đổi --clip/--tracks tương ứng.
.venv/Scripts/python.exe -X utf8 tools/video_to_clip.py --video assets/guide/clip-01-preview.mp4 --out outputs/mvp_video_clip_01
.venv/Scripts/python.exe -X utf8 tools/run_tracker.py --clip outputs/mvp_video_clip_01 --model yolo26n.pt --tracker bytetrack.yaml --device cpu --out outputs/mvp_video_clip_01/tracks.txt
.venv/Scripts/python.exe -X utf8 tools/review_tracks.py --tracks outputs/mvp_video_clip_01/tracks.txt --config configs/review_thresholds.json --out-dir outputs/mvp_video_clip_01/review

.venv/Scripts/python.exe -X utf8 tools/video_to_clip.py --video assets/guide/clip-02-preview.mp4 --out outputs/mvp_video_clip_02
.venv/Scripts/python.exe -X utf8 tools/run_tracker.py --clip outputs/mvp_video_clip_02 --model yolo26n.pt --tracker bytetrack.yaml --device cpu --out outputs/mvp_video_clip_02/tracks.txt
.venv/Scripts/python.exe -X utf8 tools/review_tracks.py --tracks outputs/mvp_video_clip_02/tracks.txt --out-dir outputs/mvp_video_clip_02/review

# Dùng độc lập với bất kỳ output tracker theo format repo
.venv/Scripts/python.exe -X utf8 tools/review_tracks.py --tracks outputs/model_bytetrack_clip_01.txt --out-dir outputs/review_existing

# Validator / evaluator / visualization cũ
.venv/Scripts/python.exe -X utf8 tools/check_mot_labels.py --clip outputs/mvp_video_clip_01 --tracks outputs/mvp_video_clip_01/tracks.txt
.venv/Scripts/python.exe -X utf8 tools/evaluate_tracking.py --pred outputs/mvp_video_clip_01/tracks.txt --gt gold/clip_01/gt.txt --seqinfo outputs/mvp_video_clip_01/seqinfo.ini --mode model --output outputs/mvp_video_clip_01/evaluation.json
.venv/Scripts/python.exe -X utf8 tools/evaluate_tracking.py --pred outputs/mvp_video_clip_02/tracks.txt --gt data/clips/clip_02/gt/gt.txt --seqinfo outputs/mvp_video_clip_02/seqinfo.ini --mode model --output outputs/mvp_video_clip_02/evaluation.json
.venv/Scripts/python.exe -X utf8 tools/visualize_tracks.py --clip outputs/mvp_video_clip_01 --tracks outputs/mvp_video_clip_01/tracks.txt --only-frames 13,17,32,39,122,149 --out outputs/mvp_video_clip_01/vis_review
```

FACT: chạy thực tế tracker qua subprocess để lưu command/exit/stdout/stderr/wall time trong `tracker_run.json`; command CLI ở trên tương đương. Detector giữ nguyên defaults `.25/.7/960/[2,5,7]`, persist True. Hash weights: `9b09cc8bf347f0fc8a5f7657480587f25db09b34bf33b0652110fb03a8ad4fef`.

## Kết quả chạy thật

| FACT | Clip 01 MP4 | Clip 02 MP4 | Evidence |
|---|---:|---:|---|
| Frame giải mã / resolution / FPS | 190 / 960×540 / 12.5 | 60 / 960×540 / 12.5 | source.json |
| Box / track | 622 / 12 | 226 / 7 | tracks.txt, tracker_run.json |
| Validator | 0 lỗi, 14 warnings | 0 lỗi, 4 warnings | CLI check_mot_labels |
| Flag / frame có flag | 27 / 20 | 2 / 2 | review_flags.json |
| Lý do thực tế | 20 track_gap + 7 track_reappeared | 2 track_gap | review_flags.json |
| Tracker wall time CPU | 29.91 s | 15.11 s | tracker_run.json, bao gồm startup/load |
| Parse + analyze một lần | 14.80 ms | 4.53 ms | mvp_acceptance.json; không bao gồm export, không phải benchmark ổn định |

FACT: 20/190 = 10.53% và 2/60 = 3.33% là tỷ lệ frame neo cảnh báo, **không phải** tỷ lệ tiết kiệm thời gian. Reviewer cần xem cả đoạn từ previous_frame_id đến frame_id và ngữ cảnh; các frame không có flag vẫn có thể sai. Có thể có hai reason cùng một event.

FACT: cả hai annotation gốc có 0 gap, nhưng analyzer cho 3 flag hình học tại 3 frame mỗi file (`outputs/mvp_review_annotation_0*/review_flags.json`). Không coi annotation gốc là bộ negative hoàn hảo, không kết luận các cảnh báo đó là false positive khi chưa review.

FACT: detector trên JPEG nguyên bản clip_02 (audit) cho 228 box/7 track, 0 flag, khác MP4 decode 226 box/7 track. Hai nguồn ảnh qua nén khác nhau, không so kết quả như cùng một input bitwise. Thứ tự/frame count/resolution theo preview repo và seqinfo; chưa kiểm nghiệm đồng bộ pixel mọi frame với JPEG gốc.

Evaluator cũ với reference cùng clip (không phải metric của heuristic):

| FACT | HOTA | IDF1 | MOTA | MOTP | FP | FN | IDSW |
|---|---:|---:|---:|---:|---:|---:|---:|
| MP4 clip 01 | .7023 | .8669 | .7277 | .8218 | 102 | 53 | 1 |
| MP4 clip 02 | .7972 | .9227 | .8458 | .8512 | 17 | 18 | 0 |

Evidence: `outputs/mvp_video_clip_0*/evaluation.json`. FACT: clip 01 evaluator báo switch frame 94, GT ID5, pred ID28→33; analyzer không phát possible_fragmentation ở ca này. Đây là ca bỏ sót thực tế, không che giấu bằng việc tune theo reference. INFERENCE: geometry endpoint không đủ bao phủ identity errors.

## Sample flags và cách đọc

FACT: trích từ `outputs/mvp_video_clip_01/review/review_flags.csv`:

```csv
frame_id,track_id,reason,observed_value,threshold,previous_frame_id,related_track_id
17,2,track_gap,3,1,13,
39,12,track_reappeared,6,5,32,
149,44,track_gap,26,1,122,
149,44,track_reappeared,26,5,122,
```

Frame 17/ID2: không có row của ID2 ở frame 14–16, phát hiện tại frame 17. FACT là thiếu row; việc đó do occlusion hợp lệ, detector mất box hay annotation thiếu là UNKNOWN cho đến khi xem ảnh. Frame 39/ID12: xem lại frame 32–39, không tự nối/sửa ID.

| Reason | observed_value / comparator | threshold mặc định |
|---|---|---:|
| track_gap | số frame thiếu >= | 1 |
| track_reappeared | số frame thiếu >= | 5 |
| large_motion_jump | khoảng cách tâm / diagonal box trước > | 1.5 |
| abnormal_size_change | max tỷ lệ width/height hai chiều > | 2.0 |
| low_consecutive_iou | IoU hai frame liền nhau < | .1 |
| possible_fragmentation | IoU endpoint >=; khoảng cách frame trong [1,5] | .3; temporal gate 5 |

Tất cả thresholds đọc từ config và copy vào JSON. Geometry không chạy xuyên gap. `possible_fragmentation` gắn ID mới và `related_track_id` cũ; nhiều ứng viên có thể tồn tại. CSV biểu diễn related_track_id thiếu bằng ô trống, JSON bằng null. CSV threshold cho fragmentation là spatial threshold; temporal gate có trong JSON config và được kiểm cùng lúc.

Parser guard dùng lại `parse_mot`, chấp nhận variant 6/7/9/10 cột của repo, comment/BOM/semicolon. Từ chối frame/ID phân số, frame<1, ID<0, NaN/Inf, thiếu cột, kích thước<=0, duplicate active frame/ID. Vẫn giữ semantics conf=0 ignored và conf<0 bị min_conf=0 lọc như parser cũ. Empty input xuất CSV header và JSON empty_input=true; 0 flags không chứng minh chất lượng. Analyzer không tự kiểm ảnh bounds, dùng validator cũ với seqinfo cho việc đó.

## Tests

FACT: lệnh unittest cuối exit 0, **Ran 10 tests in 1.800s — OK**. Lần đầu có 4 lỗi môi trường do sandbox từ chối Temp; đã chạy lại cùng bộ test ngoài sandbox, không bỏ/skip test để pass. Thông báo OpenCV `moov atom not found` là từ negative test file MP4 cố ý hỏng.

`test_two_real_annotations_and_mutations` kiểm cả 2 fixture và 10 subcase; bằng chứng và bản sao tại [manifest.json](../outputs/mvp_mutations/manifest.json):

| Mutation trên mỗi gt.txt | Điều kiểm |
|---|---|
| Xóa toàn bộ frame giữa | track_gap tại frame kế tiếp, missing=1, threshold=1 |
| Đổi ID từ midpoint | possible_fragmentation với đúng old/new ID; clear_mot cũ xác nhận switch so với bản gốc |
| Dịch box +10000 pixel | large_motion_jump + low_consecutive_iou đúng frame/ID |
| Width/height ×4 | abnormal_size_change đúng frame/ID |
| Xóa 6 frame của một track | track_reappeared missing=6 threshold=5 tại frame trở lại |

Các test còn lại: parse reference khi có; chuyển động đều; renumber toàn track không bị coi switch; entry/exit; không so geometry qua gap; fragmentation không nối track overlap thời gian/xa thời gian/xa không gian; threshold boundary và config sai; shuffled input; parser malformed/ignored/empty; CLI CSV/JSON và exit 2 khi sai; video order/metadata/no-overwrite/bad input. Source hash invariant được kiểm thêm sau pipeline. Mutation là dữ liệu giả lập để thử quy tắc, không phải evidence chất lượng trên lỗi ngoài thực tế.

## Giới hạn và trước khi tích hợp CVAT

- FACT: MVP chỉ xuất review candidates. Không auto-correct, không tạo label ground truth, không thêm possible_id_switch/lost_track/false_continuation. Evaluator đã có reference diagnostics cho các mục gần tương ứng, được reuse riêng.
- INFERENCE: motion/size/IoU có thể báo nhầm khi xe nhanh, perspective hoặc che khuất; fragmentation endpoint có thể nhầm hai xe khác nhau. FACT: đã thấy missed switch frame 94; các swap identity có geometry mượt và object chưa từng được detect có thể không có flag.
- FACT: chưa chạy lại BoT-SORT/ReID; không cần tracker phụ để nghiệm thu ByteTrack path. Không train mới. Chưa xác nhận evaluator hoàn toàn tương đương TrackEval bằng đối chiếu độc lập.
- FACT: thuật toán fragmentation O(T²), các CLI đọc toàn bộ MOT vào RAM; phù hợp clip ngắn đã thử, chưa benchmark video dài. Adapter decode bằng OpenCV theo frame order, không giữ timestamp VFR. Nếu decode lỗi giữa chừng, thư mục ảnh tạm có thể còn nhưng không có metadata thành công; không dùng nó để chạy tracker.
- UNKNOWN: precision/recall trên lỗi thật và thời gian sửa giảm bao nhiêu. Cần người review gắn closure true issue/not-a-defect, đo baseline và assisted time trên dữ liệu giữ riêng, rồi hiệu chỉnh config.
- Trước CVAT cần xác minh phiên bản/task/job thực tế, media hash và frame order, mapping MOT 1-based ↔ CVAT frame, mapping external track ID ↔ CVAT object ID, schema vehicle và quy tắc outside/occluded; các cột này không được giữ trong model MOT. `CVAT_TASK_SPEC.md` và `lab-guide.html` là evidence hướng dẫn cũ, không chứng minh session CVAT hiện tại.
- Cần chọn cơ chế import/review phù hợp phiên bản CVAT, kiểm round-trip trên task thử, hiển thị context trước/sau cảnh báo và lưu closure. CSV/JSON hiện tại không phải format import annotation CVAT. Chưa tạo connector/API/frontend và chưa ghi vào CVAT.
