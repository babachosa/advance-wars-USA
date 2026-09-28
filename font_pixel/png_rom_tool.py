"""Export the active Vietnamese ROM font as raw pixels and import Paint edits.

The editable atlas has no padding or labels: each 8x16 block is one glyph.
Only pure black and white pixels are accepted on import.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import struct

from PIL import Image, ImageDraw, ImageFont

try:
    from .build_font import BANK, DATA, HEADER, ROM_BASE, TABLE, decode
except ImportError:
    from build_font import BANK, DATA, HEADER, ROM_BASE, TABLE, decode


ROOT = Path(__file__).resolve().parent.parent
DEFAULT_ROM = ROOT / "Advance Wars (Vietnamese) Pixel Font.gba"
DEFAULT_OUTPUT = ROOT / "Advance Wars (Vietnamese) Pixel Font Edited.gba"
DEFAULT_DIR = Path(__file__).resolve().parent / "raw_edit"
COLS = 16
CELL_W, CELL_H = 8, 16


def sha1(data: bytes) -> str:
    return hashlib.sha1(data).hexdigest()


def font_entries(rom: bytes) -> list[dict]:
    if len(rom) != 0x400000:
        raise ValueError("ROM must be exactly 4 MiB")
    magic, version, cw, ch, fmt, count, table_at, pixels_at = struct.unpack_from(
        "<4sBBBBIII", rom, BANK
    )
    if (magic, version, cw, ch, fmt, table_at, pixels_at) != (
        b"AWVF", 2, 8, 16, 1, 20, 20 + count * 4
    ) or count != 186:
        raise ValueError("ROM does not contain the expected pixel font bank")
    if struct.unpack_from("<4sI", rom, HEADER) != (b"AWVM", 2):
        raise ValueError("ROM does not contain the expected active font header")
    chars = [chr(struct.unpack_from("<I", rom, BANK + table_at + i * 4)[0])
             for i in range(count)]
    if len(set(chars)) != count:
        raise ValueError("Duplicate characters in font bank")
    mapping = json.loads((ROOT / "viet_font_mapping.json").read_text(encoding="utf-8"))["character_to_byte"]
    entries = []
    used_codes = set()
    for i, char in enumerate(chars):
        code = int(mapping.get(char, f"{ord(char):02X}"), 16)
        if code in used_codes:
            raise ValueError(f"Duplicate font code {code:02X}")
        used_codes.add(code)
        bitmap, width = decode(rom, code)
        bank_at = BANK + pixels_at + i * 16
        if rom[bank_at:bank_at + 16] != bitmap:
            raise ValueError(f"Font bank and active glyph differ: {char} ({code:02X})")
        address = struct.unpack_from("<I", rom, TABLE + code * 4)[0] - ROM_BASE
        if not DATA <= address < len(rom):
            raise ValueError(f"Glyph pointer outside active font area: {char}")
        entries.append({"char": char, "code": f"{code:02X}", "width": width,
                        "address": address, "bank_address": bank_at, "bitmap": bitmap})
    return entries


def atlas_size(count: int) -> tuple[int, int]:
    return COLS * CELL_W, ((count + COLS - 1) // COLS) * CELL_H


def make_atlas(entries: list[dict]) -> Image.Image:
    image = Image.new("RGB", atlas_size(len(entries)), "white")
    pixels = image.load()
    for i, entry in enumerate(entries):
        ox, oy = (i % COLS) * CELL_W, (i // COLS) * CELL_H
        for y, row in enumerate(entry["bitmap"]):
            for x in range(CELL_W):
                if row & (0x80 >> x):
                    pixels[ox + x, oy + y] = (0, 0, 0)
    return image


def make_guide(entries: list[dict], path: Path) -> None:
    scale, label_h = 5, 27
    tile_w, tile_h = 60, CELL_H * scale + label_h
    image = Image.new("RGB", (COLS * tile_w, ((len(entries) + COLS - 1) // COLS) * tile_h), "#f5f3ee")
    draw = ImageDraw.Draw(image)
    try:
        font = ImageFont.truetype("C:/Windows/Fonts/arial.ttf", 16)
    except OSError:
        font = ImageFont.load_default()
    for i, entry in enumerate(entries):
        tx, ty = (i % COLS) * tile_w, (i // COLS) * tile_h
        draw.rectangle((tx, ty, tx + tile_w - 1, ty + tile_h - 1), outline="#a6aaa6")
        draw.text((tx + 3, ty + 3), f'{entry["char"]} {entry["code"]}', font=font, fill="black")
        for y, row in enumerate(entry["bitmap"]):
            for x in range(CELL_W):
                if row & (0x80 >> x):
                    draw.rectangle((tx + 10 + x * scale, ty + label_h + y * scale,
                                    tx + 9 + (x + 1) * scale, ty + label_h - 1 + (y + 1) * scale),
                                   fill="black")
    image.save(path)


def export(rom_path: Path, folder: Path) -> None:
    rom = rom_path.read_bytes()
    entries = font_entries(rom)
    folder.mkdir(parents=True, exist_ok=True)
    raw = folder / "font_raw.png"
    make_atlas(entries).save(raw)
    make_guide(entries, folder / "font_guide.png")
    manifest = {
        "format": "AW raw font atlas v1", "rom": rom_path.name,
        "rom_sha1": sha1(rom), "image": raw.name,
        "cell": [CELL_W, CELL_H], "columns": COLS,
        "characters": [{"index": i, "char": e["char"], "code": e["code"], "width": e["width"]}
                       for i, e in enumerate(entries)],
    }
    (folder / "font_map.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(f"Exported {len(entries)} glyphs: {raw} ({raw.stat().st_size} bytes)")
    print(f"Position guide: {folder / 'font_guide.png'}")


def read_edits(rom: bytes, folder: Path) -> tuple[list[dict], dict[int, bytes]]:
    manifest = json.loads((folder / "font_map.json").read_text(encoding="utf-8"))
    if manifest.get("format") != "AW raw font atlas v1" or sha1(rom) != manifest.get("rom_sha1"):
        raise ValueError("Font map belongs to a different ROM; export again from this ROM")
    entries = font_entries(rom)
    expected = [{"index": i, "char": e["char"], "code": e["code"], "width": e["width"]}
                for i, e in enumerate(entries)]
    if manifest.get("characters") != expected or manifest.get("cell") != [CELL_W, CELL_H] or manifest.get("columns") != COLS:
        raise ValueError("Font map does not match the active ROM font")
    image_path = folder / "font_raw.png"
    with Image.open(image_path) as source:
        image = source.convert("RGBA")
    if image.size != atlas_size(len(entries)):
        raise ValueError(f"Raw PNG must be {atlas_size(len(entries))}, got {image.size}")
    pixels = image.load()
    edits = {}
    for i, entry in enumerate(entries):
        ox, oy = (i % COLS) * CELL_W, (i // COLS) * CELL_H
        bitmap = bytearray(CELL_H)
        for y in range(CELL_H):
            for x in range(CELL_W):
                color = pixels[ox + x, oy + y]
                if color not in ((0, 0, 0, 255), (255, 255, 255, 255)):
                    raise ValueError(f"Only opaque black/white allowed: pixel ({ox+x}, {oy+y}) = {color}")
                if color[0] == 0:
                    if x >= entry["width"]:
                        raise ValueError(f'{entry["char"]}: pixel outside original width {entry["width"]}')
                    bitmap[y] |= 0x80 >> x
        if bytes(bitmap) != entry["bitmap"]:
            edits[i] = bytes(bitmap)
    # The unused final atlas cells must stay white.
    for i in range(len(entries), (len(entries) + COLS - 1) // COLS * COLS):
        ox, oy = (i % COLS) * CELL_W, (i // COLS) * CELL_H
        for y in range(CELL_H):
            for x in range(CELL_W):
                if pixels[ox + x, oy + y] != (255, 255, 255, 255):
                    raise ValueError("Unused atlas cells must remain white")
    return entries, edits


def import_edits(rom_path: Path, folder: Path, output: Path, check_only: bool) -> None:
    rom = rom_path.read_bytes()
    entries, edits = read_edits(rom, folder)
    changed = ", ".join(
        f'U+{ord(entries[i]["char"]):04X}({entries[i]["code"]})' for i in edits
    )
    print(f"Changed glyphs: {len(edits)} " + changed)
    if check_only:
        return
    if not edits:
        raise ValueError("No edited pixels found; ROM was not written")
    if output.resolve() == rom_path.resolve():
        raise ValueError("Output must differ from the source ROM")
    out = bytearray(rom)
    allowed = set()
    for i, bitmap in edits.items():
        entry = entries[i]
        width, address, bank_at = entry["width"], entry["address"], entry["bank_address"]
        packed = bytearray()
        for row in bitmap:
            for x in range(0, width, 2):
                packed.append((10 if row & (0x80 >> x) else 0) |
                              ((10 if x + 1 < width and row & (0x80 >> (x + 1)) else 0) << 4))
        out[address:address + len(packed)] = packed
        out[bank_at:bank_at + 16] = bitmap
        allowed.update(range(address, address + len(packed)))
        allowed.update(range(bank_at, bank_at + 16))
    for offset, (before, after) in enumerate(zip(rom, out, strict=True)):
        if before != after and offset not in allowed:
            raise ValueError(f"Unexpected non-font change at 0x{offset:06X}")
    for i, bitmap in edits.items():
        actual, width = decode(out, int(entries[i]["code"], 16))
        if actual != bitmap or width != entries[i]["width"]:
            raise ValueError(f'ROM round trip failed for {entries[i]["char"]}')
    output.write_bytes(out)
    print(f"Wrote {output} | SHA-1 {sha1(out)}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("export", "check", "import"))
    parser.add_argument("--rom", type=Path, default=DEFAULT_ROM)
    parser.add_argument("--dir", type=Path, default=DEFAULT_DIR)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    if args.action == "export":
        export(args.rom, args.dir)
    else:
        import_edits(args.rom, args.dir, args.output, args.action == "check")


if __name__ == "__main__":
    main()
