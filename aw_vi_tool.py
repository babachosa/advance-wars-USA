#!/usr/bin/env python3
"""Dump and safely rewrite in-place English text in Advance Wars (USA) GBA."""

from __future__ import annotations

import argparse
import csv
import hashlib
import os
from pathlib import Path
import re
import struct
import sys
import tempfile


BASE = Path(__file__).resolve().parent
DEFAULT_ROM = BASE / "Advance Wars (USA).gba"
DEFAULT_CSV = BASE / "advance_wars_en_vi.csv"
DEFAULT_OUTPUT = BASE / "Advance Wars (Vietnamese).gba"
EXPECTED_SHA1 = "d0a0a4cfe9b95ac7118f7ef476f014ca0242eb65"
ROM_SIZE = 4 * 1024 * 1024

# Each range is a verified text area in this exact US ROM. There are tables and
# graphics between them, so a blind whole-ROM ASCII scan is unsafe.
TEXT_RANGES = (
    (0x080D54, 0x082920),  # menu names, map names, labels
    (0x28072C, 0x280B80),  # Design Maps help
    (0x282C3C, 0x282D50),  # unit and weapon names
    (0x28D9C8, 0x29DDC0),  # Field Training
    (0x2BC274, 0x2CA970),  # Campaign dialogue
    (0x2E2564, 0x2E2F70),  # CO power lines
    (0x2E400C, 0x307AE0),  # unit help, profiles, dialogue, ending
    (0x3B7CFC, 0x3B7FBC),  # link and save messages
    (0x3B9DCC, 0x3BA0E0),  # versus settings help
)

NON_TEXT_RANGES = (
    (0x081C00, 0x082230),  # internal/debug labels and test strings
    (0x2F0D30, 0x2F0E9C),  # font character demonstration strings
)

LATIN1_GLYPHS = {
    0xA1, 0xBF, 0xE0, 0xE1, 0xE2, 0xE4, 0xE7, 0xE8, 0xE9,
    0xEA, 0xEB, 0xEC, 0xED, 0xEE, 0xEF, 0xF1, 0xF2, 0xF3,
    0xF4, 0xF6, 0xF9, 0xFA, 0xFB, 0xFC,
}
CONTROL_NAMES = {
    0x0D: "NL", 0x0F: "PAGE", 0x15: "PLAYER",
    0x80: "NORMAL", 0x82: "UNIT", 0x83: "COMMAND",
}
CONTROLS = set(CONTROL_NAMES) | {
    0x09, 0x0B, 0x0C, 0x0E, 0x14, 0x16, 0x17, 0x18, 0x1B, 0x1F, 0x81,
}
ALLOWED_SOURCE = set(range(0x20, 0x7F)) | LATIN1_GLYPHS | CONTROLS
CSV_FIELDS = ("offset", "max_bytes", "original_hex", "english", "vietnamese")
TOKEN_TO_BYTE = {v: k for k, v in CONTROL_NAMES.items()}
TOKEN_TO_BYTE.update({f"{k:02X}": k for k in CONTROLS if k not in CONTROL_NAMES})
TOKEN_RE = re.compile(r"\{([A-Z]+|[0-9A-F]{2})\}")


class ToolError(Exception):
    pass


def load_rom(path: Path) -> bytes:
    data = path.read_bytes()
    digest = hashlib.sha1(data).hexdigest()
    if len(data) != ROM_SIZE or digest != EXPECTED_SHA1:
        raise ToolError(
            f"ROM không đúng bản USA đã kiểm chứng: size={len(data)}, SHA-1={digest}. "
            f"Cần size={ROM_SIZE}, SHA-1={EXPECTED_SHA1}."
        )
    return data


def pointer_targets(data: bytes) -> set[int]:
    targets = set()
    for pos in range(0, len(data) - 3, 4):
        value = struct.unpack_from("<I", data, pos)[0]
        if 0x08000000 <= value < 0x08000000 + len(data):
            targets.add(value - 0x08000000)
    return targets


