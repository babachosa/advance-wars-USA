"""Build and independently recheck the full English–Vietnamese review ROM."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import struct
from collections import Counter
from pathlib import Path

import aw_vi_tool
from build_full_accent_rom import encode_text, rows_from
from full_review_ledger import LEDGER, SOURCE, read_ledger
from verify_context_review import RELOCATED


BASE = Path(__file__).resolve().parent
SOURCE_ROM = BASE / "Advance Wars (Vietnamese) Context Review 4.gba"
SOURCE_SHA1 = "acda57275804f1f536360e4e19e24efe262c08ac"
OUTPUT_ROM = BASE / "Advance Wars (Vietnamese) Full Context Final.gba"
REPORT = BASE / "full_context_final_report.json"
BANK_START = 0x3FAE80
ROM_SIZE = 0x400000


def digest(data: bytes) -> str:
    return hashlib.sha1(data).hexdigest()


def pointer_hits(data: bytes, address: int) -> list[int]:
    needle = struct.pack("<I", 0x08000000 + address)
    found = []
    pos = 0
    while (pos := data.find(needle, pos)) != -1:
        found.append(pos)
        pos += 1
    return found


def build() -> tuple[bytes, dict]:
    source_rom = SOURCE_ROM.read_bytes()
    if len(source_rom) != ROM_SIZE or digest(source_rom) != SOURCE_SHA1:
        raise ValueError("The verified source ROM changed")
    if any(byte != 0xFF for byte in source_rom[BANK_START:]):
        raise ValueError("The relocation bank is not entirely erased")
    rows = read_ledger()
    originals = rows_from(SOURCE)
    if len(rows) != len(originals) or len(rows) != 2829:
        raise ValueError("Review row count changed")
    if any(row["status"] == "pending" for row in rows):
        raise ValueError("Editorial review still has pending rows")
    out = bytearray(source_rom)
    allowed = set()
    cursor = BANK_START
    relocated = {}
    changed = 0
    for row, old in zip(rows, originals, strict=True):
        if row["offset"] != old["offset"] or row["english"] != old["english"]:
            raise ValueError("The review does not match its frozen source")
        if row["status"] == "excluded":
            if not row["note"].strip():
                raise ValueError(f"Exclusion lacks a reason at {row['offset']}")
            continue
        offset = int(row["offset"], 16)
        cap = int(old["max_bytes"])
        previous = encode_text(old["vietnamese"])
        target = encode_text(row["vietnamese"])
        if aw_vi_tool.control_order(previous) != aw_vi_tool.control_order(target):
            raise ValueError(f"Control tokens changed at {row['offset']}")
        if aw_vi_tool.PRINTF_RE.findall(previous) != aw_vi_tool.PRINTF_RE.findall(target):
            raise ValueError(f"Format placeholders changed at {row['offset']}")
        if old["vietnamese"]:
            if row["offset"] not in RELOCATED and source_rom[offset:offset + len(previous)] != previous:
                raise ValueError(f"Current text differs from the frozen source at {row['offset']}")
        elif source_rom[offset:offset + cap] != bytes.fromhex(old["original_hex"]):
            raise ValueError(f"Untranslated source bytes differ at {row['offset']}")
        if row["offset"] in RELOCATED:
            ptr = RELOCATED[row["offset"]]
            address = struct.unpack_from("<I", source_rom, ptr)[0] - 0x08000000
            if source_rom[address:address + len(previous) + 1] != previous + b"\0":
                raise ValueError(f"Existing relocation differs at {row['offset']}")
            if target != previous:
                raise ValueError(f"Existing relocation was edited at {row['offset']}")
            continue
        if len(target) <= cap:
            # Only the verified source slot can change; a shorter string ends
            # explicitly so bytes left in the old slot cannot be displayed.
            if len(target) < cap:
                payload = target + b"\0"
            else:
                payload = target
            for pos in range(offset, offset + len(payload)):
                if pos in allowed:
                    raise ValueError(f"Overlapping text slot at {row['offset']}")
                allowed.add(pos)
            out[offset:offset + len(payload)] = payload
            if payload != source_rom[offset:offset + len(payload)]:
                changed += 1
            continue
        hits = pointer_hits(source_rom, offset)
        if not hits or any(pos % 4 for pos in hits):
            raise ValueError(f"No aligned pointer table at {row['offset']}: {hits}")
        cursor = (cursor + 3) & ~3
        payload = target + b"\0"
        if cursor + len(payload) > ROM_SIZE:
            raise ValueError("Relocation bank overflow")
        out[cursor:cursor + len(payload)] = payload
        for ptr in hits:
            if any(pos in allowed for pos in range(ptr, ptr + 4)):
                raise ValueError(f"Pointer overlaps text slot at {row['offset']}")
            allowed.update(range(ptr, ptr + 4))
            struct.pack_into("<I", out, ptr, 0x08000000 + cursor)
        relocated[row["offset"]] = {"address": f"{cursor:06X}", "pointer_offsets": [f"{ptr:06X}" for ptr in hits], "bytes": len(payload)}
        allowed.update(range(cursor, cursor + len(payload)))
        cursor += len(payload)
        changed += 1
    if out[:0xC0] != source_rom[:0xC0] or len(out) != ROM_SIZE:
        raise ValueError("GBA header or size changed")
    if out[0x3F8000:BANK_START] != source_rom[0x3F8000:BANK_START]:
        raise ValueError("The Vietnamese font bank or mapping changed")
    unexpected = [pos for pos, (before, after) in enumerate(zip(source_rom, out)) if before != after and pos not in allowed]
    if unexpected:
        raise ValueError(f"Unexpected byte changes: {unexpected[:10]}")
    for row, old in zip(rows, originals, strict=True):
        offset = int(row["offset"], 16)
        if row["status"] == "excluded":
            if out[offset:offset + int(old["max_bytes"])] != source_rom[offset:offset + int(old["max_bytes"] )]:
                raise ValueError(f"Excluded text changed at {row['offset']}")
            continue
        target = encode_text(row["vietnamese"])
        if row["offset"] in relocated:
            address = int(relocated[row["offset"]]["address"], 16)
            if out[address:address + len(target) + 1] != target + b"\0":
                raise ValueError(f"Relocated text mismatch at {row['offset']}")
            for ptr_hex in relocated[row["offset"]]["pointer_offsets"]:
                ptr = int(ptr_hex, 16)
                if struct.unpack_from("<I", out, ptr)[0] != 0x08000000 + address:
                    raise ValueError(f"Pointer mismatch at {row['offset']}")
        elif row["offset"] in RELOCATED:
            ptr = RELOCATED[row["offset"]]
            address = struct.unpack_from("<I", out, ptr)[0] - 0x08000000
            if out[address:address + len(target) + 1] != target + b"\0":
                raise ValueError(f"Earlier relocation mismatch at {row['offset']}")
        elif out[offset:offset + len(target)] != target:
            raise ValueError(f"Text mismatch at {row['offset']}")
    report = {
        "source_rom_sha1": SOURCE_SHA1,
        "output_rom_sha1": digest(out),
        "rom_bytes": len(out),
        "review_status": dict(Counter(row["status"] for row in rows)),
        "changed_entries": changed,
        "relocated_entries": len(relocated),
        "relocation_bank_start": f"{BANK_START:06X}",
        "relocation_bank_end": f"{cursor:06X}",
        "relocation_bank_free_bytes": ROM_SIZE - cursor,
        "native_font_and_header_unchanged": True,
        "changed_bytes_outside_approved_slots_pointers_and_bank": 0,
        "relocations": relocated,
    }
    return bytes(out), report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("build", "check"))
    args = parser.parse_args()
    result, report = build()
    if args.action == "build":
        if OUTPUT_ROM.exists() or REPORT.exists():
            raise SystemExit("Refusing to overwrite the final ROM or report")
        OUTPUT_ROM.write_bytes(result)
        REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    else:
        if OUTPUT_ROM.read_bytes() != result:
            raise ValueError("Final ROM does not match deterministic rebuild")
        if json.loads(REPORT.read_text(encoding="utf-8")) != report:
            raise ValueError("Build report does not match deterministic rebuild")
    print(f"PASS: {report['review_status']}; {report['relocated_entries']} relocations; "
          f"bank ends {report['relocation_bank_end']}; SHA-1 {report['output_rom_sha1']}")


if __name__ == "__main__":
    main()
