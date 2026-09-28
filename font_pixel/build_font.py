"""Compile explicit pixel masters into a new ROM; verify every changed byte.

No rasterizer, resampling, or automatic mark placement in this build path.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import struct
import unicodedata as ud

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
SOURCE = ROOT / 'Advance Wars (Vietnamese) Full Context Final.gba'
OUTPUT = ROOT / 'Advance Wars (Vietnamese) Pixel Font.gba'
SOURCE_SHA1 = '36b603d4513fcbad3a486e8a22d37f1300c22031'
TABLE, WIDTHS, BANK, HEADER, DATA = 0x3F9020, 0x3F9420, 0x3F8000, 0x3F9000, 0x3FB900
ROM_BASE = 0x08000000


def sha(data):
    return hashlib.sha1(data).hexdigest()


def load(path=HERE / 'glyphs.json'):
    doc = json.loads(path.read_text(encoding='utf-8'))
    if doc['cell'] != [8, 16] or doc['format'] != 'AW pixel master v2':
        raise ValueError('Unsupported pixel master format')
    return doc


def rows(entry):
    return bytes(sum(0x80 >> x for x, pixel in enumerate(row) if pixel != '.')
                 for row in entry['pixels'])


def decode(rom, code):
    width = rom[WIDTHS + code]
    address = struct.unpack_from('<I', rom, TABLE + code * 4)[0] - ROM_BASE
    if not 1 <= width <= 8 or not 0 <= address <= len(rom) - 16 * ((width + 1) // 2):
        raise ValueError(f'Invalid glyph pointer/width for {code:02X}')
    result = []
    for y in range(16):
        bits = 0
        for x in range(width):
            value = (rom[address + y * ((width + 1) // 2) + x // 2] >> (x % 2 * 4)) & 15
            if value:
                bits |= 0x80 >> x
        result.append(bits)
    return bytes(result), width


def points(entry, layers):
    return {(x, y) for y, row in enumerate(entry['pixels']) for x, p in enumerate(row) if p in layers}


def distance(a, b):
    return min(max(abs(x - xx), abs(y - yy)) for x, y in a for xx, yy in b)


def verify_master(doc, source):
    mapping = json.loads((ROOT / 'viet_font_mapping.json').read_text(encoding='utf-8'))['character_to_byte']
    expected = {**{chr(c): f'{c:02X}' for c in range(65, 91)},
                **{chr(c): f'{c:02X}' for c in range(97, 123)}, **mapping}
    glyphs = doc['glyphs']
    if set(glyphs) != set(expected):
        raise ValueError('Expected the same 186 characters as the original font bank')
    metrics = {}
    seen = {}
    for char, entry in glyphs.items():
        code = int(entry['code'], 16)
        if entry['code'] != expected[char] or entry['width'] != source[WIDTHS + code]:
            raise ValueError(f'{char}: encoding or advance width changed')
        pixels = entry['pixels']
        if len(pixels) != 16 or any(len(row) != 8 or set(row) - set('.BHSTD') for row in pixels):
            raise ValueError(f'{char}: expected 16 explicit rows of eight labeled pixels')
        if any(p != '.' for row in pixels for p in row[entry['width']:]):
            raise ValueError(f'{char}: ink would be clipped by the existing glyph width')
        body = points(entry, 'BH')
        if not body:
            raise ValueError(f'{char}: empty body')
        decomp = ud.normalize('NFD', char)
        required = {'S': any(m in decomp for m in '\u0302\u0306'),
                    'T': any(m in decomp for m in '\u0300\u0301\u0309\u0303'),
                    'D': '\u0323' in decomp}
        gaps = {}
        for layer, needed in required.items():
            mark = points(entry, layer)
            if bool(mark) != needed:
                raise ValueError(f'{char}: wrong {layer} layer presence')
            if mark:
                others = points(entry, 'BHSTD'.replace(layer, ''))
                gap = distance(mark, others) - 1
                if gap < 1:
                    raise ValueError(f'{char}: {layer} touches other ink, including diagonals')
                gaps[layer] = gap
        base = {'đ': 'd', 'Đ': 'D'}.get(decomp[0], decomp[0])
        # Accented vowels must have exactly the same body as plain vowels.
        reference = points(glyphs[base], 'B')
        if base == 'i' and required['T']:
            reference -= {(0, 6)}
        if points(entry, 'B') != reference:
            raise ValueError(f'{char}: vowel/letter body differs from its unaccented master')
        bitmap = rows(entry)
        if bitmap in seen:
            raise ValueError(f'{char} and {seen[bitmap]} have identical bitmaps')
        seen[bitmap] = char
        metrics[char] = {'code': entry['code'], 'width': entry['width'], 'blank_pixel_gaps': gaps}
    return metrics


def compile_rom(doc, source):
    if sha(source) != SOURCE_SHA1 or len(source) != 0x400000:
        raise ValueError('Source is not the verified Full Context Final ROM')
    if source[DATA:] != b'\xff' * (len(source) - DATA):
        raise ValueError('New font destination is not empty')
    metrics = verify_master(doc, source)
    out = bytearray(source)
    allowed = bytearray(len(source))

    def write(offset, data):
        if offset < 0 or offset + len(data) > len(out):
            raise ValueError('Font data exceeds ROM')
        out[offset:offset + len(data)] = data
        allowed[offset:offset + len(data)] = b'\x01' * len(data)

    items = dict(sorted(doc['glyphs'].items(), key=lambda item: ord(item[0])))
    cursor = DATA
    for char, entry in items.items():
        bitmap, width = rows(entry), entry['width']
        packed = bytearray()
        for row in bitmap:
            for x in range(0, width, 2):
                low = 10 if row & (0x80 >> x) else 0
                high = 10 if x + 1 < width and row & (0x80 >> (x + 1)) else 0
                packed.append(low | (high << 4))
        write(cursor, packed)
        write(TABLE + int(entry['code'], 16) * 4, struct.pack('<I', ROM_BASE + cursor))
        cursor += len(packed)
    bank = (struct.pack('<4sBBBBIII', b'AWVF', 2, 8, 16, 1, len(items), 20, 20 + len(items) * 4)
            + b''.join(struct.pack('<I', ord(c)) for c in items)
            + b''.join(rows(e) for e in items.values()))
    if BANK + len(bank) > HEADER:
        raise ValueError('Bitmap bank overlaps active font tables')
    write(BANK, bank)
    write(HEADER, struct.pack('<4sIIIIIII', b'AWVM', 2, len(items),
                             ROM_BASE + TABLE, ROM_BASE + WIDTHS, ROM_BASE + DATA, cursor - DATA, 0))
    # Independent unpack of the active ROM pointers and nibbles.
    for char, entry in items.items():
        actual, width = decode(out, int(entry['code'], 16))
        if actual != rows(entry) or width != entry['width']:
            raise ValueError(f'{char}: ROM pixel round trip failed')
    if source[WIDTHS:WIDTHS + 256] != out[WIDTHS:WIDTHS + 256]:
        raise ValueError('Line metrics changed')
    codes = {int(e['code'], 16) for e in items.values()}
    for code in set(range(256)) - codes:
        if source[TABLE + code * 4:TABLE + code * 4 + 4] != out[TABLE + code * 4:TABLE + code * 4 + 4]:
            raise ValueError('Punctuation/control character pointer changed')
    changed = 0
    for offset, (before, after) in enumerate(zip(source, out, strict=True)):
        if before != after:
            changed += 1
            if not allowed[offset]:
                raise ValueError(f'Non-font byte changed at {offset:06X}')
    report = {'source_rom': SOURCE.name, 'source_sha1': sha(source), 'output_rom': OUTPUT.name,
              'output_sha1': sha(out), 'glyphs': len(items), 'accented_glyphs': 134,
              'glyph_data_start': f'{DATA:06X}', 'glyph_data_end': f'{cursor:06X}',
              'remaining_bytes': len(out) - cursor, 'changed_bytes': changed,
              'unchanged_all_256_widths': True, 'unchanged_text_game_code_and_header': True,
              'decoded_rom_matches_all_pixel_masters': True, 'touching_detached_marks': 0,
              'minimum_blank_pixels_between_detached_marks_and_other_ink': 1,
              'glyph_metrics': metrics}
    return bytes(out), report


def render(doc, old, new):
    from PIL import Image, ImageDraw, ImageFont
    font = ImageFont.truetype('C:/Windows/Fonts/arial.ttf', 14)
    title = ImageFont.truetype('C:/Windows/Fonts/arial.ttf', 22)
    families = []
    for base in 'aăâeêioôơuưy':
        for variant in (base.upper(), base):
            families.append(''.join(ud.normalize('NFC', variant + t) for t in ('', '\u0300', '\u0301', '\u0309', '\u0303', '\u0323')))
    families += ['đĐ', 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz']
    allchars = ''.join(doc['glyphs'])
    scale, cellw, cellh, cols = 4, 74, 98, 12
    atlas = Image.new('RGB', (cols * cellw, 70 + ((len(allchars) + cols - 1) // cols) * cellh), '#f6f3eb')
    draw = ImageDraw.Draw(atlas)
    draw.text((18, 12), '186 glyph • bitmap đọc lại từ ROM mới • phóng ×4', font=title, fill='#18342b')
    def glyph(draw, bitmap, x, y, scale, color='#182722'):
        for yy, bits in enumerate(bitmap):
            for xx in range(8):
                if bits & (0x80 >> xx):
                    draw.rectangle((x + xx * scale, y + yy * scale,
                                    x + (xx + 1) * scale - 1, y + (yy + 1) * scale - 1), fill=color)
    for index, char in enumerate(allchars):
        entry = doc['glyphs'][char]
        x, y = (index % cols) * cellw, 66 + (index // cols) * cellh
        draw.rectangle((x, y, x + cellw - 1, y + cellh - 1), outline='#c9cbbf')
        draw.text((x + 6, y + 3), char + f'  {entry["code"]}', font=font, fill='#56625d')
        glyph(draw, decode(new, int(entry['code'], 16))[0], x + 12, y + 26, scale)
    atlas.save(HERE / 'glyph_atlas.png')
    comparison = Image.new('RGB', (920, 94 + 26 * 90 + 160), '#f6f3eb')
    draw = ImageDraw.Draw(comparison)
    draw.text((20, 14), 'CŨ / MỚI — cùng độ rộng ký tự, cùng chân dòng', font=title, fill='#18342b')
    draw.text((146, 57), 'CŨ', font=font, fill='#77746c')
    draw.text((530, 57), 'MỚI', font=font, fill='#196c50')
    def textline(text, rom, x, y, scale):
        for char in text:
            if char in doc['glyphs']:
                code = int(doc['glyphs'][char]['code'], 16)
            else:
                code = ord(char)
            bitmap, width = decode(rom, code)
            glyph(draw, bitmap, x, y, scale)
            x += (width + 1) * scale
    for i, text in enumerate(families[:24] + ['đĐ', 'ị ỵ ự ệ ặ']):
        y = 90 + i * 90
        draw.line((20, y - 4, 900, y - 4), fill='#d7d7cb')
        draw.text((20, y + 24), text, font=font, fill='#56625d')
        textline(text, old, 146, y, 4)
        textline(text, new, 530, y, 4)
    y = 90 + 26 * 90
    draw.text((20, y), 'Cỡ gốc ×1 và ×3 — pixel lấy từ ROM mới', font=font, fill='#196c50')
    textline('Tiếng Việt: điều quân, chiến đấu, phòng thủ.', new, 20, y + 25, 1)
    textline('Tiếng Việt: điều quân, chiến đấu, phòng thủ.', new, 20, y + 48, 3)
    textline('Ấ Ầ Ẩ Ẫ Ậ   Ắ Ằ Ẳ Ẵ Ặ   Ở Ỡ Ự ỵ', new, 20, y + 100, 3)
    comparison.save(HERE / 'comparison.png')
    crop = Image.new('RGB', (900, 360), '#f6f3eb')
    draw = ImageDraw.Draw(crop)
    draw.text((20, 10), 'Font mới • dấu tách nét • giữ nguyên độ rộng', font=title, fill='#18342b')
    for i, text in enumerate(['Ấ Ầ Ẩ Ẫ Ậ   Ắ Ằ Ẳ Ẵ Ặ', 'ấ ầ ẩ ẫ ậ   ắ ằ ẳ ẵ ặ', 'Ế Ễ Ố Ỗ Ở Ỡ Ự   ế ễ ở ỡ ị ỵ']):
        textline(text, new, 20, 46 + i * 76, 4)
    textline('Tiếng Việt: điều quân, chiến đấu, phòng thủ.', new, 20, 296, 3)
    crop.save(HERE / 'preview.png')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('action', choices=['build', 'check'])
    parser.add_argument('--master', type=Path, default=HERE / 'glyphs.json')
    args = parser.parse_args()
    doc, source = load(args.master), SOURCE.read_bytes()
    result, report = compile_rom(doc, source)
    report_path = HERE / 'verification.json'
    if args.action == 'build':
        OUTPUT.write_bytes(result)
        report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        render(doc, source, OUTPUT.read_bytes())
    else:
        if OUTPUT.read_bytes() != result or json.loads(report_path.read_text(encoding='utf-8')) != report:
            raise ValueError('Output ROM/report differs from deterministic rebuild')
    print(f'PASS: {len(doc["glyphs"])} glyphs; zero touching detached marks; unchanged widths/text; SHA-1 {sha(result)}')


if __name__ == '__main__':
    main()
