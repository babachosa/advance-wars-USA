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

# Verified strings missed by the general NUL scanner: short dialogue, labels
# preceded by display commands, and the two choices in one fixed-width field.
# Keep exact source bytes here so a changed layout cannot silently corrupt ROM.
SUPPLEMENTAL_TEXT = {
    0x082704: b"BLACK",
    0x08273C: b"COM",
    0x280B2A: b"Intel",
    0x280B3A: b"End",
    0x282CA0: b"B Cptr",
    0x282CA8: b"T Cptr",
    0x2E9F14: b"   Yes     No",
    0x2EA284: b"Lost",
    0x2EC710: b"A rich, green plain.\x0dEasy to traverse,\x0dbut offers little\x0ddefensive cover.",
    0x2F13A8: b"The war starts here! So,\x0d\x15, are you ready?",
    0x3B7F94: b"\x0cSomething's wrong with the link.\x0dPress START to reset.\x0f",
    0x2F62D0: b"Ha, ha, ha, ha, ha!\x0f",
    0x2FB6E4: b"Well, I... Uhm...\x0f",
    0x2FCA9C: b"Hmm...\x0f",
    0x2FCBAC: b"But, but...\x0f",
    0x2FCCA8: b"Hmm... ",
    0x2FDAC0: b"I'm... so... groggy...\x0f",
    0x2FFD6C: b"But I...\x0f",
    0x30208C: b"But I...\x0f",
    0x30438C: b"But I...\x0f",
    0x3075DC: b"Yes!!! I won!",
    # A separate multiplayer client payload near the end of the ROM.
    0x3D8ED8: b"End", 0x3D8EDC: b"Options",
    0x3D8EE4: b"Yield", 0x3D8EEC: b"Wait",
    0x3D8EF4: b"Join", 0x3D8EFC: b"Fire",
    0x3D923C: b"WAIT", 0x3D9264: b"NOT CONNECTED",
    0x3D9274: b"READY", 0x3D927C: b"ERROR",
    0x3D9284: b"CONNECTED", 0x3D9290: b"MASTER",
    0x3D92F8: b"PRESS START", 0x3D9304: b"ENTRY WAIT",
    0x3F3604: b"   yes      no",
    0x3F609C: b"The Orange Star Army has lost!\x0e\x0e",
    0x3F60C0: b"The Blue Moon Army has lost!\x0e\x0e",
    0x3F60E0: b"The Green Earth Army has lost!\x0e\x0e",
    0x3F6104: b"The Yellow Comet Army has lost!\x0e\x0e",
    0x3F6264: b"If you yield, you lose.\x0dDo you really yield?\x0e\x18",
    0x3F6A8C: (b"The\x1aAlara\x1aregion\x1ais\x1aquite\x1aremote.\x0f"
               b"This\x1ais\x1awhy\x1aOlaf\x1ahasn't\x1adeployed\x0d"
               b"many\x1atroops\x1ato\x1athe\x1aarea.\x0f"
               b"You\x1ayourself\x1ahave\x1atwo\x1a\x82infantry\x80\x1aunits\x0d"
               b"under\x1ayour\x1acommand.\x0f"),
}
SUPPLEMENTAL_TEXT.update({
    offset: label.encode("ascii") for offset, label in {
        0x28B552: "Unit", 0x28B55A: "Intel", 0x28B562: "Power",
        0x28B56A: "Save", 0x28B572: "Options", 0x28B57E: "End",
        0x28B586: "Terms", 0x28B58E: "Status", 0x28B59A: "CO",
        0x28B5A2: "Rules", 0x28B5AA: "Music On",
        0x28B5B6: "Music Off", 0x28B5C2: "Visual A",
        0x28B5CE: "Visual B", 0x28B5DA: "Visual C",
        0x28B5E6: "No Visual", 0x28B5F2: "Delete",
        0x28B5FE: "Yield", 0x28B604: "Exit Map",
        0x28B612: "Victory", 0x28B61E: "Climate",
        0x28B62A: "Fire", 0x28B632: "Fire",
        0x28B63A: "Capt", 0x28B642: "Capt",
        0x28B64E: "Load", 0x28B656: "Drop",
        0x28B65E: "Drop", 0x28B666: "Join",
        0x28B66E: "Supply", 0x28B67A: "Wait",
        0x28B682: "Dive", 0x28B68A: "Rise",
    }.items()
})
SUPPLEMENTAL_TEXT.update({
    offset: value.encode("latin-1") + b"\x0f" for offset, value in {
        0x2BC74C: "Um... No, I don't.",
        0x2BCC88: "Well, um...", 0x2BE1C0: "Um...",
        0x2BE8C0: "Grrr... I... I lost again...",
        0x2BF494: "Oooh...you...", 0x2C0608: "Yeah... Sure...",
        0x2C079C: "Oh, I...", 0x2C0CC0: "I... I lost to...a girl?",
        0x2C0DC8: "Oh, OK...", 0x2C1114: "Rrr...",
        0x2C1228: "Oh, OK...", 0x2C14D8: "Oh, OK...",
        0x2C29D0: "But... But... Sonja, I...",
        0x2C2AE8: "Well, I...", 0x2C2B60: "Um...",
        0x2C2EEC: "Wha...?", 0x2C34D4: "Oh...",
        0x2C39A4: "(sigh)...", 0x2C4470: "Um...",
        0x2C8C04: "Hmm.", 0x2C9FF8: "Bu...but...",
    }.items()
})

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
TOKEN_TO_BYTE["1A"] = 0x1A  # word separator in the multiplayer payload
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
    existing = {offset for offset, _ in entries}
    for offset, raw in SUPPLEMENTAL_TEXT.items():
        if data[offset:offset + len(raw)] != raw:
            raise ToolError(f"Chuoi bo sung khong khop ROM tai {offset:06X}")
        if offset in existing:
            raise ToolError(f"Chuoi bo sung bi trung tai {offset:06X}")
        entries.append((offset, raw))
    return sorted(entries)


def display(raw: bytes) -> str:
    parts = []
    for byte in raw:
        if byte == 0x1A:
            parts.append("{1A}")
        elif byte in CONTROLS:
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
