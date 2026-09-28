"""Apply reviewed meaning fixes within the verified text slots."""

from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path

import aw_vi_tool
from build_full_accent_rom import encode_text, rows_from

BASE = Path(__file__).resolve().parent
SOURCE_ROM = BASE / "Advance Wars (Vietnamese) Final.gba"
SOURCE_SHA1 = "aed935a5c22b32e7931bd8ff93bf55739a17d84f"
SOURCE_CSV = BASE / "advance_wars_vi_accented.csv"
CORRECTIONS = BASE / "context_corrections.json"
OUTPUT_CSV = BASE / "advance_wars_vi_context_review.csv"
OUTPUT_ROM = BASE / "Advance Wars (Vietnamese) Context Review 1.gba"


def main() -> None:
    raw = SOURCE_ROM.read_bytes()
    if len(raw) != 0x400000 or hashlib.sha1(raw).hexdigest() != SOURCE_SHA1:
        raise ValueError("Reviewed source ROM changed")
    rows = rows_from(SOURCE_CSV)
    changes: dict[str, str] = json.loads(CORRECTIONS.read_text(encoding="utf-8"))
    if not set(changes) <= {row["offset"] for row in rows}:
        raise ValueError("Unknown correction offset")
    out = bytearray(raw)
    intervals = []
    for row in rows:
        offset_text = row["offset"]
        if offset_text not in changes:
            continue
        target = changes[offset_text]
        before = encode_text(row["vietnamese"])
        after = encode_text(target)
        offset = int(offset_text, 16)
        capacity = int(row["max_bytes"])
        if len(after) > capacity:
            raise ValueError(f"Correction exceeds slot at {offset_text}: {len(after)} > {capacity}")
        if aw_vi_tool.control_order(before) != aw_vi_tool.control_order(after):
            raise ValueError(f"Control byte order changed at {offset_text}")
        if aw_vi_tool.PRINTF_RE.findall(before) != aw_vi_tool.PRINTF_RE.findall(after):
            raise ValueError(f"Format placeholder changed at {offset_text}")
        if raw[offset:offset + len(before)] != before:
            raise ValueError(f"Source text mismatch at {offset_text}")
        tail = raw[offset + len(before):offset + capacity]
        if any(tail):
            raise ValueError(f"Nonzero tail; cannot safely expand at {offset_text}")
        if offset + capacity < len(raw) and raw[offset + capacity] != 0:
            raise ValueError(f"No terminator after slot at {offset_text}")
        intervals.append((offset, offset + capacity))
        out[offset:offset + capacity] = after + bytes(capacity - len(after))
        row["vietnamese"] = target
    for (_, end), (start, _) in zip(sorted(intervals), sorted(intervals)[1:]):
        if end > start:
            raise ValueError("Corrections overlap")
    if out[:0xC0] != raw[:0xC0] or len(out) != len(raw):
        raise ValueError("ROM header or size changed")
    with OUTPUT_CSV.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=aw_vi_tool.CSV_FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    OUTPUT_ROM.write_bytes(out)
    print(f"PASS: {len(changes)} context corrections, SHA-1 {hashlib.sha1(out).hexdigest()}")


if __name__ == "__main__":
    main()
