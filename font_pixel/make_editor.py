"""Package an offline pixel editor, using the exact validated pixel masters."""
import json
from build_font import HERE, SOURCE, decode, load


def main():
    doc = load()
    source = SOURCE.read_bytes()
    mapping = {char: int(entry['code'], 16) for char, entry in doc['glyphs'].items()}
    used = set(mapping.values())
    mapping.update({chr(code): code for code in range(32, 127) if code not in used})
    old = {}
    for char, code in mapping.items():
        bitmap, width = decode(source, code)
        old[char] = {'width': width, 'pixels': [
            ''.join('B' if row & (0x80 >> x) else '.' for x in range(8)) for row in bitmap]}
    # JSON is embedded as text, with '<' escaped to keep script tags inert.
    def inline(obj):
        return json.dumps(obj, ensure_ascii=False).replace('<', '\\u003c')
    html = (HERE / 'editor.template.html').read_text(encoding='utf-8')
    html = html.replace('__FONT_DATA__', inline(doc)).replace('__OLD_DATA__', inline(old))
    (HERE / 'editor.html').write_text(html, encoding='utf-8')
    print('PASS: self-contained editor.html with 186 editable letters')


if __name__ == '__main__':
    main()
