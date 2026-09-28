# Đối chiếu tiếng Anh và bản Việt có dấu

## Kết luận

**Chưa đúng ngữ cảnh 100%.** Đây là kết luận chắc chắn vì đã có ít nhất 13 mục sai được đối chiếu trực tiếp; con số này chưa phải tổng số lỗi trong 2.829 mục.

## Kiểm tra nguồn

- Dump lại 2.829 mục từ `Advance Wars (USA).gba` bằng `aw_vi_tool.py`.
- Tại từng offset, byte gốc, chuỗi tiếng Anh và kích thước ô đều khớp `advance_wars_en_vi.csv` (2.829/2.829). Lỗi `nhed` không phải lỗi dump.
- `Advance Wars (Vietnamese) Final.gba` khớp từng byte với bản dựng từ `advance_wars_vi_accented.csv`. SHA-1: `aed935a5c22b32e7931bd8ff93bf55739a17d84f`.

## Lỗi ngữ cảnh đã xác nhận

| Offset | Tiếng Anh | Tiếng Việt trong ROM cuối | Vấn đề |
|---|---|---|---|
| `291F68` | “Would you move it here, please?” | “Hãy đưa nó đến đây nhed” | `nhed` là lỗi trong bản dịch viết tay; phải diễn đạt “nhé?” hoặc tương đương. |
| `291D34` | “it won't regain any HP” | “quân sẽ không hỏi HP” | `hỏi` sai nghĩa `regain`; còn có `nhed`. |
| `29B6D8` | “They remain dark until you're next to them.” | “Nó tôi đến khi bạn lại gần.” | Nghĩa và ngữ pháp sai. |
| `2C4A94` | “Boy, am I glad to see you!” | “May quá chỉ đã đến!” | Sai từ và ngữ pháp. |
| `2C62B4` | “There's no way Andy would do something like that.” | “Andy không đội nào làm chuyện đó.” | Cụm “không đội nào” sai ngữ cảnh. |
| `2E86C4` | “It's up to you” | “Tuy bản đồ” | Sai nghĩa. |
| `2FA748` | Sami giới thiệu năng lực chỉ huy | Nhiều cụm như “Muốn con hơn không, nhi?”, “Tội giới dùng bộ binh” | Nhiều từ đặt sai dấu và câu sai nghĩa. |
| `0818A4` | `SNOW:%s` | `TUYT:%s` | Thiếu chữ `E` trong từ “TUYẾT”. |

Tệp `english_vietnamese_context_audit.csv` chứa đủ 2.829 cặp câu với trạng thái. `CONFIRMED_ERROR` là lỗi đã kiểm tra trực tiếp; `NOT_SEMANTICALLY_VERIFIED` **không có nghĩa là đã đúng**. Không thể xác nhận chính xác ngữ cảnh 100% chỉ bằng kiểm tra byte hoặc mô hình tự thêm dấu. Phải biên tập và đối chiếu nghĩa từng câu, rồi build và kiểm tra lại bản sửa.

Chạy lại: `python audit_english_vietnamese.py`.
