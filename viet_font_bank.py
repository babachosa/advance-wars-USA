"""Hand-drawn 8x16 Vietnamese bitmap bank for Advance Wars USA.

This is an inert ROM asset. It deliberately does not patch the game's text
renderer: the renderer has not yet been proven to understand Vietnamese text.
No system font, font package, or rasterizer is used to make these pixels.
"""

from __future__ import annotations

import argparse
import hashlib
import struct
import unicodedata
from pathlib import Path

SOURCE = Path("Advance Wars (Vietnamese) Update 2.gba")
OUTPUT = Path("Advance Wars (Vietnamese) Font Bank.gba")
SOURCE_SHA1 = "4c4b23e4207c14646cf175cc1ed0f5c5a99ff166"
OFFSET = 0x3F8000
END = 0x400000
MAGIC = b"AWVF"
CELL_WIDTH = 8
CELL_HEIGHT = 16

# Each slash-delimited row is seven manually selected pixels. The eighth
# column is available for the Vietnamese horn.
BASE = {
    "A": ".###.../#...#../#...#../#####../#...#../#...#../#...#../.......",
    "B": "####.../#...#../#...#../####.../#...#../#...#../####.../.......",
    "C": ".####../#....../#....../#....../#....../#....../.####../.......",
    "D": "####.../#...#../#...#../#...#../#...#../#...#../####.../.......",
    "E": "#####../#....../#....../####.../#....../#....../#####../.......",
    "F": "#####../#....../#....../####.../#....../#....../#....../.......",
    "G": ".####../#....../#....../#.###../#...#../#...#../.###.#./.......",
    "H": "#...#../#...#../#...#../#####../#...#../#...#../#...#../.......",
    "I": ".###.../..#..../..#..../..#..../..#..../..#..../.###.../.......",
    "J": "..###../...#.../...#.../...#.../#..#.../#..#.../.##..../.......",
    "K": "#...#../#..#.../#.#..../##...../#.#..../#..#.../#...#../.......",
    "L": "#....../#....../#....../#....../#....../#....../#####../.......",
    "M": "#...#../##.##../#.#.#../#.#.#../#...#../#...#../#...#../.......",
    "N": "#...#../##..#../#.#.#../#..##../#...#../#...#../#...#../.......",
    "O": ".###.../#...#../#...#../#...#../#...#../#...#../.###.../.......",
    "P": "####.../#...#../#...#../####.../#....../#....../#....../.......",
    "Q": ".###.../#...#../#...#../#...#../#.#.#../#..#.../.##.#../.......",
    "R": "####.../#...#../#...#../####.../#.#..../#..#.../#...#../.......",
    "S": ".####../#....../#....../.###.../....#../....#../####.../.......",
    "T": "#####../..#..../..#..../..#..../..#..../..#..../..#..../.......",
    "U": "#...#../#...#../#...#../#...#../#...#../#...#../.###.../.......",
    "V": "#...#../#...#../#...#../#...#../#...#../.#.#.../..#..../.......",
    "W": "#...#../#...#../#...#../#.#.#../#.#.#../##.##../#...#../.......",
    "X": "#...#../#...#../.#.#.../..#..../.#.#.../#...#../#...#../.......",
    "Y": "#...#../#...#../.#.#.../..#..../..#..../..#..../..#..../.......",
    "Z": "#####../....#../...#.../..#..../.#...../#....../#####../.......",
    "a": "......./......./.###.../....#../.####../#...#../.####../.......",
    "b": "#....../#....../#.##.../##..#../#...#../#...#../####.../.......",
    "c": "......./......./.###.../#....../#....../#....../.###.../.......",
    "d": "....#../....#../.##.#../#..##../#...#../#...#../.####../.......",
    "e": "......./......./.###.../#...#../#####../#....../.####../.......",
    "f": "..##.../.#..#../.#...../####.../.#...../.#...../.#...../.......",
    "g": "......./......./.####../#...#../#...#../.####../....#../.###...",
    "h": "#....../#....../#.##.../##..#../#...#../#...#../#...#../.......",
    "i": "..#..../......./.##..../..#..../..#..../..#..../.###.../.......",
    "j": "...#.../......./..##.../...#.../...#.../#..#.../.##..../.......",
    "k": "#....../#....../#..#.../#.#..../##...../#.#..../#..#.../.......",
    "l": ".##..../..#..../..#..../..#..../..#..../..#..../.###.../.......",
    "m": "......./......./##.#.../#.#.#../#.#.#../#.#.#../#.#.#../.......",
    "n": "......./......./#.##.../##..#../#...#../#...#../#...#../.......",
    "o": "......./......./.###.../#...#../#...#../#...#../.###.../.......",
    "p": "......./......./####.../#...#../#...#../####.../#....../#......",
    "q": "......./......./.##.#../#..##../#...#../.####../....#../....#..",
    "r": "......./......./#.##.../##..#../#....../#....../#....../.......",
    "s": "......./......./.####../#....../.###.../....#../####.../.......",
    "t": ".#...../.#...../####.../.#...../.#...../.#..#../..##.../.......",
    "u": "......./......./#...#../#...#../#...#../#..##../.##.#../.......",
    "v": "......./......./#...#../#...#../#...#../.#.#.../..#..../.......",
    "w": "......./......./#...#../#.#.#../#.#.#../##.##../#...#../.......",
    "x": "......./......./#...#../.#.#.../..#..../.#.#.../#...#../.......",
    "y": "......./......./#...#../#...#../.####../....#../#...#../.###...",
    "z": "......./......./#####../...#.../..#..../.#...../#####../.......",
}

