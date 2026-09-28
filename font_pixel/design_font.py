"""Authoring recipe. Builds editable, explicit 8x16 pixel masters, never a TTF.

Normal builds read glyphs.json directly; running this deliberately resets it.
Coordinates are zero based. Each letter retains its existing ROM advance.
"""
from pathlib import Path
import json
import struct
import unicodedata as ud

ROOT = Path(__file__).resolve().parent.parent
HERE = Path(__file__).resolve().parent

# Seven hand-picked rows, shared cap line 6 and baseline 12.
CAPS = {
    'A': '..###../.#...#./#.....#/#.....#/#######/#.....#/#.....#',
    'B': '#####./#....#/#....#/#####./#....#/#....#/#####.',
    'C': '.#####./#.....#/#....../#....../#....../#.....#/.#####.',
    'D': '####../#...#./#....#/#....#/#....#/#...#./####..',
    'E': '######/#...../#...../#####./#...../#...../######',
    'F': '######/#...../#...../#####./#...../#...../#.....',
    'G': '.#####./#.....#/#....../#..####/#.....#/#.....#/.#####.',
    'H': '#....#/#....#/#....#/######/#....#/#....#/#....#',
    'I': '#/#/#/#/#/#/#',
    'J': '..####/....#./....#./....#./....#./#...#./.###..',
    'K': '#....#/#...#./#..#../###.../#..#../#...#./#....#',
    'L': '#...../#...../#...../#...../#...../#...../######',
    'M': '#.....#/##...##/#.#.#.#/#..#..#/#.....#/#.....#/#.....#',
    'N': '#....#/##...#/#.#..#/#..#.#/#...##/#....#/#....#',
    'O': '..###../.#...#./#.....#/#.....#/#.....#/.#...#./..###..',
    'P': '#####./#....#/#....#/#####./#...../#...../#.....',
    'Q': '..###../.#...#./#.....#/#.....#/#...#.#/.#...#./..###.#',
    'R': '#####./#....#/#....#/#####./#..#../#...#./#....#',
    'S': '.######/#....../#....../.#####./......#/......#/######.',
    'T': '#######/...#.../...#.../...#.../...#.../...#.../...#...',
    'U': '#.....#/#.....#/#.....#/#.....#/#.....#/#.....#/.#####.',
    'V': '#.....#/#.....#/#.....#/.#...#./.#...#./..#.#../...#...',
    'W': '#.....#/#.....#/#.....#/#..#..#/#.#.#.#/##...##/#.....#',
    'X': '#.....#/.#...#./..#.#../...#.../..#.#../.#...#./#.....#',
    'Y': '#.....#/.#...#./..#.#../...#.../...#.../...#.../...#...',
    'Z': '#######/.....#./....#../...#.../..#..../.#...../#######',
}
# Lowercase bowls are five pixels tall. Ascenders align to the new capitals.
SMALL = {
    'a': (8, '.##../...#./.###./#..#./.####'),
    'b': (6, '#.../#.../###./#..#/#..#/#..#/###.'),
    'c': (8, '.###/#.../#.../#.../.###'),
    'd': (6, '...#./...#./.###./#..#./#..#./#..#./.####'),
    'e': (8, '.##./#..#/####/#.../.###'),
    'f': (6, '..##/.#../###./.#../.#../.#../.#..'),
    'g': (8, '.###/#..#/#..#/.###/...#/...#/.##.'),
    'h': (6, '#.../#.../###./#..#/#..#/#..#/#..#'),
    'i': (8, '#/#/#/#/#'),
    'j': (8, '..#/..#/..#/..#/..#/..#/##.'),
    'k': (6, '#.../#.../#..#/#.#./##../#.#./#..#'),
    'l': (5, '#/#/#/#/#/#/#/#'),
    'm': (8, '##.#./#.#.#/#.#.#/#.#.#/#.#.#'),
    'n': (8, '###./#..#/#..#/#..#/#..#'),
    'o': (8, '.##./#..#/#..#/#..#/.##.'),
    'p': (8, '###./#..#/#..#/#..#/###./#.../#...'),
    'q': (8, '.###/#..#/#..#/#..#/.###/...#/...#'),
    'r': (8, '#.##/##../#.../#.../#...'),
    's': (8, '.###/#.../.##./...#/###.'),
    't': (6, '.#./.#./###/.#./.#./.#./..#'),
    'u': (8, '#..#/#..#/#..#/#..#/.###'),
    'v': (8, '#...#/#...#/#...#/.#.#./..#..'),
    'w': (8, '#...#/#.#.#/#.#.#/#.#.#/.#.#.'),
    'x': (8, '#...#/.#.#./..#../.#.#./#...#'),
    'y': (8, '#..#/#..#/#..#/.###/...#/...#/..##'),
    'z': (8, '#####/...#./..#../.#.../#####'),
}


