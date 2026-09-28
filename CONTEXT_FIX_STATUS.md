# Tình trạng sửa ngữ cảnh

ROM rà soát mới nhất: `Advance Wars (Vietnamese) Context Review 4.gba`.
SHA-1: `acda57275804f1f536360e4e19e24efe262c08ac`.

- Đã sửa 13 mục sai xác nhận trong `ENGLISH_VIETNAMESE_AUDIT.md`, gồm `nhed`, `TUYT`, “hỏi HP”, câu bãi ngầm và đoạn Sami.
- Đã sửa thêm các dấu hỏi bị viết thành `d`/`đ` và một số cụm sai dấu lặp lại. Tổng cộng **41 mục** khác bản ROM `Final.gba` trước đó.
- Đã đối chiếu tất cả 2.774 mục có nội dung tiếng Việt giữa CSV mới và ROM mới: khớp. ROM vẫn 4 MiB, header và toàn bộ font cũ không đổi. Trong 482 byte khác ROM trước, không byte nào nằm ngoài 41 ô văn bản được sửa, hai con trỏ nhãn và vùng ROM trống mới `0x3FAE40–0x3FAE52`.
- Hai nhãn “TUYẾT:%s” và “BÃO TUYẾT” dài hơn ô cũ được chuyển sang vùng trống và cập nhật đúng một con trỏ cho mỗi nhãn. Các câu còn lại nằm trong ô cũ và giữ nguyên thứ tự byte điều khiển.

**Chưa thể xác nhận toàn bộ 2.829 mục đúng nghĩa 100%.** Khi rà tiếp vẫn thấy những câu chưa có trong 13 lỗi ban đầu, ví dụ tại `296448` còn “Quá muốn rồi!” cho “you're too late!”; tại `298350` còn “đang cố thời!” cho “what we've got”. Bản này là ROM rà soát, không phải bản dịch cuối đã duyệt toàn bộ. Chưa mở giả lập theo yêu cầu.