# The letters that receive Vietnamese marks are redrawn pixel by pixel to
# match the game's native body metrics. This keeps the body of an accented
# letter on the same row and at the same size as its unaccented counterpart.
# Each tuple gives the first occupied row and hand-authored bitmap rows.
VI_BASE = {
    "A": (4, "...#.../..###../..###../.##.##./.##.##./#######/##...##/#.....#/#.....#"),
    "E": (4, "######./#....../#....../#....../#####../#....../#....../#....../######."),
    "I": (4, "#......./#......./#......./#......./#......./#......./#......./#......./#......."),
    "O": (4, "..###../.##.##./##...##/#.....#/#.....#/#.....#/##...##/.##.##./..###.."),
    "U": (4, "#.....#/#.....#/#.....#/#.....#/#.....#/#.....#/#.....#/##...##/.#####."),
    "Y": (4, "#.....#/##...##/.#...#./.##.##./..#.#../..###../...#.../...#.../...#..."),
    "D": (4, "####.../#..##../#...##./#....#./#....#./#....#./#...##./#..##../####..."),
    "a": (8, "####.../#..#.../#..#.../#..#.../#####..."),
    "e": (8, "####..../#..#..../####..../#......./####...."),
    "i": (6, "#......./......../#......./#......./#......./#......./#......."),
    "o": (8, "####..../#..#..../#..#..../#..#..../####...."),
    "u": (8, "#..#..../#..#..../#..#..../#..#..../####...."),
    "y": (8, "#..#..../#..#..../#..#..../#..#..../####..../...#..../####...."),
    "d": (5, "...#..../...#..../...#..../####..../#..#..../#..#..../#..#..../#####..."),
}

# Pixel coordinates are in the same 8x16 cell. Tone marks on letters with a
# shape mark occupy rows 0-2; all other top marks occupy rows 3-5.
TOP_MARKS = {
    "\u0300": (".#......", "..#.....", "...#...."),  # grave: top left, bottom right
    "\u0301": ("....#...", "...#....", "..#....."),  # acute: top right, bottom left
    "\u0303": (".##.##..", "#..#..#.", "........"),  # tilde
    "\u0309": ("..##....", "....#...", "...#...."),  # hook above
}
TOP_MARKS_NARROW = {
    "\u0300": ("#.......", ".#......", "..#....."),
    "\u0301": ("...#....", "..#.....", ".#......"),
    "\u0303": (".#.#....", "#.#.....", "........"),
    "\u0309": (".##.....", "...#....", "..#....."),
}
TOP_MARKS_THIN = {
    "\u0300": ("#.......", ".#......", ".#......"),
    "\u0301": (".#......", "#.......", "#......."),
    "\u0303": ("#.#.....", ".#......", "........"),
    "\u0309": ("##......", ".#......", "#......."),
}
TOP_MARKS_MEDIUM = dict(TOP_MARKS)
TOP_MARKS_MEDIUM["\u0303"] = (".#.#....", "#.#.#...", "........")
SHAPE_MARKS = {
    "\u0302": ("..#.....", ".#.#...."),  # circumflex
    "\u0306": ("#...#...", ".###...."),  # breve
}
SHAPE_MARKS_WIDE = {
    "\u0302": ("...#....", "..#.#..."),
    "\u0306": (".#...#..", "..###..."),
}
VOWELS = "aăâeêioôơuưy"
TONES = ("", "\u0300", "\u0301", "\u0309", "\u0303", "\u0323")


