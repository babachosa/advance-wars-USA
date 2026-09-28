"""Accent only the standalone 'Mung den Advance Wars!' sentence."""

from __future__ import annotations

import hashlib
from pathlib import Path

import map_viet_font
from patch_viet_sample import without_tones

BASE = Path(__file__).resolve().parent
SOURCE = BASE / "Advance Wars (Vietnamese) Accent Demo.gba"
OUTPUT = BASE / "Advance Wars (Vietnamese) Accent Demo 2.gba"
SOURCE_SHA1 = "c2167874d4f948909b0bf5b0fd327a2d4745e1da"
OFFSET = 0x2EFD10
OLD = b"Mung den Advance Wars!"
NEW = "Mừng đến Advance Wars!"
PAGE = 0x0F


def make_image(source: bytes) -> bytes:
    if len(source) != map_viet_font.ROM_SIZE or hashlib.sha1(source).hexdigest() != SOURCE_SHA1:
        raise ValueError("First accent-demo ROM does not match its verified SHA-1")
    if without_tones(NEW) != OLD.decode("ascii"):
        raise ValueError("The change must add accents only")
    encoded = map_viet_font.encode_vietnamese(NEW)
    if len(encoded) != len(OLD):
        raise ValueError("Accented sentence changed its byte length")
    before = OLD + bytes((PAGE, 0))
    after = encoded + bytes((PAGE, 0))
    if source[OFFSET:OFFSET + len(before)] != before:
        raise ValueError("Standalone sentence or PAGE control has changed")
    out = bytearray(source)
    out[OFFSET:OFFSET + len(after)] = after
    changed = [i for i, (a, b) in enumerate(zip(source, out)) if a != b]
    if any(not OFFSET <= i < OFFSET + len(OLD) for i in changed):
        raise ValueError("Unexpected change outside the selected sentence")
    for char, code in zip(NEW, encoded, strict=True):
        if char in map_viet_font.mapping():
            p = int.from_bytes(out[map_viet_font.POINTER_OFFSET + 4 * code:
                                   map_viet_font.POINTER_OFFSET + 4 * code + 4], "little")
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
            raise SystemExit("Refusing to overwrite the second demo ROM")
        OUTPUT.write_bytes(expected)
    elif OUTPUT.read_bytes() != expected:
        raise ValueError("Second demo ROM does not match the verified rebuild")
    print(f"PASS: standalone welcome sentence; SHA-1 {hashlib.sha1(expected).hexdigest()}")


if __name__ == "__main__":
    main()
