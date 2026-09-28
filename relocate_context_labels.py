"""Relocate two corrected labels into verified free space, then repoint them."""

from __future__ import annotations

import csv
import hashlib
import struct
from pathlib import Path

import aw_vi_tool
from build_full_accent_rom import encode_text, rows_from

BASE = Path(__file__).resolve().parent
SOURCE_ROM = BASE / "Advance Wars (Vietnamese) Context Review 1.gba"
SOURCE_SHA1 = "7b5aadaf540428f80f03d6c9eb02d1d7e33b969e"
SOURCE_CSV = BASE / "advance_wars_vi_context_review.csv"
OUTPUT_ROM = BASE / "Advance Wars (Vietnamese) Context Review 2.gba"
OUTPUT_CSV = BASE / "advance_wars_vi_context_review_2.csv"
FREE_START = 0x3FAE40
RELOCATIONS = {
    "0818A4": (0x02818C, "TUYẾT:%s"),
    "08289C": (0x2EA1C4, "BÃO TUYẾT"),
}


def main() -> None:
    raw = SOURCE_ROM.read_bytes()
    if len(raw) != 0x400000 or hashlib.sha1(raw).hexdigest() != SOURCE_SHA1:
        raise ValueError("Source ROM changed")
    rows = rows_from(SOURCE_CSV)
    by_offset = {row["offset"]: row for row in rows}
    out = bytearray(raw)
    cursor = FREE_START
    for offset_text, (pointer_offset, target) in RELOCATIONS.items():
        row = by_offset[offset_text]
        old_address = 0x08000000 + int(offset_text, 16)
        old_pointer = struct.pack("<I", old_address)
        hits = [i for i in range(0, len(raw) - 3) if raw[i:i + 4] == old_pointer]
        if hits != [pointer_offset]:
            raise ValueError(f"Unexpected pointer references for {offset_text}: {hits}")
        old_text = encode_text(row["vietnamese"])
        new_text = encode_text(target)
        if aw_vi_tool.PRINTF_RE.findall(old_text) != aw_vi_tool.PRINTF_RE.findall(new_text):
            raise ValueError(f"Format placeholder changed at {offset_text}")
        if aw_vi_tool.control_order(old_text) != aw_vi_tool.control_order(new_text):
            raise ValueError(f"Control byte changed at {offset_text}")
        if raw[int(offset_text, 16):int(offset_text, 16) + len(old_text)] != old_text:
            raise ValueError(f"Original label mismatch at {offset_text}")
        payload = new_text + b"\0"
        if any(value != 0xFF for value in raw[cursor:cursor + len(payload)]):
            raise ValueError("Relocation destination is not erased ROM")
        out[cursor:cursor + len(payload)] = payload
        struct.pack_into("<I", out, pointer_offset, 0x08000000 + cursor)
        row["vietnamese"] = target
        cursor += len(payload)
    if out[:0xC0] != raw[:0xC0] or len(out) != len(raw):
        raise ValueError("ROM size or header changed")
    with OUTPUT_CSV.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=aw_vi_tool.CSV_FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    OUTPUT_ROM.write_bytes(out)
    print(f"PASS: relocated {len(RELOCATIONS)} labels to {FREE_START:06X}-{cursor:06X}; "
          f"SHA-1 {hashlib.sha1(out).hexdigest()}")


if __name__ == "__main__":
    main()
