"""Connect the hand-drawn Vietnamese bank to AW1's active 8-bit glyph renderer.

The original pointer/width tables and original glyph data are never modified.
Only four literal references in the renderer/width readers are redirected to
new tables in the verified FF tail. This does not translate existing strings.
"""

from __future__ import annotations

import hashlib
import json
import struct
import unicodedata
from functools import lru_cache
from pathlib import Path

import aw_vi_tool
import viet_font_bank

BASE = Path(__file__).resolve().parent
SOURCE = BASE / "Advance Wars (Vietnamese) Font Bank.gba"
OUTPUT = BASE / "Advance Wars (Vietnamese) Font Mapped.gba"
MAP_FILE = BASE / "viet_font_mapping.json"
SOURCE_SHA1 = "714229b64a5d3d2e4d6fb69d11f787421a2756ef"
MAP_OFFSET = 0x3F9000
POINTER_OFFSET = MAP_OFFSET + 0x20
WIDTH_OFFSET = POINTER_OFFSET + 256 * 4
GLYPH_OFFSET = WIDTH_OFFSET + 256
NATIVE_POINTER_OFFSET = 0x3095FC
NATIVE_WIDTH_OFFSET = 0x3099FC
ROM_BASE = 0x08000000
ROM_SIZE = 0x400000

# 0x84..0xFF are not used by the ordinary English/Vietnamese text in this
# exact ROM. The ten punctuation codes below are absent from extracted normal
# strings; they are byte slots, not characters in the translated text.
EXTRA_CODES = (0x24, 0x3D, 0x5B, 0x5C, 0x5D, 0x5E, 0x5F, 0x60, 0x7B, 0x7C)
CODES = tuple(range(0x84, 0x100)) + EXTRA_CODES
POINTER_LITERAL_OFFSETS = (0x52330,)
WIDTH_LITERAL_OFFSETS = (0x19284, 0x48210, 0x5232C)


@lru_cache(maxsize=1)
def accent_glyphs() -> dict[str, bytes]:
    chars = {c: bitmap for c, bitmap in viet_font_bank.glyphs().items()
             if ord(c) > 0x7F}
    assert len(chars) == 134
    return chars


@lru_cache(maxsize=1)
def mapping() -> dict[str, int]:
    return dict(zip(accent_glyphs(), CODES, strict=True))


def encode_vietnamese(text: str) -> bytes:
    """Encode ordinary visible text for the mapped one-byte glyph table.

    Game control bytes must be inserted separately by a text editor that knows
    their meaning. Reserved ASCII slots cannot also represent punctuation.
    """
    result = bytearray()
    char_to_code = mapping()
    for char in unicodedata.normalize("NFC", text):
        if char in char_to_code:
            result.append(char_to_code[char])
        elif 0x20 <= ord(char) <= 0x7E and ord(char) not in EXTRA_CODES:
            result.append(ord(char))
        else:
            raise ValueError(f"Unsupported text character: {char!r}")
    return bytes(result)


def native_bitmap(rows: bytes, width: int) -> bytes:
    """Pack hand-authored 1bpp rows into AW1's 4bpp nibble layout.

    AW1 uses nibble A for its solid font ink; the renderer recolors that nibble
    according to the existing text style. Pixel 0 is the low nibble.
    """
    assert len(rows) == 16 and 1 <= width <= 8
    out = bytearray()
    for row in rows:
        for left in range(0, width, 2):
            lo = 0xA if row & (0x80 >> left) else 0
            hi = 0xA if left + 1 < width and row & (0x80 >> (left + 1)) else 0
            out.append(lo | (hi << 4))
    return bytes(out)


def ink_width(rows: bytes) -> int:
    return max((8 - (row & -row).bit_length() + 1 for row in rows if row), default=1)


def ensure_slots_unused() -> None:
    original = aw_vi_tool.load_rom(BASE / "Advance Wars (USA).gba")
    translated = SOURCE.read_bytes()
    entries = aw_vi_tool.extract(original)
    normal = [(offset, raw) for offset, raw in entries
              if not aw_vi_tool.japanese_offset(offset)]
    used = set(CODES)
    collisions = [(offset, byte) for offset, raw in normal for byte in raw if byte in used]
    for offset, original_raw in normal:
        # The localized ROM keeps each NUL-terminated string in its original
        # slot; padding after its new terminator is irrelevant.
        raw = translated[offset:offset + len(original_raw)].split(b"\0", 1)[0]
        collisions.extend((offset + i, byte) for i, byte in enumerate(raw) if byte in used)
    if collisions:
        raise ValueError(f"Reserved code present in original/translated text: {collisions[:8]}")


