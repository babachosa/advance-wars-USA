Advance Wars (USA).tbl
======================
ROM: Advance Wars (USA).gba
SHA-1: D0A0A4CFE9B95AC7118F7EF476F014CA0242EB65

Bảng TBL bao phủ đủ 256 giá trị byte (00–FF).
20–7E: ký tự ASCII. Các ký tự Latin-1 có dấu được đối chiếu với dãy ký tự
trong ROM tại khoảng 0x2F0DA9.

00: kết thúc chuỗi hoặc byte đệm, tùy vị trí.
0D: xuống dòng trong hội thoại.
0F: tách đoạn/chuyển trang hội thoại (suy ra từ ngữ cảnh).
15: tên người chơi (suy ra từ ngữ cảnh).
80: trở về định dạng chữ thường.
82: bắt đầu nhấn mạnh tên đơn vị.
83: bắt đầu nhấn mạnh lệnh menu.

Các mục [$XX] giữ nguyên byte thô vì chưa xác định được ý nghĩa. Chúng không
phải ký tự có thể dùng tùy ý. Bảng .tbl chỉ giúp đọc/sửa chuỗi trong hex
editor; nó không xử lý con trỏ, độ dài chuỗi, font hay dữ liệu nén.

File .tbl dùng UTF-8. Nếu hex editor cũ không hiển thị đúng chữ có dấu, hãy
chuyển .tbl sang mã ANSI/Windows-1252 trước khi nạp.