def compose(letter: str, tone: str) -> bytes:
    decomp = unicodedata.normalize("NFD", letter)
    base = {"đ": "d", "Đ": "D"}.get(decomp[0], decomp[0])
    shape = next((c for c in decomp[1:] if c in SHAPE_MARKS), "")
    horn = "\u031b" in decomp
    rows = [0] * CELL_HEIGHT
    start, patterns = VI_BASE.get(base, (7, BASE[base]))
    for y, pattern in enumerate(patterns.split("/"), start):
        for x, pixel in enumerate(pattern):
            if pixel == "#":
                rows[y] |= 1 << (7 - x)
    if base == "i" and tone:
        rows[6] = 0  # accented i replaces its dot with the tone mark
    if base in "dD" and letter.lower() == "đ":
        rows[7 if base == "d" else 8] |= 0b01111000
    body_width = max((8 - (row & -row).bit_length() + 1 for row in rows if row), default=1)
    if shape:
        shape_y = 2 if base.isupper() else 6
        shape_rows = SHAPE_MARKS_WIDE[shape] if body_width >= 6 else SHAPE_MARKS[shape]
        for y, pattern in enumerate(shape_rows, shape_y):
            for x, pixel in enumerate(pattern):
                if pixel == "#":
                    rows[y] |= 1 << (7 - x)
    if horn:
        horn_pixels = ((6, 5), (7, 4), (7, 5), (6, 6)) if base.isupper() else ((3, 8), (4, 7), (5, 7), (4, 9))
        for x, y in horn_pixels:
            rows[y] |= 1 << (7 - x)
    if tone == "\u0323":
        dot_x = {1: (0,), 4: (1, 2), 5: (2,), 6: (2, 3), 7: (3,)}[body_width]
        for x in dot_x:
            rows[15] |= 1 << (7 - x)
    elif tone:
        mark_set = (TOP_MARKS_THIN if body_width == 1 else
                    TOP_MARKS_NARROW if body_width <= 4 else
                    TOP_MARKS_MEDIUM if body_width <= 6 else TOP_MARKS)
        if shape and base.isupper():
            rise = 0
            patterns = mark_set[tone][:2]
        else:
            rise = (2 if shape else 1) if base.isupper() else (2 if shape else 5)
            patterns = mark_set[tone]
        for y, pattern in enumerate(patterns, rise):
            for x, pixel in enumerate(pattern):
                if pixel == "#":
                    rows[y] |= 1 << (7 - x)
    return bytes(rows)


def glyphs() -> dict[str, bytes]:
    result = {c: compose(c, "") for c in BASE}
    for base in VOWELS:
        for case in (base, base.upper()):
            for tone in TONES:
                char = unicodedata.normalize("NFC", case + tone)
                result[char] = compose(case, tone)
    for c in "đĐ":
        result[c] = compose(c, "")
    return dict(sorted(result.items(), key=lambda item: ord(item[0])))


def bank_bytes() -> bytes:
    items = glyphs()
    # Header: magic, version, cell width/height, count, table/data offsets.
    header = struct.pack("<4sBBBBIII", MAGIC, 1, CELL_WIDTH, CELL_HEIGHT, 1,
                         len(items), 20, 20 + len(items) * 4)
    table = b"".join(struct.pack("<I", ord(c)) for c in items)
    return header + table + b"".join(items.values())


