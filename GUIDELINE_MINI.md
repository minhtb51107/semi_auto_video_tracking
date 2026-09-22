# Mini annotation guideline — Ngày 3 (tracking)

> Điền file này **trong lúc gán nhãn**, không phải sau khi xong. Mỗi lần bạn dừng
> lại nghĩ "cái này tính sao nhỉ?" thì đó là một dòng phải ghi vào đây.
>
> Đây là tài liệu mà người gán nhãn tiếp theo sẽ đọc để làm giống bạn. Nếu hai
> người trong nhóm gán khác nhau, gần như luôn là vì file này chưa nói rõ — chứ
> không phải vì ai kém.

Nhóm / tên: Tran Binh Minh / cá nhân
Clip: `clip_01`, `clip_02`

---

## 1. Phạm vi: gán cái gì, không gán cái gì

Một lớp duy nhất: **`vehicle`** — xe bốn bánh (xe con, van, xe buýt, xe tải).

| Gán | Không gán |
| --- | --- |
| xe con, SUV, taxi, xe bán tải | người đi bộ |
| van, minivan | xe đạp |
| xe buýt, minibus | **xe máy / mô tô** |
| xe tải, xe đầu kéo | xe trong ảnh quảng cáo, trong gương, dưới bóng nước |

Bổ sung của nhóm (nếu có): không có

## 2. Luật ID — phần quan trọng nhất

| Tình huống | Luật của nhóm | Vì sao |
| --- | --- | --- |
| Xe bị che một phần rồi hiện lại | giữ nguyên ID nếu bị che **dưới 25 frame** (mặc định của lab: 25 frame = 2 giây @ 12.5 fps) | Giữ identity khi vẫn nhận ra quỹ đạo và appearance của xe. |
| Xe bị che lâu hơn ngưỡng trên | xem xét track mới nếu không còn đủ bằng chứng nối identity | Tránh nối nhầm hai xe giống nhau sau thời gian mất dấu dài. |
| Xe rời khung hình rồi quay lại | mặc định: **track mới** | Ra khỏi khung là kết thúc track cũ. |
| Hai xe cắt nhau / chồng lên nhau | giữ ID theo quỹ đạo trước khi cắt; kiểm tra frame trước, trong và sau crossing | Ưu tiên continuity của từng xe, không đổi ID chỉ vì bbox overlap. |

## 3. Luật bbox

| Tình huống | Luật của nhóm |
| --- | --- |
| Xe bị cắt bởi rìa ảnh | bbox chạm đúng rìa, không đoán phần ngoài ảnh |
| Xe bị xe khác che một phần | bbox ôm phần **nhìn thấy được** |
| Xe vừa xuất hiện, còn rất nhỏ / rất mờ | bắt đầu track từ frame đầu tiên xác định được là xe bốn bánh; ngưỡng nhóm chọn: cần nhìn đủ hình dạng xe, không đoán từ một vài pixel |
| Xe đang đỗ, không di chuyển | vẫn gán track nếu là xe bốn bánh nhìn thấy; kiểm tra không nhầm với bbox bị treo |
| Keyframe đặt dày ở đâu | đặt dày khi xe đổi hướng, đổi tốc độ/kích thước, bị che hoặc đi qua vùng crossing; kiểm tra midpoint giữa các keyframe |

## 4. Ít nhất ba ca mơ hồ đã gặp thật

Ghi **frame cụ thể** và **ID cụ thể**, không ghi chung chung.

### Ca 1
- Clip / frame / ID: clip_01 / 55-78 / ID 5
- Tình huống: evaluate cảnh báo track bắt đầu sớm hơn reference.
- Quyết định: kiểm tra lại frame đầu tiên xe thực sự xác định được; không tự sửa file MOT bằng tay.
- Lý do: thời điểm entry phải dựa trên xe nhìn thấy trong ảnh, không dựa riêng vào metric.

### Ca 2
- Clip / frame / ID: clip_01 / 79-100 / ID 6
- Tình huống: track có thể bắt đầu sớm hơn thời điểm xe rõ ràng xuất hiện.
- Quyết định: dùng cùng ngưỡng nhận diện xe bốn bánh như các track khác và kiểm tra frame transition.
- Lý do: guideline cần nói rõ khi xe nhỏ hoặc mờ mới đủ chắc chắn để bắt đầu track.

### Ca 3
- Clip / frame / ID: clip_01 / 82-102 / ID 5/6
- Tình huống: bbox nội suy có thể lệch khỏi phần xe nhìn thấy ở midpoint.
- Quyết định: thêm keyframe quanh vùng lệch nếu kiểm tra hình ảnh xác nhận drift.
- Lý do: hai đầu keyframe đúng không bảo đảm các frame giữa đúng.

## 5. Sửa gì sau khi chấm với gold và sau khi kiểm chéo

Luật nào trong file này hoá ra còn thiếu hoặc còn mơ hồ? Viết lại cho rõ:

- Ghi frame đầu/cuối của các track nhỏ hoặc bị che ngay khi annotate để dễ kiểm tra Outside và entry.
- Sau evaluate, chỉ sửa trong CVAT rồi export lại; không sửa trực tiếp MOT và không dùng gold/model làm nhãn.