def looks_like_text(raw: bytes, pointed: bool) -> bool:
    if not raw or any(c not in ALLOWED_SOURCE for c in raw):
        return False
    letters = [c for c in raw if 65 <= c <= 90 or 97 <= c <= 122]
    if len(letters) < 2 or len(raw) > 2048:
        return False
    # Long English text has a vowel. Short pointer-referenced labels may be
    # acronyms such as HQ or CO. These checks reject most graphics/table data.
    vowels = sum(c in b"AEIOUaeiou" for c in letters)
    if len(raw) <= 4:
        return pointed or vowels > 0
    if vowels == 0:
        return False
    visible_length = sum(c >= 0x20 for c in raw)
    if not visible_length or len(letters) / visible_length < 0.55:
        return False
    if not pointed and len(raw) < 8 and b" " not in raw and not raw.isalpha():
        return False
    return True


def extract(data: bytes) -> list[tuple[int, bytes]]:
    targets = pointer_targets(data)
    entries = []
    for start, stop in TEXT_RANGES:
        pos = start
        while pos < stop:
            end = data.find(b"\0", pos, stop)
            if end < 0:
                break
            raw = data[pos:end]
            internal = any(a <= pos < b for a, b in NON_TEXT_RANGES)
            if not internal and looks_like_text(raw, pos in targets):
                entries.append((pos, raw))
            pos = end + 1
    return entries


def display(raw: bytes) -> str:
    parts = []
    for byte in raw:
        if byte in CONTROLS:
            parts.append("{" + CONTROL_NAMES.get(byte, f"{byte:02X}") + "}")
        elif byte in (ord("{"), ord("}")):
            parts.append(f"{{{byte:02X}}}")
        else:
            parts.append(bytes([byte]).decode("latin-1"))
    return "".join(parts)


def parse_translation(value: str) -> bytes:
    result = bytearray()
    pos = 0
    while pos < len(value):
        if value[pos] == "{":
            match = TOKEN_RE.match(value, pos)
            if not match:
                raise ToolError(f"token không hợp lệ gần {value[pos:pos+16]!r}")
            token = match.group(1)
            byte = TOKEN_TO_BYTE.get(token)
            if byte is None:
                byte = int(token, 16)
                if byte not in (ord("{"), ord("}")):
                    raise ToolError(f"token {{{token}}} không được phép thêm")
            result.append(byte)
            pos = match.end()
            continue
        char = value[pos]
        code = ord(char)
        if not (0x20 <= code <= 0x7E) or char == "}":
            raise ToolError(f"chỉ dùng tiếng Việt không dấu/ASCII; ký tự lỗi: {char!r}")
        result.append(code)
        pos += 1
    return bytes(result)


def control_order(raw: bytes) -> list[int]:
    return [c for c in raw if c in CONTROLS]


def line_budgets(raw: bytes) -> list[int]:
    # Preserve the original byte budget of each displayed line/page, not only
    # the total string. This helps avoid UI clipping with narrow text boxes.
    chunks = re.split(b"[\x0d\x0f]", raw)
    return [len(chunk) for chunk in chunks]


def validate_translation(original: bytes, translated: bytes, offset: int) -> None:
    if b"\0" in translated:
        raise ToolError(f"{offset:06X}: bản dịch chứa byte 00")
    if control_order(translated) != control_order(original):
        raise ToolError(f"{offset:06X}: thiếu, thừa hoặc đổi thứ tự token điều khiển")
    if len(translated) > len(original):
        raise ToolError(
            f"{offset:06X}: dài {len(translated)} byte, tối đa {len(original)} byte"
        )
    # The original NUL-terminated slot is the memory safety boundary. Keeping
    # the control sequence preserves page and line breaks; the text within a
    # given line can change length without writing beyond the slot.


def dump(rom_path: Path, csv_path: Path) -> None:
    data = load_rom(rom_path)
    entries = extract(data)
    if not entries:
        raise ToolError("Không tìm thấy text; kiểm tra ROM và vùng text.")
    if csv_path.exists():
        raise ToolError(f"File CSV đã tồn tại: {csv_path}. Hãy đổi tên hoặc di chuyển trước.")
    with csv_path.open("w", newline="", encoding="utf-8-sig") as file:
        writer = csv.DictWriter(file, fieldnames=CSV_FIELDS)
        writer.writeheader()
        for offset, raw in entries:
            writer.writerow({
                "offset": f"{offset:06X}",
                "max_bytes": len(raw),
                "original_hex": raw.hex().upper(),
                "english": display(raw),
                "vietnamese": "",
            })
    print(f"Đã dump {len(entries)} chuỗi vào {csv_path}")


