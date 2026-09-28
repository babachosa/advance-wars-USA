"""Patch one short accented Battle Maps sentence into the mapped ROM."""

from __future__ import annotations

import hashlib
import unicodedata
from pathlib import Path

import map_viet_font

BASE = Path(__file__).resolve().parent
SOURCE = BASE / "Advance Wars (Vietnamese) Font Mapped.gba"
OUTPUT = BASE / "Advance Wars (Vietnamese) Accent Demo.gba"
SOURCE_SHA1 = "49a3de055872dc015d7ca6dfb0f718b504dba0ed"
OFFSET = 0x2F1D9C
SLOT_BYTES = 646
OLD = b"Chao mung den Ban Do Chien Dau."
NEW = "Chào mừng đến Bản Đồ Chiến Đấu."


def without_tones(text: str) -> str:
    decomposed = unicodedata.normalize("NFD", text.replace("Đ", "D").replace("đ", "d"))
    return "".join(char for char in decomposed if not unicodedata.combining(char))


def make_image(source: bytes) -> bytes:
    if len(source) != map_viet_font.ROM_SIZE or hashlib.sha1(source).hexdigest() != SOURCE_SHA1:
        raise ValueError("Mapped source ROM does not match the verified SHA-1")
    current = source[OFFSET:OFFSET + SLOT_BYTES].split(b"\0", 1)[0]
    if not current.startswith(b"Vao di!\x0f" + OLD + b"\x0d"):
        raise ValueError("Battle Maps sentence no longer matches the expected text")
    if current.count(OLD) != 1:
        raise ValueError("Sentence is not unique within the text slot")
    if without_tones(NEW) != OLD.decode("ascii"):
        raise ValueError("The sample must change accents only, not wording")
    encoded = map_viet_font.encode_vietnamese(NEW)
    if len(encoded) != len(OLD):
        raise ValueError("Accent-only replacement must keep the same byte length")
    new_text = current.replace(OLD, encoded, 1)
    if len(new_text) > SLOT_BYTES or b"\0" in new_text:
        raise ValueError("New text exceeds its original NUL-terminated slot")
    controls = (0x0D, 0x0F, 0x15, 0x80, 0x81, 0x82, 0x83)
    if [b for b in current if b in controls] != [b for b in new_text if b in controls]:
        raise ValueError("Text control sequence changed")
    out = bytearray(source)
    out[OFFSET:OFFSET + len(current) + 1] = new_text.ljust(len(current), b"\0") + b"\0"
    changed = [i for i, (a, b) in enumerate(zip(source, out)) if a != b]
    if any(not OFFSET <= i < OFFSET + len(current) for i in changed):
        raise ValueError("Unexpected change outside the selected text slot")
    if out[:0xC0] != source[:0xC0]:
        raise ValueError("GBA header changed")
    # Every accented byte in the new sentence resolves to this new ROM bank.
    for char, code in zip(NEW, encoded, strict=True):
        if char in map_viet_font.mapping():
            p = int.from_bytes(out[map_viet_font.POINTER_OFFSET + code * 4:
                                   map_viet_font.POINTER_OFFSET + code * 4 + 4], "little")
            if not map_viet_font.GLYPH_OFFSET <= p - map_viet_font.ROM_BASE < map_viet_font.ROM_SIZE:
                raise ValueError(f"Glyph pointer invalid for {char!r}")
    return bytes(out)


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("build", "check"))
    args = parser.parse_args()
    expected = make_image(SOURCE.read_bytes())
    if args.action == "build":
        if OUTPUT.exists():
            raise SystemExit("Refusing to overwrite the demo ROM")
        OUTPUT.write_bytes(expected)
    elif OUTPUT.read_bytes() != expected:
        raise ValueError("Demo ROM does not match the verified rebuild")
    print(f"PASS: accented Battle Maps sentence; SHA-1 {hashlib.sha1(expected).hexdigest()}")


if __name__ == "__main__":
    main()
