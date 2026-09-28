# Rà toàn bộ bản Anh–Việt trước khi đóng ROM cuối

## Phạm vi

- Đối chiếu **từng mục trong 2.829 mục** của bản dump tiếng Anh đã xác minh với câu tiếng Việt có dấu hiện tại. Không lấy việc khớp byte hoặc mô hình thêm dấu làm bằng chứng đúng nghĩa.
- 2.774 mục có nội dung tiếng Việt ban đầu phải được đánh dấu `approved` hoặc `revised` sau khi đọc cả câu Anh và Việt. Trong 55 mục ban đầu để trống, dịch những mục có ích cho người chơi và ghi lý do cụ thể cho những mục phải giữ nguyên.
- Soát cả câu ngắn, nhãn giao diện, tên đơn vị, lệnh, hội thoại và câu dài. Dùng một bảng thuật ngữ nhất quán cho Advance Wars.

## Quy trình

1. **Khóa nguồn:** dump lại ROM USA SHA-1 đã kiểm chứng; kiểm offset, hex, control byte và chuỗi tiếng Anh khớp 2.829/2.829 mục.
2. **Tạo sổ rà soát:** mỗi mục có offset, câu Anh, câu Việt hiện tại, trạng thái và ghi chú. Chia thành các lô có thể kiểm tra và lưu tiến độ; không đánh dấu `approved` bằng suy đoán tự động.
3. **Biên tập theo nghĩa:** đọc từng cặp câu, sửa sai dấu, sai từ, thiếu ý, tên riêng, ngôi xưng và câu quá dài. Câu lặp phải thống nhất. Các mục thiếu chữ trong bản Việt được dịch lại từ câu Anh.
4. **Kiểm ROM:** mã hóa qua font có dấu; kiểm ký tự có glyph, byte điều khiển, `%` placeholder, ranh giới ô, con trỏ và vùng font. Câu dài hơn ô cũ chuyển sang vùng ROM an toàn rồi cập nhật mọi con trỏ tham chiếu đã xác minh.
5. **Đóng bản cuối:** chỉ build khi tất cả 2.829 mục có trạng thái rõ ràng, không còn `pending`, `blocked` hoặc lỗi kiểm tra. Dựng lại byte để so sánh, ghi SHA-1. Không mở giả lập theo yêu cầu.

## Cổng hoàn thành

- `approved + revised + excluded = 2829`; tất cả `excluded` có lý do cụ thể.
- Không còn chuỗi lỗi được phát hiện (`nhed`, `TUYT`, dấu hỏi thành `d/đ`, từ không khớp ngữ cảnh đã biết).
- ROM đầu ra vượt qua kiểm tra tĩnh toàn bộ 4 MiB và không sửa byte ngoài văn bản, con trỏ được duyệt hoặc bank mới.
- Báo cáo trung thực rằng kiểm tra tĩnh không thay thế chơi thử; không tuyên bố “đúng 100% khi chơi” nếu không chạy game.

## Trạng thái hoàn thành

- Dump tiếng Anh đã xác minh 2.829/2.829 mục.
- Sổ rà soát: 1.325 mục giữ nguyên, 1.452 mục sửa theo ngữ cảnh, 52 mục loại trừ có lý do (chuỗi gỡ lỗi nội bộ, tên riêng/thương hiệu cố định).
- ROM cuối `Advance Wars (Vietnamese) Full Context Final.gba` đã build và dựng lại đối chiếu byte thành công; SHA-1 `36b603d4513fcbad3a486e8a22d37f1300c22031`.
- 106 chuỗi dài đã chuyển sang bank trống từ `0x3FAE80` đến `0x3FB8F1`; 136 con trỏ tìm được đã cập nhật. Còn 18.191 byte trống ở cuối ROM.
- Đã kiểm chiều rộng glyph theo từng dòng của 106 chuỗi chuyển bank và mọi mục trong các vùng text chính, dùng bảng font trong ROM và cộng thêm 1 pixel đệm mỗi glyph. Không dòng nào rộng hơn dòng tiếng Anh gốc rộng nhất trong cùng nhóm giao diện. Các chuỗi chuyển bank không chứa tên người chơi hoặc placeholder thay đổi độ dài. Kết quả chi tiết nằm trong `relocated_layout_audit.csv`.
- Kiểm tra tĩnh xác nhận kích thước 4 MiB, header không đổi, byte chỉ thay đổi trong ô văn bản, con trỏ đã duyệt và bank mới. Không mở giả lập theo yêu cầu, vì vậy chưa thể xác nhận trải nghiệm khi chơi thực tế.
- So sánh ROM cuối trực tiếp với ROM USA gốc: xác minh 2.829 ô text và 2.829 byte ranh giới ngay sau ô, 138 con trỏ text, 0 byte thay đổi ngoài vùng được duyệt. Kết quả nằm trong `original_to_final_verification.json`.