def read_translations(csv_path: Path, data: bytes) -> list[tuple[int, bytes, bytes]]:
    expected = dict(extract(data))
    seen = set()
    edits = []
    errors = []
    with csv_path.open("r", newline="", encoding="utf-8-sig") as file:
        reader = csv.DictReader(file)
        if tuple(reader.fieldnames or ()) != CSV_FIELDS:
            raise ToolError(f"CSV phải có đúng các cột: {', '.join(CSV_FIELDS)}")
        for number, row in enumerate(reader, 2):
            try:
                offset = int(row["offset"], 16)
                if offset in seen:
                    raise ToolError(f"offset trùng: {offset:06X}")
                seen.add(offset)
                original = expected.get(offset)
                if original is None:
                    raise ToolError(f"offset không thuộc danh sách text: {offset:06X}")
                if int(row["max_bytes"]) != len(original):
                    raise ToolError(f"{offset:06X}: max_bytes đã bị sửa")
                if row["original_hex"].upper() != original.hex().upper():
                    raise ToolError(f"{offset:06X}: original_hex không khớp ROM")
                if row["english"] != display(original):
                    raise ToolError(f"{offset:06X}: cột english đã bị sửa")
                value = row["vietnamese"]
                if value is None:
                    raise ToolError(f"{offset:06X}: thiếu cột vietnamese")
                if value == "":
                    continue
                translated = parse_translation(value)
                validate_translation(original, translated, offset)
                edits.append((offset, original, translated))
            except (ToolError, ValueError, TypeError) as exc:
                errors.append(f"Dòng CSV {number}: {exc}")
    if seen != expected.keys():
        missing = sorted(expected.keys() - seen)
        errors.append(f"CSV thiếu {len(missing)} chuỗi; đầu tiên: " + ", ".join(f"{x:06X}" for x in missing[:5]))
    if errors:
        raise ToolError("Có lỗi, chưa ghi ROM:\n" + "\n".join(errors[:30]) +
                        (f"\n... và {len(errors)-30} lỗi nữa" if len(errors) > 30 else ""))
    return edits


def build(rom_path: Path, csv_path: Path, output_path: Path, check_only: bool) -> None:
    data = load_rom(rom_path)
    edits = read_translations(csv_path, data)
    print(f"Hợp lệ: {len(edits)} chuỗi được dịch; {len(extract(data))-len(edits)} chuỗi giữ nguyên.")
    if check_only:
        return
    if output_path.resolve() == rom_path.resolve():
        raise ToolError("Không được ghi đè ROM gốc.")
    if output_path.exists():
        raise ToolError(f"ROM đầu ra đã tồn tại: {output_path}. Hãy đổi tên hoặc di chuyển trước.")
    modified = bytearray(data)
    for offset, original, translated in edits:
        # Rewrite within the original string's bytes only. The existing NUL
        # terminator remains at its exact address; unused bytes become NUL.
        modified[offset:offset + len(original)] = translated.ljust(len(original), b"\0")
    # Validate the exact diff budget before writing any file.
    allowed = set()
    for offset, original, _ in edits:
        allowed.update(range(offset, offset + len(original)))
    diffs = [i for i, (a, b) in enumerate(zip(data, modified)) if a != b]
    if any(i not in allowed for i in diffs) or len(modified) != len(data):
        raise ToolError("Kiểm tra vùng ghi thất bại; chưa tạo ROM.")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    temp_name = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="wb", prefix=".aw_vi_", suffix=".tmp", dir=output_path.parent, delete=False
        ) as file:
            temp_name = file.name
            file.write(modified)
            file.flush()
            os.fsync(file.fileno())
        os.replace(temp_name, output_path)
    finally:
        if temp_name and os.path.exists(temp_name):
            os.unlink(temp_name)
    print(f"Đã tạo ROM: {output_path} ({len(diffs)} byte thay đổi)")


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("dump", "check", "build"))
    parser.add_argument("--rom", type=Path, default=DEFAULT_ROM)
    parser.add_argument("--csv", type=Path, default=DEFAULT_CSV)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    try:
        if args.command == "dump":
            dump(args.rom, args.csv)
        else:
            build(args.rom, args.csv, args.output, check_only=args.command == "check")
    except (ToolError, OSError, csv.Error) as exc:
        print(f"LỖI: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
