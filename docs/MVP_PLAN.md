# MVP tối thiểu — lập sau audit, trước implementation

Cơ sở: [MVP_AUDIT.md](MVP_AUDIT.md), cổng quyết định PASS. Chỉ làm CLI offline.

| File | Lý do | Input | Output |
|---|---|---|---|
| tools/review_tracks.py (mới) | Reuse motlib parser/by_track/IoU; xuất structured temporal review độc lập reference | MOT + JSON config | review_flags.csv, review_flags.json + metadata/hash/summary |
| configs/review_thresholds.json (mới) | Ngưỡng thử nghiệm chưa hiệu chỉnh, đơn vị/comparator rõ trong docs | cấu hình do người dùng chọn | thresholds cho analyzer |
| tools/video_to_clip.py (mới) | Pipeline cũ chỉ nhận img1 JPEG; adapter đơn giản, không thay tracker | MP4 local | thư mục mới img1/*.jpg + seqinfo.ini + source metadata/hash; từ chối ghi đè |
| tests/test_review_tracks.py (mới) | Parser/continuity, negative cases, mutation trên cả hai annotation; giữ nguyên source | hai gt.txt + bản sao cố ý sai | unittest result, mutation copies/manifest trong outputs/mvp_mutations |
| tests/test_video_to_clip.py (mới) | Kiểm indexing, metadata, từ chối overwrite/bad video | video nhỏ tạo trong temp | unittest result |
| docs/MVP_AUDIT.md (mới) | Evidence trước code | repo + chạy thử | audit và gate |
| docs/MVP_PLAN.md (mới) | Diff/scope/contract | audit | kế hoạch này |
| docs/MVP_RESULTS.md (mới sau chạy) | Nghiệm thu, lệnh tái lập, limitation/CVAT | logs/results thật | báo cáo |

Không sửa code cũ, notebook, ground truth, bài nộp hay model. Artifact trong thư mục con outputs/ bị ignore theo quy tắc hiện tại; JSON ngay tại outputs/ được phép track. Giữ nguyên .gitignore. Dùng unittest/thư viện chuẩn; adapter dùng OpenCV đã có, test video dùng NumPy đi kèm môi trường tracking.

## Quy tắc dự kiến

Tất cả flag là gợi ý review, không phải kết luận lỗi. frame_id là frame hiện tại (đầu đoạn xuất hiện lại), previous_frame_id ghi ngữ cảnh. Frame 1-based. CSV/JSON cùng danh sách, thứ tự ổn định, có `frame_id,track_id,reason,observed_value,threshold`; thêm related_track_id/previous_frame_id khi cần. JSON lưu config, hash input, số rows/tracks/flagged frames.

- track_gap: missing = current.frame - previous.frame - 1 >= 1. Đây là sự thật về lỗ hổng dữ liệu, nguyên nhân chưa biết. Bao phủ gap warning vốn có của validator ở dạng structured.
- track_reappeared: cùng ID trở lại sau >=5 frame thiếu. Có thể cùng phát track_gap; hai lý do cùng event, không đếm thành hai lỗi thật.
- large_motion_jump: chỉ frame liền nhau; khoảng cách tâm / diagonal box trước >1.5.
- abnormal_size_change: chỉ frame liền nhau; max(w2/w1,w1/w2,h2/h1,h1/h2)>2.0.
- low_consecutive_iou: chỉ frame liền nhau, IoU<0.1 (consecutive chỉ cặp frame kế nhau).
- possible_fragmentation: track A kết thúc trước track B bắt đầu, cách <=5 frame; endpoint IoU>=0.3. Ghi B và related_track_id=A. Không tự merge; không gọi đây là ID switch. Không xét track đang overlap thời gian. Complexity endpoint O(T²) chấp nhận được cho clip ngắn.

Không thêm possible_id_switch/lost_track/false_continuation: reference-based IDSW/ghost/missed đã có trong evaluator, và chỉ geometry không thể xác nhận identity. Thử đổi ID cần gây possible_fragmentation; dùng evaluator cũ với bản gốc làm reference trong mutation test để chứng minh IDSW được tạo.

## Kiểm tra / nghiệm thu

1. Parse cả hai annotation 9 cột và tracker 10 cột, kiểm SHA-256 bất biến; baseline continuity 0 gap. Test thêm reference nếu có.
2. Trên từng file annotation, tạo bản sao: xóa toàn bộ một frame giữa track; đổi ID từ midpoint; dịch một box; đổi size; xóa một đoạn tạo gap. Assert đúng frame/track/reason/observed/threshold, không chỉ assert có flag bất kỳ.
3. Kiểm negative cases (chuyển động đều, entry/exit, global ID renumber, overlap tracks), malformed/duplicate/nonfinite/empty và CLI CSV/JSON.
4. Chạy video preview thật → video_to_clip → run_tracker ByteTrack nguyên trạng → review_tracks; không dùng GT giả làm tracker output, không train. Chạy evaluator cũ riêng nếu có reference cùng sequence; phân biệt preview decode với JPEG gốc.
5. Báo cáo số candidate frames, không gọi tỷ lệ giảm candidate là thời gian tiết kiệm. Chưa đo người review thì thời gian tiết kiệm UNKNOWN.
