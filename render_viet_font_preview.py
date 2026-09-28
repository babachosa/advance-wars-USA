"""Render the manually authored bitmap rows for visual inspection only."""

from pathlib import Path

from PIL import Image, ImageDraw

import viet_font_bank

BASE = Path(__file__).resolve().parent
OUTPUT = BASE / "viet_font_preview.png"
COLUMNS = 12
TILE_W, TILE_H = 72, 92
SCALE = 4


def main() -> None:
    glyphs = viet_font_bank.glyphs()
    rows = (len(glyphs) + COLUMNS - 1) // COLUMNS
    image = Image.new("RGB", (COLUMNS * TILE_W, rows * TILE_H), (225, 225, 225))
    draw = ImageDraw.Draw(image)
    for index, (char, bitmap) in enumerate(glyphs.items()):
        x = (index % COLUMNS) * TILE_W
        y = (index // COLUMNS) * TILE_H
        draw.rectangle((x, y, x + TILE_W - 1, y + TILE_H - 1), outline=(155, 155, 155))
        draw.text((x + 2, y + 2), f"U+{ord(char):04X}", fill=(25, 25, 25))
        for py, bits in enumerate(bitmap):
            for px in range(8):
                if bits & (0x80 >> px):
                    left = x + 3 + px * SCALE
                    top = y + 17 + py * SCALE
                    draw.rectangle((left, top, left + SCALE - 1, top + SCALE - 1), fill=(0, 0, 0))
        draw.line((x + 2, y + 17 + 14 * SCALE, x + TILE_W - 3, y + 17 + 14 * SCALE),
                  fill=(230, 70, 70))
    image.save(OUTPUT)
    print(f"PASS: preview of {len(glyphs)} hand-drawn glyphs")


if __name__ == "__main__":
    main()
