"""Build a one-byte Vietnamese ROM from an accent-only reviewed CSV."""

from __future__ import annotations

import argparse
import csv
import hashlib
import unicodedata
from pathlib import Path

import aw_vi_tool
import map_viet_font

BASE = Path(__file__).resolve().parent
SOURCE = BASE / "Advance Wars (Vietnamese) Accent Demo 2.gba"
SOURCE_SHA1 = "599138a74a408c82ec23aee53f65557025c023a1"
ORIGINAL_CSV = BASE / "advance_wars_en_vi.csv"
ACCENTED_CSV = BASE / "advance_wars_vi_accented.csv"
OUTPUT = BASE / "Advance Wars (Vietnamese) Final.gba"


def strip_accents(text: str) -> str:
    text = text.replace("đ", "d").replace("Đ", "D")
    return "".join(c for c in unicodedata.normalize("NFD", text)
                   if not unicodedata.combining(c))


def encode_text(value: str) -> bytes:
    result = bytearray()
    pos = 0
    while pos < len(value):
        if value[pos] == "{":
            match = aw_vi_tool.TOKEN_RE.match(value, pos)
            if not match:
                raise ValueError(f"Invalid control token at {pos}: {value[pos:pos+16]!r}")
            token = match.group(1)
            byte = aw_vi_tool.TOKEN_TO_BYTE.get(token)
            if byte is None:
                byte = int(token, 16)
                if byte not in (ord("{"), ord("}")):
                    raise ValueError(f"Unapproved control token: {token}")
            result.append(byte)
            pos = match.end()
        else:
            next_token = value.find("{", pos)
            if next_token < 0:
                next_token = len(value)
            result.extend(map_viet_font.encode_vietnamese(value[pos:next_token]))
            pos = next_token
    return bytes(result)


REVERSE_MAPPING = {code: char for char, code in map_viet_font.mapping().items()}


def unaccent_mapped_bytes(raw: bytes) -> bytes:
    return bytes(ord(strip_accents(REVERSE_MAPPING[byte])) if byte in REVERSE_MAPPING else byte
                 for byte in raw)


def rows_from(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as file:
        reader = csv.DictReader(file)
        if tuple(reader.fieldnames or ()) != aw_vi_tool.CSV_FIELDS:
            raise ValueError(f"CSV fields differ from {aw_vi_tool.CSV_FIELDS}")
        return list(reader)


def build_image(source: bytes) -> tuple[bytes, int, int]:
    if len(source) != map_viet_font.ROM_SIZE or hashlib.sha1(source).hexdigest() != SOURCE_SHA1:
        raise ValueError("Current ROM SHA-1 does not match the verified source")
    old_rows = rows_from(ORIGINAL_CSV)
    new_rows = rows_from(ACCENTED_CSV)
    if len(old_rows) != 2829 or len(new_rows) != 2829:
        raise ValueError("CSV row count changed")
    out = bytearray(source)
    allowed = set()
    translated = accented = 0
    for old, new in zip(old_rows, new_rows, strict=True):
        if any(old[field] != new[field] for field in aw_vi_tool.CSV_FIELDS if field != "vietnamese"):
            raise ValueError(f"CSV metadata changed at {old['offset']}")
        offset = int(old["offset"], 16)
        original_value = old["vietnamese"]
        target_value = new["vietnamese"]
        if not original_value:
            if target_value:
                raise ValueError(f"Untranslated source was altered at {offset:06X}")
            continue
        translated += 1
        if strip_accents(target_value) != original_value:
            raise ValueError(f"Not an accent-only edit at {offset:06X}")
        before = aw_vi_tool.parse_translation(original_value)
        after = encode_text(target_value)
        if len(before) != len(after) or len(after) > int(old["max_bytes"]):
            raise ValueError(f"Text length changed at {offset:06X}")
        if aw_vi_tool.control_order(before) != aw_vi_tool.control_order(after):
            raise ValueError(f"Control byte order changed at {offset:06X}")
        if aw_vi_tool.PRINTF_RE.findall(before) != aw_vi_tool.PRINTF_RE.findall(after):
            raise ValueError(f"Format placeholders changed at {offset:06X}")
        current = source[offset:offset + len(before)]
        if unaccent_mapped_bytes(current) != before:
            raise ValueError(f"Current ROM text does not match CSV at {offset:06X}")
        # Some UI labels are fixed-width fields followed by control bytes,
        # rather than NUL-terminated strings. Never write beyond this slot.
        slot = set(range(offset, offset + len(before)))
        if slot & allowed:
            raise ValueError(f"Overlapping text slots at {offset:06X}")
        allowed.update(slot)
        out[offset:offset + len(before)] = after
        if after != before:
            accented += 1
    if translated != 2774:
        raise ValueError(f"Translated row count changed: {translated}")
    if any(a != b and i not in allowed for i, (a, b) in enumerate(zip(source, out))):
        raise ValueError("Unexpected ROM modification outside translated text slots")
    if out[:0xC0] != source[:0xC0]:
        raise ValueError("GBA header changed")
    return bytes(out), translated, accented


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("build", "check"))
    args = parser.parse_args()
    expected, translated, accented = build_image(SOURCE.read_bytes())
    if args.action == "build":
        if OUTPUT.exists():
            raise SystemExit("Refusing to overwrite the final ROM")
        OUTPUT.write_bytes(expected)
    elif OUTPUT.read_bytes() != expected:
        raise ValueError("Final ROM does not match verified rebuild")
    print(f"PASS: {accented}/{translated} translated rows accented; "
          f"SHA-1 {hashlib.sha1(expected).hexdigest()}")


if __name__ == "__main__":
    main()