def main():
    target = HERE / 'glyphs.json'
    if target.exists():
        raise SystemExit('glyphs.json already exists; edit the pixel master directly.')
    rom = (ROOT / 'Advance Wars (Vietnamese) Full Context Final.gba').read_bytes()
    mapping = json.loads((ROOT / 'viet_font_mapping.json').read_text(encoding='utf-8'))['character_to_byte']
    chars = list(CAPS) + list(SMALL) + list(mapping)
    entries = {}
    for char in chars:
        code = int(mapping[char], 16) if char in mapping else ord(char)
        width = rom[0x3F9420 + code]
        pixels = [['.'] * 8 for _ in range(16)]

        def put(pattern, x, y, layer):
            for dy, row in enumerate(pattern.split('/')):
                for dx, ink in enumerate(row):
                    if ink == '#':
                        assert 0 <= x + dx < width and 0 <= y + dy < 16, (char, x, y)
                        assert pixels[y + dy][x + dx] == '.', (char, x + dx, y + dy)
                        pixels[y + dy][x + dx] = layer

        decomp = ud.normalize('NFD', char)
        base = {'đ': 'd', 'Đ': 'D'}.get(decomp[0], decomp[0])
        upper = base.isupper()
        marks = decomp[1:]
        tone = next((m for m in marks if m in '\u0300\u0301\u0309\u0303\u0323'), '')
        shape = next((m for m in marks if m in '\u0302\u0306'), '')
        horn = '\u031b' in marks
        body_y, body = (6, CAPS[base]) if upper else SMALL[base]
        put(body, 0, body_y, 'B')
        if base in 'ij' and not (base == 'i' and tone and tone != '\u0323'):
            put('#', 0 if base == 'i' else 2, 6, 'B')
        if char in 'đĐ':
            # Stroke crosses the ascender/bowl; it is a structural part of đ.
            y = 7 if char == 'đ' else 9
            for x in range(1, 5 if char == 'đ' else 4):
                if pixels[y][x] == '.':
                    pixels[y][x] = 'H'
        if shape:
            pattern = '.#./#.#' if shape == '\u0302' else '#.#/.#.'
            put(pattern, 2 if upper else 0, 3 if upper else 5, 'S')
        if horn:
            # A small joined horn is part of the letter, separate from tone.
            put('#/#', 7 if upper else 5, 5 if upper else 6, 'H')
            hx, hy = (6, 7) if upper else (4, 8)
            if pixels[hy][hx] == '.':
                put('#', hx, hy, 'H')
        if tone == '\u0323':
            # y's descender ends at x=2..3: x=0 leaves a diagonal pixel gap.
            dot_x = 0 if base in 'iIy' else (3 if upper else 1)
            put('#', dot_x, 15, 'D')
        elif tone:
            patterns = {'\u0300': '#./.#', '\u0301': '.#/#.',
                        '\u0309': '##./..#', '\u0303': '.#.#/#.#.'}
            if base in 'iI':
                patterns['\u0309'] = '##/.#'
                patterns['\u0303'] = '#.#/.#.'
            pattern = patterns[tone]
            span = max(map(len, pattern.split('/')))
            body_width = rom[0x3F9420 + ord(base)]
            x = max(0, (body_width - span) // 2)
            y = (0 if upper else 2) if shape else (2 if horn and upper else 3 if upper else 5)
            put(pattern, x, y, 'T')
        entries[char] = {'code': f'{code:02X}', 'width': width,
                         'pixels': [''.join(row) for row in pixels]}
    document = {'format': 'AW pixel master v2', 'cell': [8, 16],
                'legend': {'.': 'transparent', 'B': 'body', 'H': 'horn or crossed stroke',
                           'S': 'circumflex or breve', 'T': 'top tone', 'D': 'dot below'},
                'glyphs': dict(sorted(entries.items(), key=lambda kv: ord(kv[0])))}
    target.write_text(json.dumps(document, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(f'Wrote explicit pixel masters for {len(entries)} letters')


if __name__ == '__main__':
    main()
