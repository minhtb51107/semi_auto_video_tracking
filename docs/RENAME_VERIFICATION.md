# Semi-Auto Video Tracking — kiểm chứng đổi tên

Đường dẫn hiện tại: `D:/LCOM108_NMLT/code/100_bai_code/tep_chua_python/semi_auto_video_tracking`.

Đã đổi tên thư mục project, giữ nguyên tên các tài liệu lịch sử MVP_AUDIT.md, MVP_PLAN.md, MVP_RESULTS.md. Đã kiểm lại tất cả 673 đường dẫn trong inventory trước đổi tên và 346 file của copy manifest: không thiếu file nào.

25 file văn bản có tên đường dẫn tạm đã được chuẩn hóa, gồm README, tài liệu separation, metadata/log kết quả cũ, settings và script activate/pyvenv.cfg. Để không làm mất provenance, nguyên bản trước sửa được lưu tại [original_path_records.zip](../evidence/rename/original_path_records.zip), kèm [path_updates.json](../evidence/rename/path_updates.json) ghi hash trước/sau. Metadata cũ đã chuẩn hóa đường dẫn không được coi là run mới; bản gốc trong ZIP là evidence nguyên thủy.

README hiển thị **Semi-Auto Video Tracking**. Không đổi logic analyzer, tracker, evaluator hoặc config. Venv launcher/activation được tạo lại theo vị trí mới; pip launcher được cài lại từ wheel ensurepip có sẵn, không tải dependency hay model mới. `pip.exe --version` trỏ đúng venv mới.

Gate trước Validation Phase đã PASS:

```powershell
.venv\Scripts\python.exe -X utf8 tools/reproduce_mvp.py --run-id renamed_verified
```

- Tests: 10/10, 1.996 s, không skip; [tests.log](../outputs/runs/renamed_verified/tests.log).
- 14 lệnh subprocess exit 0: pip check + tests + decode/tracker/review/validator/evaluator/visualizer cho hai clip.
- Clip 01: 622 box / 12 track / 27 flags / 20 frame.
- Clip 02: 226 box / 7 track / 2 flags / 2 frame.
- SHA-256 hai MOT khớp lần trước đổi tên; package imports và interpreter trỏ vào project mới. [acceptance.json](../outputs/runs/renamed_verified/acceptance.json).

Chỉ bắt đầu đối chiếu validation sau gate này. Repo lab gốc không bị sửa, không commit/push. Những lần chạy tiếp theo bỏ `--run-id` để tự tạo output mới, không ghi đè evidence.
