"""Measure rendered-line widths of relocated text with the ROM glyph table."""

from __future__ import annotations

import csv
import json
from pathlib import Path

import aw_vi_tool
from build_full_accent_rom import encode_text, rows_from
from full_review_ledger import LEDGER, SOURCE, read_ledger
from map_viet_font import WIDTH_OFFSET

BASE = Path(__file__).resolve().parent
ROM = BASE / "Advance Wars (Vietnamese) Full Context Final.gba"
REPORT = BASE / "full_context_final_report.json"
OUTPUT = BASE / "relocated_layout_audit.csv"
FIELDS = ("offset", "kind", "english_max_pixels", "vietnamese_max_pixels",
          "english_max_with_spacing", "vietnamese_max_with_spacing",
          "english_longest_line", "vietnamese_longest_line")


def lines(value: str, widths: bytes) -> list[tuple[int, int, str]]:
    encoded = encode_text(value)
    visible = []
    length = spacing = 0
    result = []
    for byte in encoded + b"\x0f":
        if byte in (0x0C, 0x0D, 0x0F):
            result.append((length, spacing, "".join(visible)))
            visible, length, spacing = [], 0, 0
        elif byte == 0x1A:
            visible.append(" ")
            length += widths[0x20]
            spacing += widths[0x20] + 1
        elif byte >= 0x20 and byte not in (0x80, 0x81, 0x82, 0x83):
            visible.append(chr(byte) if byte < 0x80 else "■")
            length += widths[byte]
            spacing += widths[byte] + 1
    return result


def main() -> None:
    data = ROM.read_bytes()
    widths = data[WIDTH_OFFSET:WIDTH_OFFSET + 256]
    report = json.loads(REPORT.read_text(encoding="utf-8"))
    source = {row["offset"]: row for row in rows_from(SOURCE)}
    reviewed = {row["offset"]: row for row in read_ledger()}
    results = []
    for offset in report["relocations"]:
        old, new = source[offset], reviewed[offset]
        en = lines(old["english"], widths)
        vi = lines(new["vietnamese"], widths)
        longest_en = max(en)
        longest_vi = max(vi)
        results.append({
            "offset": offset,
            "kind": "dialogue" if "{NL}" in old["english"] or "{PAGE}" in old["english"] else "label",
            "english_max_pixels": max(line[0] for line in en),
            "vietnamese_max_pixels": max(line[0] for line in vi),
            "english_max_with_spacing": max(line[1] for line in en),
            "vietnamese_max_with_spacing": max(line[1] for line in vi),
            "english_longest_line": longest_en[2],
            "vietnamese_longest_line": longest_vi[2],
        })
    with OUTPUT.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(results)
    print(f"{len(results)} relocated strings; {sum(r['kind']=='dialogue' for r in results)} dialogue; "
          f"{sum(r['kind']=='label' for r in results)} labels")
    for row in sorted(results, key=lambda r: r["vietnamese_max_with_spacing"], reverse=True)[:25]:
        print(f"{row['offset']} {row['kind']} EN {row['english_max_with_spacing']:3} "
              f"VI {row['vietnamese_max_with_spacing']:3} {row['vietnamese_longest_line']}")
    print("Largest width increases:")
    for row in sorted(results, key=lambda r: r["vietnamese_max_with_spacing"] - r["english_max_with_spacing"], reverse=True)[:35]:
        print(f"{row['offset']} EN {row['english_max_with_spacing']:3} "
              f"VI {row['vietnamese_max_with_spacing']:3} "
              f"+{row['vietnamese_max_with_spacing'] - row['english_max_with_spacing']:3} "
              f"{reviewed[row['offset']]['english'][:35]} → {reviewed[row['offset']]['vietnamese'][:45]}")
    print("Source width envelopes by UI group:")
    groups = {
        "map names": (0x080D54, 0x0817F0),
        "map list": (0x082230, 0x082700),
        "unit labels": (0x282C3C, 0x282D50),
        "CO quotes": (0x2E2564, 0x2E2F70),
        "design help": (0x28072C, 0x280B80),
        "action menu": (0x28B552, 0x28B692),
        "terrain labels": (0x28404C, 0x2840B4),
        "map settings": (0x082700, 0x082920),
        "unit help": (0x2E400C, 0x2E8000),
        "battle labels": (0x2EA000, 0x2EA300),
        "terrain help": (0x2EC710, 0x2EF000),
        "battle maps dialogue": (0x2EF000, 0x2F4000),
        "late dialogue": (0x2F4000, 0x307AE0),
    }
    risks = []
    for name, (start, end) in groups.items():
        members = [old for old in source.values() if start <= int(old["offset"], 16) < end]
        english_widths = [max(line[1] for line in lines(old["english"], widths)) for old in members]
        vietnamese_widths = [max(line[1] for line in lines(reviewed[old["offset"]]["vietnamese"], widths))
                             for old in members if reviewed[old["offset"]]["status"] != "excluded"]
        print(f"{name}: {len(members)} source max {max(english_widths)} "
              f"reviewed max {max(vietnamese_widths)}")
        for old in members:
            new = reviewed[old["offset"]]
            if new["status"] == "excluded":
                continue
            width = max(line[1] for line in lines(new["vietnamese"], widths))
            if width > max(english_widths):
                print(f"  exceeds source envelope: {old['offset']} {width} "
                      f"{new['vietnamese'][:65]}")
                risks.append((old["offset"], name, width, max(english_widths)))
    print("Relocated text against English envelopes in the game's text regions:")
    specific = tuple(groups.values())
    covered = set()
    for start, end in aw_vi_tool.TEXT_RANGES:
        members = [old for old in source.values() if start <= int(old["offset"], 16) < end]
        if not members:
            continue
        envelope = max(max(line[1] for line in lines(old["english"], widths)) for old in members)
        at_risk = [row for row in results if start <= int(row["offset"], 16) < end
                   and not any(a <= int(row["offset"], 16) < b for a, b in specific)
                   and row["vietnamese_max_with_spacing"] > envelope]
        covered.update(row["offset"] for row in results if start <= int(row["offset"], 16) < end)
        print(f"{start:06X}-{end:06X} English envelope {envelope}; "
              f"relocated above it: {len(at_risk)}")
        for row in at_risk:
            print(f"  {row['offset']} {row['vietnamese_max_with_spacing']}")
            risks.append((row["offset"], "general text", row["vietnamese_max_with_spacing"], envelope))
        all_at_risk = [reviewed[old["offset"]] for old in members
                       if reviewed[old["offset"]]["status"] != "excluded"
                       and not any(a <= int(old["offset"], 16) < b for a, b in specific)
                       and max(line[1] for line in lines(reviewed[old["offset"]]["vietnamese"], widths)) > envelope]
        if all_at_risk:
            print(f"  all reviewed entries above source envelope: {len(all_at_risk)} "
                  f"{[row['offset'] for row in all_at_risk[:8]]}")
            risks.extend((row["offset"], "general text", "above source envelope", envelope)
                         for row in all_at_risk)
    covered.update(row["offset"] for row in results
                   if any(a <= int(row["offset"], 16) < b for a, b in specific))
    missing = {row["offset"] for row in results} - covered
    if missing or risks:
        raise ValueError(f"Layout audit failed: ungrouped={sorted(missing)}, excess={risks[:12]}")
    print(f"PASS: all {len(results)} relocated strings and all reviewed entries in "
          "the checked text regions stay within their group's widest original "
          "English line by ROM glyph width (+1 pixel spacing).")


if __name__ == "__main__":
    main()
