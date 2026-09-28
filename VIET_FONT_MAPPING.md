# Mapping font tiếng Việt vào Advance Wars

ROM đầu ra: `Advance Wars (Vietnamese) Font Mapped.gba` (SHA-1 `49a3de055872dc015d7ca6dfb0f718b504dba0ed`). Nguồn là `Advance Wars (Vietnamese) Font Bank.gba` (SHA-1 `714229b64a5d3d2e4d6fb69d11f787421a2756ef`).

Game vẽ chữ từ bảng con trỏ 256 phần tử và bảng độ rộng 256 byte. `map_viet_font.py` sao chép hai bảng này sang vùng `FF` tại cuối ROM, nạp 134 glyph có dấu từ bank `AWVF`, chuyển pixel sang định dạng 4bpp của game, rồi điền con trỏ và độ rộng vào các mã byte còn trống. Chỉ bốn literal trỏ tới bảng đang dùng được đổi; bảng gốc và glyph gốc ở chỗ cũ không bị ghi đè. Dữ liệu mapping mới bắt đầu tại `0x3F9000`, sau bank ở `0x3F8000`.

Mỗi ký tự tiếng Việt có dấu có đúng một mã byte trong `viet_font_mapping.json`. Mã `0x84`–`0xFF` và mười mã dấu câu không xuất hiện trong các chuỗi văn bản thông thường của ROM gốc được dùng cho 134 ký tự. Các mã `0x80`–`0x83` vốn là lệnh đổi kiểu chữ của game nên được giữ nguyên. Chữ ASCII còn lại vẫn dùng bảng gốc. Bộ mã hóa có thể thử bằng:

```powershell
python map_viet_font.py encode "Tiếng Việt đủ dấu"
```

Lệnh này chỉ in byte hex để dùng khi chèn văn bản, không sửa ROM. Các câu dịch hiện có vẫn không dấu. Khi thêm bản dịch có dấu, cần tuân thủ độ dài từng ô chuỗi và giữ nguyên các byte điều khiển; script này chưa tự chèn bản dịch.

Kiểm tra bản ROM và mapping:

```powershell
python viet_font_bank.py check
python map_viet_font.py check
```

`check` tái tạo bản vá từ ROM nguồn đã xác nhận SHA-1, so sánh toàn bộ ROM đầu ra, kiểm tra mỗi con trỏ và dữ liệu pixel 134 glyph, xác nhận bốn literal, vùng ghi được phép, cùng việc giữ nguyên header và font gốc. Chưa chạy thử trên giả lập theo yêu cầu; kiểm tra tĩnh không thể xác nhận hoàn toàn cách hiển thị trong mọi màn chơi.
