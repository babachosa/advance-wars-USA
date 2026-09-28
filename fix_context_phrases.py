"""Apply hand-reviewed phrase fixes to the current context-review ROM."""

from __future__ import annotations

import csv
import hashlib
from pathlib import Path

import aw_vi_tool
from build_full_accent_rom import encode_text, rows_from

BASE = Path(__file__).resolve().parent
SOURCE_ROM = BASE / "Advance Wars (Vietnamese) Context Review 3.gba"
SOURCE_SHA1 = "6f26b8edd9c4cbef43653a4d334ca8419657f0c9"
SOURCE_CSV = BASE / "advance_wars_vi_context_review_3.csv"
OUTPUT_ROM = BASE / "Advance Wars (Vietnamese) Context Review 4.gba"
OUTPUT_CSV = BASE / "advance_wars_vi_context_review_4.csv"
FIXES = {
    "295B04": [("Tội để bạn tự xử lý", "Tôi để bạn tự xử lý")],
    "297A30": [("Tội để bản xử lý", "Tôi để bạn xử lý")],
    "2BCB18": [("Cụ cố gắng lên!", "Cứ cố gắng lên!")],
    "2C1F84": [("Tội được phép", "Tôi được phép")],
    "2C722C": [("Cụ tin ở bốn em!", "Cứ tin ở bọn em!")],
    "2C8470": [("Cụ để ta lo", "Cứ để ta lo")],
    "2C86A8": [("Cụ để ta lo", "Cứ để ta lo")],
    "2C9034": [("Cụ dùng quân của tôi.", "Cứ dùng quân của tôi.")],
    "2F3DC8": [("Cụ cố gắng lên!", "Cứ cố gắng lên!")],
    "2F81AC": [("Cụ thể này ta sẽ", "Cứ đà này ta sẽ")],
}


def main() -> None:
    raw = SOURCE_ROM.read_bytes()
    if len(raw) != 0x400000 or hashlib.sha1(raw).hexdigest() != SOURCE_SHA1:
        raise ValueError("Source ROM changed")
    rows = rows_from(SOURCE_CSV)
    out = bytearray(raw)
    done = []
    for row in rows:
        offset_text = row["offset"]
        if offset_text not in FIXES:
            continue
        before_text = row["vietnamese"]
        after_text = before_text
        for wrong, right in FIXES[offset_text]:
            if after_text.count(wrong) != 1:
                raise ValueError(f"Expected phrase not unique at {offset_text}: {wrong!r}")
            after_text = after_text.replace(wrong, right)
        before = encode_text(before_text)
        after = encode_text(after_text)
        pos = int(offset_text, 16)
        cap = int(row["max_bytes"])
        if len(after) > cap or len(before) > cap:
            raise ValueError(f"Text too long at {offset_text}")
        if aw_vi_tool.control_order(before) != aw_vi_tool.control_order(after):
            raise ValueError(f"Control byte changed at {offset_text}")
        if raw[pos:pos + len(before)] != before or any(raw[pos + len(before):pos + cap]):
            raise ValueError(f"Source slot mismatch at {offset_text}")
        out[pos:pos + cap] = after + bytes(cap - len(after))
        row["vietnamese"] = after_text
        done.append(offset_text)
    with OUTPUT_CSV.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=aw_vi_tool.CSV_FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    OUTPUT_ROM.write_bytes(out)
    print(f"PASS: {len(done)} phrase fixes; SHA-1 {hashlib.sha1(out).hexdigest()}")


if __name__ == "__main__":
    main()
