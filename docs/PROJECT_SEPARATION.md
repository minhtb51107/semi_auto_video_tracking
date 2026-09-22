# Tách đề tài 2 khỏi Day03 lab — kết quả thực hiện

Project mới: `D:/LCOM108_NMLT/code/100_bai_code/tep_chua_python/semi_auto_video_tracking`.
Đã tạo đúng thư mục con trực tiếp của `tep_chua_python` theo đường dẫn người dùng yêu cầu.

## Repo nguồn giữ nguyên

Đã lập hash snapshot trước copy và đối chiếu sau khi chạy project mới: **645 file của project nguồn giữ nguyên**, không có file thêm/xóa/đổi nội dung. Phạm vi gồm source/data/docs/outputs/evidence/cache trong project; không bao gồm nội bộ `.git` và dependency `.venv`. Không commit/push, không copy `.git` sang project mới.

Evidence:

- [copy_manifest.json](../evidence/separation/copy_manifest.json): 346 file đã copy và SHA-256 từng file, tổng 31,948,816 byte (chưa tính dependency).
- [source_snapshot_before.json](../evidence/separation/source_snapshot_before.json): snapshot trước thao tác.
- [source_verification.json](../evidence/separation/source_verification.json): đối chiếu cuối, `original_project_unchanged=true`, `changed=[]`, `added=[]`.

## Chọn file và thay đổi ở bản mới

Giữ nguyên năm module lab thực sự reuse: motlib, run_tracker, check_mot_labels, evaluate_tracking, visualize_tracks. Hai module MVP review_tracks/video_to_clip cũng giữ nguyên. Hash cả bảy module bằng nguồn.

Giữ hai annotation, hai reference, JPEG/seqinfo gốc, hai MP4 preview, weights, guideline/schema/third-party notices, snapshot pre-gold, audit/plan/results MVP và các output MOT/metrics/flags/log/ảnh review quan trọng. BoT-SORT output cũ chỉ được giữ làm evidence lịch sử, không chạy hay phụ thuộc ReID trong project mới.

Không copy Git history, notebook, VS Code config, CVAT XML, HTML/CSS/JS/screenshot hướng dẫn lab, lock_pre_gold script, config ReID không dùng; không copy JPEG giải mã của run MVP cũ vì có thể tái tạo từ MP4. Không xóa bất kỳ mục nào trong repo nguồn.

Thay đổi chỉ trong project mới:

- README mới giải thích nguồn gốc, reuse/phần mới, setup và chạy từ đầu.
- requirements-lock.txt ghi phiên bản package thực tế; .gitignore mới chỉ ignore environment/cache/weights/reference và media phát sinh, giữ khả năng lưu evidence nhỏ.
- tools/reproduce_mvp.py là runner tái lập tuần tự, kiểm dependency origins và lưu log/exit/hash.
- tests/test_review_tracks.py đổi nơi ghi mutation sang `outputs/standalone_mutations`, giữ nguyên test assertions và evidence cũ tại outputs/mvp_mutations.
- Tài liệu separation/inventory và manifest bằng chứng mới.

## Chứng minh chạy từ project mới

Lệnh đã chạy, cwd là root mới:

```powershell
.venv\Scripts\python.exe -X utf8 tools/reproduce_mvp.py --run-id standalone_verified
```

Lệnh tái chạy: bỏ `--run-id` để runner tạo thư mục mới theo thời gian. Không ghi đè run đã có.

Evidence: [acceptance.json](../outputs/runs/standalone_verified/acceptance.json), [tests.log](../outputs/runs/standalone_verified/tests.log), [pip_check.log](../outputs/runs/standalone_verified/pip_check.log). **14 lệnh subprocess exit 0**: pip check, unittest, sáu bước mỗi clip (decode, tracker, review, validate, evaluate, visualize).

| Kiểm tra | Kết quả |
|---|---|
| Dependency consistency | No broken requirements found |
| Toàn bộ unittest | 10/10 pass, 2.146 giây; gồm 10 mutation subcase trên hai annotation |
| Clip 01 | 190 frame → 622 box / 12 track → 27 flags tại 20 frame |
| Clip 02 | 60 frame → 226 box / 7 track → 2 flags tại 2 frame |
| MOT clip 01 SHA-256 | 29354e2b3d906ab88018bcfb1aa6dce94902da285b0e14412cbe33426cd8abb2 |
| MOT clip 02 SHA-256 | 07c4066df77620bec6a53068f29ff636f33935fa15c12178ff462deea898e535 |
| Đối chiếu MOT | Cả hai khớp byte-for-byte output MVP trước khi tách |
| Annotation/reference/snapshot mới | Hash năm gt.txt giữ nguyên sau test/pipeline |

Interpreter, sys.prefix và các package torch/ultralytics/cv2/numpy/lap/PIL trỏ vào `.venv` mới. Môi trường tạo mới, không dùng activation/script launcher của venv cũ, không junction/symlink. Package được copy thành file thực để dùng offline; không tải lại dependencies. Runner xóa PYTHONPATH/PYTHONHOME khỏi child env, tắt user-site và kiểm package origins. Code/tools/tests/config, requirements-lock và pyvenv.cfg không chứa tên đường dẫn repo lab cũ. Python nền/stdlib vẫn là bản Python đã cài trên máy, không phải thành phần repo lab.

Các đường dẫn repo cũ trong `docs/MVP_AUDIT.md` và metadata **lịch sử** tại outputs/evidence được giữ nguyên để không viết lại provenance. Chúng không được dùng làm input path khi chạy lại. Runner dùng input local và thư mục run mới, không sửa đường dẫn lịch sử để giả làm kết quả mới.

Lần đầu chạy venv/Temp trong sandbox bị lỗi quyền ghi (kể cả khi Temp nằm trong project). Đã hoàn thiện venv và chạy lại toàn bộ runner ngoài sandbox, không skip hoặc nới assertion. Log lần lỗi được giữ tại `outputs/runs/standalone_20260922/`. Đã dọn thư mục Temp còn sót, cache Python source và settings Ultralytics fallback ở root mới; giữ settings cần dùng ở `.runtime/ultralytics/`. Dòng `moov atom not found` trong tests.log là negative test MP4 cố ý hỏng.

## Phạm vi nghiệm thu

Đã tách và tái lập thành công trên máy hiện tại; không phụ thuộc đường dẫn repo lab để chạy. Việc cài sạch qua package index trên máy khác chưa được thử; README ghi riêng lệnh tạo venv/install lock và điều kiện Python/wheel. Không khẳng định đã đo tiết kiệm thời gian review hoặc accuracy của heuristic. Giới hạn MVP trước (bao gồm missed ID switch frame 94) vẫn giữ nguyên.

Danh sách file project bàn giao: [FILE_INVENTORY.md](FILE_INVENTORY.md). Environment/cache được mô tả theo nhóm; source, input và evidence được liệt kê từng file. Các thư mục img1 trong run mới là output vừa tạo để tiện review, còn img1 của run cũ không được copy.