def validate(source: bytes, patched: bytes) -> None:
    assert hashlib.sha1(source).hexdigest() == SOURCE_SHA1
    assert len(source) == len(patched) == END
    assert patched[:OFFSET] == source[:OFFSET]
    assert source[OFFSET:] == b"\xff" * (END - OFFSET)
    bank = bank_bytes()
    assert patched[OFFSET:OFFSET + len(bank)] == bank
    assert patched[OFFSET + len(bank):] == b"\xff" * (END - OFFSET - len(bank))
    assert len(bank) <= END - OFFSET
    # GBA header checksum and identification remain byte-for-byte identical.
    assert source[:0xC0] == patched[:0xC0]
    assert ((-sum(patched[0xA0:0xBD]) - 0x19) & 0xFF) == patched[0xBD]
    items = glyphs()
    assert len(items) == 186
    assert all(len(rows) == 8 and all(len(row) == 7 and set(row) <= {".", "#"} for row in rows)
               for rows in (pattern.split("/") for pattern in BASE.values()))
    assert all(0 <= start < CELL_HEIGHT and start + len(pattern.split("/")) <= CELL_HEIGHT
               and all(len(row) in (7, 8) and set(row) <= {".", "#"} for row in pattern.split("/"))
               for start, pattern in VI_BASE.values())
    assert all(len(pixel_rows) == CELL_HEIGHT for pixel_rows in items.values())
    assert len(set(items.values())) == len(items), "Two different characters have identical pixels"
    # Independently compare the manually transcribed bodies with native pixels.
    for char in VI_BASE:
        code = ord(char)
        width = source[0x3099FC + code]
        address = struct.unpack_from("<I", source, 0x3095FC + code * 4)[0] - 0x08000000
        row_bytes = (width + 1) // 2
        native = bytearray(16)
        for y in range(16):
            packed = source[address + y * row_bytes:address + (y + 1) * row_bytes]
            for x in range(width):
                if (packed[x // 2] >> (4 * (x % 2))) & 15:
                    native[y] |= 0x80 >> x
        assert items[char] == native, f"Base pixels differ from native {char}"
    # Screen y grows downward: acute rises right; grave falls right.
    for marks in (TOP_MARKS, TOP_MARKS_NARROW, TOP_MARKS_MEDIUM, TOP_MARKS_THIN):
        acute_x = [row.index("#") for row in marks["\u0301"]]
        grave_x = [row.index("#") for row in marks["\u0300"]]
        assert acute_x[0] > acute_x[-1] and all(a >= b for a, b in zip(acute_x, acute_x[1:]))
        assert grave_x[0] < grave_x[-1] and all(a <= b for a, b in zip(grave_x, grave_x[1:]))
    for base in VOWELS:
        for case in (base, base.upper()):
            plain = compose(case, "")
            for tone in TONES:
                char = unicodedata.normalize("NFC", case + tone)
                ink = items[char]
                # The base is unchanged below the accents, except i's dot.
                assert all((marked & unmarked) == unmarked for marked, unmarked in
                           zip(ink[8:15], plain[8:15])), char
                assert ink[12] & plain[12] == plain[12], char
                assert len(ink) == 16, char
            assert compose(case, "\u0300")[8:15] == compose(case, "\u0301")[8:15]
    # No unaligned or aligned literal ROM pointer currently targets this bank.
    for address in range(0x08000000 + OFFSET, 0x08000000 + OFFSET + len(bank), 4):
        assert struct.pack("<I", address) not in source[:OFFSET]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("build", "check"))
    args = parser.parse_args()
    source = SOURCE.read_bytes()
    if args.action == "build":
        if OUTPUT.exists():
            raise SystemExit(f"Refusing to overwrite {OUTPUT}")
        if source[OFFSET:] != b"\xff" * (END - OFFSET):
            raise SystemExit("The selected ROM tail is not empty")
        patched = source[:OFFSET] + bank_bytes().ljust(END - OFFSET, b"\xff")
        validate(source, patched)
        OUTPUT.write_bytes(patched)
    else:
        patched = OUTPUT.read_bytes()
        validate(source, patched)
    print(f"PASS: {len(glyphs())} manually drawn glyphs, {len(bank_bytes())} bank bytes")
    print(f"ROM SHA-1: {hashlib.sha1(patched).hexdigest()}")


if __name__ == "__main__":
    main()
