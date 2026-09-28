# Bank font tiếng Việt cho Advance Wars (USA)

`Advance Wars (Vietnamese) Font Bank.gba` được tạo từ bản `Advance Wars (Vietnamese) Update 2.gba` (SHA-1 `4c4b23e4207c14646cf175cc1ed0f5c5a99ff166`). ROM mới có SHA-1 `714229b64a5d3d2e4d6fb69d11f787421a2756ef`.

Bank bắt đầu tại offset ROM `0x3F8000`, nằm trong vùng `FF` cuối ROM. Dữ liệu có 186 glyph: 52 chữ Latin không dấu và 134 chữ tiếng Việt có dấu. Mỗi glyph là 8×16 pixel, mỗi hàng một byte 1bpp (bit cao là pixel trái). Bảng tra gồm các mã Unicode 32-bit little-endian, tiếp theo là các glyph theo thứ tự mã Unicode. Header 20 byte: `AWVF`, phiên bản 1, chiều rộng 8, chiều cao 16, định dạng 1, số glyph, offset bảng, offset dữ liệu.

Các pixel được vẽ trực tiếp trong `viet_font_bank.py` bằng các hàng `.`/`#` và tọa độ dấu, không lấy từ font hệ thống. Thân chữ có dấu được vẽ theo đúng kích thước và chân chữ gốc của game ở hàng 12; dấu chấm dưới đặt hàng 15. Xem `viet_font_preview.png` để kiểm tra bằng mắt. Đã sửa hướng nét dấu sắc và dấu huyền; `render_viet_font_preview.py` tạo lại ảnh từ chính các hàng pixel này.

Kiểm tra tĩnh:

```powershell
python viet_font_bank.py check
```

Lệnh này xác nhận SHA-1 ROM đầu vào, kích thước 4 MiB, checksum header GBA, đủ 186 glyph, kích thước ô, nét thân của các chữ có dấu khớp từng pixel với chữ gốc của game, không có hai glyph trùng bitmap, vùng trước `0x3F8000` giữ nguyên từng byte, phần đuôi còn lại là `FF`, và không có con trỏ ROM trực tiếp từ vùng trước bank trỏ vào bank.

**Tình trạng tích hợp:** ROM `Font Bank.gba` chỉ chứa dữ liệu độc lập. Bản đã nối bảng font vào game là `Advance Wars (Vietnamese) Font Mapped.gba`; xem `VIET_FONT_MAPPING.md`. Các câu dịch hiện tại vẫn không dấu cho đến khi được mã hóa và chèn bằng bảng mã mới.
