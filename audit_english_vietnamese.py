"""Re-dump English and prepare a reproducible line-by-line context audit."""

from __future__ import annotations

import csv
import hashlib
import re
from pathlib import Path

import aw_vi_tool

BASE = Path(__file__).resolve().parent
ENGLISH_DUMP = BASE / "english_redump_audit.csv"
SOURCE_CSV = BASE / "advance_wars_en_vi.csv"
ACCENTED_CSV = BASE / "advance_wars_vi_accented.csv"
FINAL_ROM = BASE / "Advance Wars (Vietnamese) Final.gba"
COMPARISON = BASE / "english_vietnamese_context_audit.csv"

# These were checked against the complete English and Vietnamese entries.
# This is an evidence list, not an exhaustive language review.
CONFIRMED_ERRORS = {
    "0818A4": "SNOW rendered as TUYT; E is missing from TUYET.",
    "08289C": "BLIZZARD rendered as BAO TUYT; E is missing from TUYET.",
    "291C38": "nhed is an invalid Vietnamese word; English says please.",
    "291D34": "regain HP became hoi HP; nhed is also invalid.",
    "291DF4": "nhed is an invalid Vietnamese word; English says please.",
    "291F68": "nhed is an invalid Vietnamese word; English says please.",
    "2920D0": "dayd and nhed are invalid; English asks questions.",
    "29678C": "nhed is an invalid Vietnamese word; English says please.",
    "29B6D8": "remain dark became 'no toi den', which has the wrong meaning.",
    "2C4A94": "glad to see you became the ungrammatical 'May qua chi da den'.",
    "2C62B4": "There's no way Andy would... became 'Andy khong doi nao...'.",
    "2E86C4": "It's up to you became 'Tuy ban do'.",
    "2FA748": "Several clauses in Sami's introduction have the wrong words or meaning.",
}


def read_rows(path: Path) -> dict[str, dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as file:
        rows = list(csv.DictReader(file))
    result = {row["offset"]: row for row in rows}
    if len(result) != len(rows):
        raise ValueError(f"Duplicate offset in {path.name}")
    return result


def main() -> None:
    rom = aw_vi_tool.load_rom(aw_vi_tool.DEFAULT_ROM)
    extracted = {f"{offset:06X}": raw for offset, raw in aw_vi_tool.extract(rom)}
    dump = read_rows(ENGLISH_DUMP)
    source = read_rows(SOURCE_CSV)
    accented = read_rows(ACCENTED_CSV)
    if not (extracted.keys() == dump.keys() == source.keys() == accented.keys()):
        raise ValueError("Offset lists differ")
    for offset, row in dump.items():
        if bytes.fromhex(row["original_hex"]) != extracted[offset]:
            raise ValueError(f"English dump byte mismatch at {offset}")
        if any(row[key] != source[offset][key] for key in
               ("max_bytes", "original_hex", "english")):
            raise ValueError(f"Stored English differs from fresh dump at {offset}")
    # The ROM builder independently verifies every accented text slot against
    # the checked source ROM, including control bytes and byte counts.
    import build_full_accent_rom
    expected, _, _ = build_full_accent_rom.build_image(
        build_full_accent_rom.SOURCE.read_bytes())
    if FINAL_ROM.read_bytes() != expected:
        raise ValueError("Final ROM and accented CSV differ")
    with COMPARISON.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.writer(file)
        writer.writerow(("offset", "english", "vietnamese_accented",
                         "audit_status", "finding"))
        for offset in sorted(dump):
            english = dump[offset]["english"]
            vietnamese = accented[offset]["vietnamese"]
            finding = CONFIRMED_ERRORS.get(offset, "")
            if finding:
                status = "CONFIRMED_ERROR"
            elif not vietnamese:
                status = "UNTRANSLATED_OR_INTERNAL"
            elif vietnamese == english:
                status = "UNCHANGED_ENGLISH_OR_NAME"
            else:
                status = "NOT_SEMANTICALLY_VERIFIED"
            writer.writerow((offset, english, vietnamese, status, finding))
    print(f"PASS: {len(dump)} English entries exactly match original ROM and stored CSV")
    print(f"PASS: final ROM exactly matches accented CSV; SHA-1 {hashlib.sha1(expected).hexdigest()}")
    print(f"CONFIRMED_ERROR: {len(CONFIRMED_ERRORS)} entries; semantic 100% claim FAILED")
    print(COMPARISON)


if __name__ == "__main__":
    main()
