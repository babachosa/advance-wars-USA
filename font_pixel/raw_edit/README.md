# Sửa font pixel bằng Paint

- Mở **font_raw.png** trong Paint và phóng to (ví dụ 800%–1600%). Đây là ảnh raw 128×192 pixel: mỗi ô 8×16 pixel là một chữ, không có lề hoặc nhãn trong ảnh.
- Xem **font_guide.png** để biết vị trí chữ và mã hex. Ảnh guide chỉ dùng để tham khảo, **không** đưa vào ROM.
- Dùng công cụ Bút chì với màu **đen #000000** và **trắng #FFFFFF**; giữ nguyên kích thước ảnh và lưu lại dưới dạng PNG. Mỗi chữ phải nằm trong chiều rộng ban đầu; vị trí và chiều rộng ghi trong **font_map.json**.
- Khi sửa xong, báo lại để mình chạy bước nhập ảnh và kiểm tra ROM. Tool sẽ tạo `Advance Wars (Vietnamese) Pixel Font Edited.gba`; ROM Pixel Font hiện tại không bị ghi đè.

Các lệnh của tool (chạy từ thư mục gốc dự án):

```powershell
python font_pixel\png_rom_tool.py export
python font_pixel\png_rom_tool.py check
python font_pixel\png_rom_tool.py import
```

Không chạy `export` sau khi đã sửa ảnh vì lệnh đó tạo lại ảnh từ ROM gốc. `check` chỉ xác nhận ảnh hợp lệ và liệt kê chữ đã sửa. `import` mã hóa ảnh vào ROM mới, cập nhật cả bảng bitmap lưu trong ROM, và kiểm tra lại từng glyph đã đổi.
