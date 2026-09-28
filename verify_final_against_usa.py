"""Verify every final-ROM byte difference against the original USA ROM."""

from __future__ import annotations

import csv
import hashlib
import json
import struct
from collections import Counter
from pathlib import Path

import aw_vi_tool
import map_viet_font
from build_full_accent_rom import encode_text, rows_from
from full_review_ledger import read_ledger
from verify_context_review import RELOCATED


BASE = Path(__file__).resolve().parent
ORIGINAL = BASE / "Advance Wars (USA).gba"
FINAL = BASE / "Advance Wars (Vietnamese) Full Context Final.gba"
REVIEW_BASE = BASE / "Advance Wars (Vietnamese) Context Review 4.gba"
CSV = BASE / "advance_wars_en_vi.csv"
FINAL_REPORT = BASE / "full_context_final_report.json"
OUTPUT = BASE / "original_to_final_verification.json"
EXPECTED_ORIGINAL_SHA1 = "d0a0a4cfe9b95ac7118f7ef476f014ca0242eb65"


def sha1(data: bytes) -> str:
    return hashlib.sha1(data).hexdigest()


def main() -> None:
    original = ORIGINAL.read_bytes()
    final = FINAL.read_bytes()
    review_base = REVIEW_BASE.read_bytes()
    report = json.loads(FINAL_REPORT.read_text(encoding="utf-8"))
    if len(original) != 0x400000 or len(final) != 0x400000:
        raise ValueError("ROM size changed")
    if sha1(original) != EXPECTED_ORIGINAL_SHA1:
        raise ValueError("USA original SHA-1 mismatch")
    if sha1(final) != report["output_rom_sha1"]:
        raise ValueError("Final ROM SHA-1 mismatch")
    rows = rows_from(CSV)
    reviewed = read_ledger()
    if len(rows) != len(reviewed) != 2829:
        raise ValueError("Text row count changed")
    if original[0x3F8000:] != b"\xFF" * (0x400000 - 0x3F8000):
        raise ValueError("Original font-bank destination was not empty")
    if final[:0xC0] != original[:0xC0]:
        raise ValueError("GBA header changed")
    if final[map_viet_font.NATIVE_POINTER_OFFSET:map_viet_font.NATIVE_POINTER_OFFSET + 1024] != original[map_viet_font.NATIVE_POINTER_OFFSET:map_viet_font.NATIVE_POINTER_OFFSET + 1024]:
        raise ValueError("Native font pointers changed")
    if final[map_viet_font.NATIVE_WIDTH_OFFSET:map_viet_font.NATIVE_WIDTH_OFFSET + 256] != original[map_viet_font.NATIVE_WIDTH_OFFSET:map_viet_font.NATIVE_WIDTH_OFFSET + 256]:
        raise ValueError("Native font widths changed")
    allowed: dict[int, str] = {}

    def mark(start: int, end: int, category: str) -> None:
        if not 0 <= start <= end <= len(original):
            raise ValueError(f"Invalid approved interval {start:06X}-{end:06X}")
        for pos in range(start, end):
            previous = allowed.get(pos)
            if previous is not None and previous != category:
                raise ValueError(f"Approved intervals overlap at {pos:06X}: {previous}, {category}")
            allowed[pos] = category

    for row, review in zip(rows, reviewed, strict=True):
        if row["offset"] != review["offset"] or row["english"] != review["english"]:
            raise ValueError("English and review rows differ")
        offset = int(row["offset"], 16)
        raw = bytes.fromhex(row["original_hex"])
        capacity = int(row["max_bytes"])
        if len(raw) != capacity or original[offset:offset + capacity] != raw:
            raise ValueError(f"USA source slot differs at {row['offset']}")
        mark(offset, offset + capacity, "original_text_slot")
        if review["status"] == "excluded":
            if final[offset:offset + capacity] != review_base[offset:offset + capacity]:
                raise ValueError(f"Excluded text changed from reviewed source at {row['offset']}")
            continue
        target = encode_text(review["vietnamese"])
        if not aw_vi_tool.japanese_offset(offset):
            if aw_vi_tool.control_order(raw) != aw_vi_tool.control_order(target):
                raise ValueError(f"Control code sequence differs from USA at {row['offset']}")
            if aw_vi_tool.PRINTF_RE.findall(raw) != aw_vi_tool.PRINTF_RE.findall(target):
                raise ValueError(f"Format placeholders differ from USA at {row['offset']}")
        if row["offset"] in report["relocations"]:
            relocation = report["relocations"][row["offset"]]
            address = int(relocation["address"], 16)
            if final[address:address + len(target) + 1] != target + b"\0":
                raise ValueError(f"New bank text mismatch at {row['offset']}")
            if final[offset:offset + capacity] != original[offset:offset + capacity] and row["offset"] not in RELOCATED:
                # The old slot can contain the prior Vietnamese text; it is
                # allowed by the source-slot mask, but must not grow.
                pass
        elif row["offset"] in RELOCATED:
            ptr = RELOCATED[row["offset"]]
            address = struct.unpack_from("<I", final, ptr)[0] - 0x08000000
            if final[address:address + len(target) + 1] != target + b"\0":
                raise ValueError(f"Earlier bank text mismatch at {row['offset']}")
        else:
            if len(target) > capacity or final[offset:offset + len(target)] != target:
                raise ValueError(f"In-place text exceeds its slot or differs at {row['offset']}")
            if len(target) < capacity and final[offset + len(target)] != 0:
                raise ValueError(f"Shortened text lacks NUL inside slot at {row['offset']}")
        # The byte immediately after the source slot belongs to neither this
        # string nor its terminator. The global diff mask below checks it.

    for pos in map_viet_font.POINTER_LITERAL_OFFSETS + map_viet_font.WIDTH_LITERAL_OFFSETS:
        mark(pos, pos + 4, "font_renderer_reference")
    for offset, expected in RELOCATED.items():
        mark(expected, expected + 4, "earlier_text_pointer")
        old_pointer = 0x08000000 + int(offset, 16)
        if struct.unpack_from("<I", original, expected)[0] != old_pointer:
            raise ValueError(f"Earlier source pointer differs at {offset}")
    pointer_count = 0
    for offset, relocation in report["relocations"].items():
        address = int(relocation["address"], 16)
        for ptr_hex in relocation["pointer_offsets"]:
            ptr = int(ptr_hex, 16)
            mark(ptr, ptr + 4, "new_text_pointer")
            if struct.unpack_from("<I", original, ptr)[0] != 0x08000000 + int(offset, 16):
                raise ValueError(f"Original pointer differs at {ptr_hex}")
            if struct.unpack_from("<I", final, ptr)[0] != 0x08000000 + address:
                raise ValueError(f"Final pointer differs at {ptr_hex}")
            pointer_count += 1
    mark(0x3F8000, 0x400000, "new_font_and_text_bank")
    diff_count = Counter()
    unexpected = []
    for pos, (old, new) in enumerate(zip(original, final, strict=True)):
        if old == new:
            continue
        category = allowed.get(pos)
        if category is None:
            unexpected.append(pos)
        else:
            diff_count[category] += 1
    if unexpected:
        raise ValueError(f"Changed bytes outside approved regions: {[f'{p:06X}' for p in unexpected[:20]]}; total {len(unexpected)}")
    protected_boundaries = 0
    for row in rows:
        boundary = int(row["offset"], 16) + int(row["max_bytes"])
        if boundary < len(original) and boundary not in allowed:
            protected_boundaries += 1
            if final[boundary] != original[boundary]:
                raise ValueError(f"Byte immediately after text slot changed at {row['offset']}")
    result = {
        "original_sha1": sha1(original),
        "final_sha1": sha1(final),
        "rom_bytes": len(final),
        "original_text_slots_verified": len(rows),
        "relocated_texts_verified": len(report["relocations"]),
        "updated_text_pointers_verified": pointer_count + len(RELOCATED),
        "changed_bytes_by_approved_region": dict(diff_count),
        "changed_bytes_outside_approved_regions": 0,
        "unowned_text_slot_boundary_bytes_checked": protected_boundaries,
        "unowned_text_slot_boundary_bytes_changed": 0,
        "native_font_and_gba_header_unchanged": True,
    }
    OUTPUT.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"PASS: original → final, {len(rows)} slots, {len(report['relocations'])} new relocations, "
          f"{pointer_count + len(RELOCATED)} text pointers, 0 unauthorized byte changes; SHA-1 {sha1(final)}")


if __name__ == "__main__":
    main()
