"""Validate reviewed text and identify ROM relocation needs before final build."""

from __future__ import annotations

import csv
import struct
from collections import Counter
from pathlib import Path

import aw_vi_tool
from build_full_accent_rom import encode_text, rows_from
from full_review_ledger import LEDGER, SOURCE, read_ledger
from verify_context_review import RELOCATED

BASE = Path(__file__).resolve().parent
ROM = BASE / "Advance Wars (Vietnamese) Context Review 4.gba"


def main() -> None:
    rows = read_ledger()
    source = {row["offset"]: row for row in rows_from(SOURCE)}
    rom = ROM.read_bytes()
    problems = []
    overflows = []
    for row in rows:
        if row["status"] not in {"approved", "revised"}:
            continue
        original = source[row["offset"]]
        try:
            before = encode_text(original["vietnamese"])
            after = encode_text(row["vietnamese"])
        except Exception as error:
            problems.append((row["offset"], str(error)))
            continue
        if aw_vi_tool.control_order(before) != aw_vi_tool.control_order(after):
            problems.append((row["offset"], "control byte sequence changed"))
        if aw_vi_tool.PRINTF_RE.findall(before) != aw_vi_tool.PRINTF_RE.findall(after):
            problems.append((row["offset"], "format placeholder changed"))
        capacity = int(original["max_bytes"])
        if len(after) > capacity:
            if row["offset"] in RELOCATED:
                pointer = struct.unpack_from("<I", rom, RELOCATED[row["offset"]])[0]
                actual = pointer - 0x08000000
                if rom[actual:actual + len(after) + 1] != after + b"\0":
                    problems.append((row["offset"], "existing relocation mismatch"))
                continue
            ptr = struct.pack("<I", 0x08000000 + int(row["offset"], 16))
            references = []
            start = 0
            while True:
                hit = rom.find(ptr, start)
                if hit < 0:
                    break
                references.append(hit)
                start = hit + 1
            if not references:
                problems.append((row["offset"], "overlong text has no known pointer"))
            overflows.append((row["offset"], len(after), capacity, references))
    print(dict(Counter(row["status"] for row in rows)))
    print(f"Overlong reviewed entries requiring relocation: {len(overflows)}")
    print(f"Problems: {len(problems)}")
    for problem in problems[:30]:
        print(*problem)
    if problems:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
