# Kế hoạch hoàn tất bản Việt hóa có dấu

Nguồn là `Advance Wars (Vietnamese) Accent Demo 2.gba`, đã có font mới và hai câu thử. CSV có 2.829 ô chữ; 2.774 ô đã dịch tiếng Việt (khoảng 194.456 ký tự, 42.588 từ), 55 ô để nguyên từ bản gốc. ROM hiện khớp CSV ở mọi ô đã dịch trừ đúng hai câu thử.

1. Trích nội dung từng ô đã dịch từ ROM hiện tại. Giữ nguyên tên riêng, tiếng Anh chủ ý, ký hiệu định dạng và byte điều khiển.
2. Khôi phục dấu theo ngữ cảnh, sau đó rà từ ngữ dễ nhầm trong game (đơn vị, địa hình, thao tác, tên CO). Chỉ chấp nhận thay đổi dấu: bỏ dấu ở kết quả phải khớp nguyên văn từng ký tự của câu cũ.
3. Mã hóa từng ký tự có dấu bằng `viet_font_mapping.json`. Kiểm tra mọi ô có cùng số byte, cùng vị trí dấu câu và byte điều khiển; không vượt ranh giới chuỗi hoặc ghi vào ô bên cạnh. Các câu chưa dịch giữ nguyên.
4. Build `Advance Wars (Vietnamese) Final.gba` từ ROM có font đã kiểm tra. Tái tạo và so sánh toàn bộ ROM; chỉ các byte văn bản được duyệt được phép đổi. Kiểm tra lại toàn bộ con trỏ glyph, dữ liệu font, header GBA và SHA-1 đầu ra.

Đây là các cổng kiểm tra trước khi gọi ROM là bản cuối. Kiểm tra tĩnh không thay thế được việc chơi thử, và yêu cầu hiện tại là không mở giả lập.

## Kết quả build (28-09-2026)

- Đã tạo `Advance Wars (Vietnamese) Final.gba` (4 MiB, SHA-1 `aed935a5c22b32e7931bd8ff93bf55739a17d84f`).
- 2.648/2.774 ô có bản dịch đã được thêm dấu; 65 ô dịch khác tiếng Anh giữ nguyên vì là tên riêng, chữ viết tắt hoặc từ vốn không cần dấu; 61 ô trùng nguyên văn tiếng Anh và 55 ô trống giữ nguyên.
- `python build_full_accent_rom.py check` dựng lại toàn bộ ROM và so sánh byte: PASS. Font và mapping kiểm tra riêng: PASS. Không mở giả lập theo yêu cầu.
- Văn bản nguồn không dấu còn một số lỗi chính tả hoặc thiếu chữ (ví dụ `TUYT` thay vì `TUYET`, `nhed` thay vì `nhe`). Vì chỉ thêm dấu và giữ nguyên số byte, các lỗi đó chưa thể sửa thành câu chuẩn trong lượt build này. Kiểm tra tĩnh cũng chưa chứng minh mọi câu hội thoại đều tự nhiên khi chơi.
