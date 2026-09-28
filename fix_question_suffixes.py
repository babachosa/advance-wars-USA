"""Repair handwritten d-for-question-mark typos found by English comparison."""

from __future__ import annotations

import csv
import hashlib
import re
from pathlib import Path

import aw_vi_tool
from build_full_accent_rom import encode_text, rows_from

BASE = Path(__file__).resolve().parent
SOURCE_ROM = BASE / "Advance Wars (Vietnamese) Context Review 2.gba"
SOURCE_SHA1 = "ade27e842eb4556e9a3fc5b703a46a2a43702bc2"
SOURCE_CSV = BASE / "advance_wars_vi_context_review_2.csv"
OUTPUT_ROM = BASE / "Advance Wars (Vietnamese) Context Review 3.gba"
OUTPUT_CSV = BASE / "advance_wars_vi_context_review_3.csv"
FIXES = {
    "chud": "chứ?", "khôngd": "không?", "saod": "sao?",
    "khuyend": "khuyên?", "Gid": "Gì?", "thuậtd": "thuật?",
    "tad": "ta?", "ngàyd": "ngày?", "thuad": "thua?",
    "had": "hả?", "gìđ": "gì?",
    "khôngđ": "không?", "saođ": "sao?",
}
PATTERN = re.compile(r"(?<!\w)(?:" + "|".join(map(re.escape, FIXES)) + r")(?!\w)")


def main() -> None:
    raw = SOURCE_ROM.read_bytes()
    if len(raw) != 0x400000 or hashlib.sha1(raw).hexdigest() != SOURCE_SHA1:
        raise ValueError("Source ROM changed")
    rows = rows_from(SOURCE_CSV)
    out = bytearray(raw)
    changed = []
    for row in rows:
        before_text = row["vietnamese"]
        after_text = PATTERN.sub(lambda m: FIXES[m.group()], before_text)
        if before_text == after_text:
            continue
        # Every audited d-suffix occurs in a question in the original English.
        if "?" not in row["english"]:
            raise ValueError(f"No English question at {row['offset']}")
        before = encode_text(before_text)
        after = encode_text(after_text)
        if len(before) != len(after) or aw_vi_tool.control_order(before) != aw_vi_tool.control_order(after):
            raise ValueError(f"Size/control changed at {row['offset']}")
        offset = int(row["offset"], 16)
        if raw[offset:offset + len(before)] != before:
            raise ValueError(f"Source mismatch at {row['offset']}")
        out[offset:offset + len(after)] = after
        row["vietnamese"] = after_text
        changed.append(row["offset"])
    with OUTPUT_CSV.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=aw_vi_tool.CSV_FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    OUTPUT_ROM.write_bytes(out)
    print(f"PASS: {len(changed)} question typo rows fixed: {changed}")
    print(f"SHA-1 {hashlib.sha1(out).hexdigest()}")


if __name__ == "__main__":
    main()
