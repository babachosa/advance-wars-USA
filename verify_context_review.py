"""Verify the context-review ROM against every translated CSV entry."""

from __future__ import annotations

import hashlib
import struct
from pathlib import Path

import aw_vi_tool
from build_full_accent_rom import encode_text, rows_from

BASE = Path(__file__).resolve().parent
ROM = BASE / "Advance Wars (Vietnamese) Context Review 4.gba"
CSV = BASE / "advance_wars_vi_context_review_4.csv"
RELOCATED = {"0818A4": 0x02818C, "08289C": 0x2EA1C4}


def main() -> None:
    rom = ROM.read_bytes()
    if len(rom) != 0x400000:
        raise ValueError("ROM size changed")
    rows = rows_from(CSV)
    checked = 0
    for row in rows:
        value = row["vietnamese"]
        if not value:
            continue
        payload = encode_text(value)
        offset_text = row["offset"]
        if offset_text in RELOCATED:
            pointer = struct.unpack_from("<I", rom, RELOCATED[offset_text])[0]
            pos = pointer - 0x08000000
            if not 0x3FAE40 <= pos < 0x3FAE80:
                raise ValueError(f"Relocated pointer outside bank at {offset_text}")
            if rom[pos:pos + len(payload) + 1] != payload + b"\0":
                raise ValueError(f"Relocated text mismatch at {offset_text}")
        else:
            pos = int(offset_text, 16)
            if rom[pos:pos + len(payload)] != payload:
                raise ValueError(f"Text mismatch at {offset_text}")
            if len(payload) > int(row["max_bytes"]):
                raise ValueError(f"Text exceeds slot at {offset_text}")
        checked += 1
    if rom[:0xC0] != (BASE / "Advance Wars (USA).gba").read_bytes()[:0xC0]:
        raise ValueError("GBA header changed")
    print(f"PASS: {checked} translated text entries match ROM; "
          f"SHA-1 {hashlib.sha1(rom).hexdigest()}")


if __name__ == "__main__":
    main()