def build_image(source: bytes) -> bytes:
    if len(source) != ROM_SIZE or hashlib.sha1(source).hexdigest() != SOURCE_SHA1:
        raise ValueError("Input font-bank ROM does not match the verified source")
    if source[MAP_OFFSET:] != b"\xff" * (ROM_SIZE - MAP_OFFSET):
        raise ValueError("Font mapping area is not empty")
    ensure_slots_unused()
    char_to_code = mapping()
    pointers = bytearray(source[NATIVE_POINTER_OFFSET:NATIVE_POINTER_OFFSET + 1024])
    widths = bytearray(source[NATIVE_WIDTH_OFFSET:NATIVE_WIDTH_OFFSET + 256])
    glyph_data = bytearray()
    for char, code in char_to_code.items():
        rows = accent_glyphs()[char]
        width = ink_width(rows)
        pointer = ROM_BASE + GLYPH_OFFSET + len(glyph_data)
        struct.pack_into("<I", pointers, code * 4, pointer)
        widths[code] = width
        glyph_data.extend(native_bitmap(rows, width))
    end = GLYPH_OFFSET + len(glyph_data)
    if end > ROM_SIZE:
        raise ValueError("Mapped glyphs exceed ROM tail")
    out = bytearray(source)
    out[MAP_OFFSET:MAP_OFFSET + 0x20] = struct.pack(
        "<4sIIIIIII", b"AWVM", 1, len(char_to_code),
        ROM_BASE + POINTER_OFFSET, ROM_BASE + WIDTH_OFFSET,
        ROM_BASE + GLYPH_OFFSET, end - GLYPH_OFFSET, 0)
    out[POINTER_OFFSET:POINTER_OFFSET + len(pointers)] = pointers
    out[WIDTH_OFFSET:WIDTH_OFFSET + len(widths)] = widths
    out[GLYPH_OFFSET:end] = glyph_data
    for off in POINTER_LITERAL_OFFSETS:
        if struct.unpack_from("<I", source, off)[0] != ROM_BASE + NATIVE_POINTER_OFFSET:
            raise ValueError(f"Unexpected original pointer literal at {off:06X}")
        struct.pack_into("<I", out, off, ROM_BASE + POINTER_OFFSET)
    for off in WIDTH_LITERAL_OFFSETS:
        if struct.unpack_from("<I", source, off)[0] != ROM_BASE + NATIVE_WIDTH_OFFSET:
            raise ValueError(f"Unexpected original width literal at {off:06X}")
        struct.pack_into("<I", out, off, ROM_BASE + WIDTH_OFFSET)
    validate(source, bytes(out))
    return bytes(out)


def validate(source: bytes, out: bytes) -> None:
    assert len(source) == len(out) == ROM_SIZE
    assert source[:0xC0] == out[:0xC0]
    assert source[NATIVE_POINTER_OFFSET:NATIVE_POINTER_OFFSET + 1024] == \
           out[NATIVE_POINTER_OFFSET:NATIVE_POINTER_OFFSET + 1024]
    assert source[NATIVE_WIDTH_OFFSET:NATIVE_WIDTH_OFFSET + 256] == \
           out[NATIVE_WIDTH_OFFSET:NATIVE_WIDTH_OFFSET + 256]
    allowed = set(range(MAP_OFFSET, ROM_SIZE))
    for off in POINTER_LITERAL_OFFSETS + WIDTH_LITERAL_OFFSETS:
        allowed.update(range(off, off + 4))
    if any(a != b and i not in allowed for i, (a, b) in enumerate(zip(source, out))):
        raise ValueError("Unexpected ROM modification outside mapping area")
    for char, code in mapping().items():
        p = struct.unpack_from("<I", out, POINTER_OFFSET + code * 4)[0]
        width = out[WIDTH_OFFSET + code]
        rows = accent_glyphs()[char]
        expected = native_bitmap(rows, width)
        assert GLYPH_OFFSET <= p - ROM_BASE < ROM_SIZE
        assert out[p - ROM_BASE:p - ROM_BASE + len(expected)] == expected
    for off in POINTER_LITERAL_OFFSETS:
        assert struct.unpack_from("<I", out, off)[0] == ROM_BASE + POINTER_OFFSET
    for off in WIDTH_LITERAL_OFFSETS:
        assert struct.unpack_from("<I", out, off)[0] == ROM_BASE + WIDTH_OFFSET
    # Encoding a representative phrase must reach the exact mapped slots.
    example = "Tiếng Việt đủ dấu"
    encoded = encode_vietnamese(example)
    for char, code in zip(example, encoded, strict=True):
        if char in mapping():
            assert code == mapping()[char]
            assert struct.unpack_from("<I", out, POINTER_OFFSET + code * 4)[0] >= ROM_BASE + GLYPH_OFFSET


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("build", "check", "encode"))
    parser.add_argument("text", nargs="?")
    args = parser.parse_args()
    if args.action == "encode":
        if args.text is None:
            parser.error("encode requires a text argument")
        print(encode_vietnamese(args.text).hex(" ").upper())
        return
    source = SOURCE.read_bytes()
    expected = build_image(source)
    if args.action == "build":
        if OUTPUT.exists() or MAP_FILE.exists():
            raise SystemExit("Refusing to overwrite mapped ROM or mapping file")
        OUTPUT.write_bytes(expected)
        payload = {
            "rom_base_sha1": SOURCE_SHA1,
            "rom_mapped_sha1": hashlib.sha1(expected).hexdigest(),
            "character_to_byte": {char: f"{code:02X}" for char, code in mapping().items()},
        }
        MAP_FILE.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
                            encoding="utf-8")
    else:
        actual = OUTPUT.read_bytes()
        if actual != expected:
            raise ValueError("Mapped ROM does not match verified rebuild")
        recorded = json.loads(MAP_FILE.read_text(encoding="utf-8"))
        assert recorded["character_to_byte"] == \
               {char: f"{code:02X}" for char, code in mapping().items()}
    print(f"PASS: mapped {len(mapping())} Vietnamese glyphs; SHA-1 "
          f"{hashlib.sha1(expected).hexdigest()}")


if __name__ == "__main__":
    main()
