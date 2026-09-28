"""Transfer only diacritics from model suggestions into the original CSV."""

from __future__ import annotations

import csv
import difflib
import json
import re
import unicodedata
from collections import Counter
from pathlib import Path

import aw_vi_tool
from build_full_accent_rom import ACCENTED_CSV, ORIGINAL_CSV, strip_accents
from restore_viet_model import BREAK_RE, PREDICTIONS, TOKEN_RE

BASE = Path(__file__).resolve().parent
REVIEW = BASE / "viet_accent_review.csv"
WORD_RE = re.compile(r"[A-Za-zÀ-ỿĐđ]+")
PROTECTED = {
    "advance", "wars", "andy", "sami", "nell", "max", "grit", "olaf",
    "sonja", "eagle", "drake", "jess", "kanbei", "sturm", "hachi",
    "orange", "star", "blue", "moon", "green", "earth", "yellow", "comet",
    "apc", "hq", "hp", "vs", "map", "start", "select", "com", "cpu",
}
OVERRIDES = {
    "2EFD10": ("Mung den Advance Wars!", "Mừng đến Advance Wars!"),
    "2F1D9C": ("Chao mung den Ban Do Chien Dau.",
               "Chào mừng đến Bản Đồ Chiến Đấu."),
}
UI_OVERRIDES = {
    "081294": "Vịnh quỷ", "082460": "{09}{81}Vịnh quỷ",
    "0818A4": "TUYT:%s", "082264": "{09}{UNIT}Bản ĐặcBiệt",
    "08271C": "LAM", "0828C4": "SAO MAY",
    "282C50": "TăngVừa", "282C90": "Chiếncơ",
    "28B55A": "Tin", "28B62A": "Bắn", "28B632": "Bắn",
    "28B656": "Thả", "28B65E": "Thả", "28B66E": "TiếpTế",
    "28B682": "Lặn", "3D8EFC": "Bắn",
    "080D44": "Bản11", "080D4C": "Bản10",
    "2EA298": "Thủ", "2F9980": "Trúng!", "3D8CB8": "RỖNG",
    "3B7F84": "Xin chờ.", "28B58E": "Trạng",
    "28B5CE": "Cảnh B", "28B5DA": "Cảnh C", "2F721C": "Ngố.",
    "2BE930": "Dạ.{PAGE}", "2BFFB8": "Dạ.{PAGE}",
    "2BEF20": "Dạ.{PAGE}",
    "0816EC": "TRỐNG", "081884": "TẮT", "0818EC": "DỪNG",
    "081904": "PHE CAM THẮNG", "081914": "PHE LAM THẮNG",
    "08193C": "CHIẾM THỦ ĐÔ", "08194C": "X CHIẾM",
    "081958": "TỬ CHIẾN", "081A60": "LƯỢT TIẾP", "081A6C": "NHẤN NÚT A",
    "0826E8": "TẮT", "08270C": "VÀNG", "082714": "LỤC", "082724": "ĐỎ",
    "082740": "NGƯỜI", "0827D8": "CHUẨN", "0827E0": "LƯỢNG   /",
    "0827EC": "CHƠI", "0827F4": "TIỀN", "0827FC": "NGHỈ",
    "082804": "ĐỘI", "08280C": "CHỈHUY", "082814": "DÒ XA",
    "082820": "XẾP", "082828": "MÀU", "082834": "THIÊN THẠCH",
    "082844": "SÓNG TO", "08284C": "SẤM SÉT TẤN CÔNG",
    "082860": "TẦM NHÌN XA", "082870": "TĂNG SĨ KHÍ",
    "082880": "BẮN TỈA XA", "082890": "DI CHUYỂN 2",
    "08289C": "BÃO TUYT", "0828A8": "SỨC MẠNH",
    "0828B4": "SỬA TỐI ĐA", "082704": "ĐEN", "08273C": "MÁY",
    "3D923C": "CHỜ", "3D9264": "CHƯA KẾT NỐI", "3D927C": "LỖI",
    "3D9284": "ĐÃ NỐI", "3D9290": "CHỦ", "3D92F8": "NHẤN START",
    "3D9304": "CHỜ VÀO",
}

# The model has no knowledge of Advance Wars' control tags. Their contents
# have a single meaning throughout the game, so restore them deterministically.
TAG_TERMS = {
    "COMMAND": {
        "ban": "Bắn", "ban.": "Bắn.", "chiem": "Chiếm", "cho": "Chờ",
        "danh": "Đánh", "don vi": "Đơn vị", "lan": "Lặn",
        "quan con lai": "Quân còn lại", "tha": "Thả",
        "tha xuong": "Thả xuống", "trang thai": "Trạng thái",
    },
    "UNIT": {
        "ban": "Bắn", "co gioi": "cơ giới", "hoa tien": "hỏa tiễn",
        "phong khong": "phòng không", "quan co gioi": "quân cơ giới",
        "tang lon": "tăng lớn", "tau do bo": "tàu đổ bộ",
        "tau ngam": "tàu ngầm", "truc thang cho quan": "trực thăng chở quân",
    },
}
TAG_RE = re.compile(r"\{(COMMAND|UNIT)\}([^{}]+)\{NORMAL\}")
PHRASE_FIXES = {
    "Gió hay": "Giờ hãy",
    "gió hay": "giờ hãy",
    "sợ chỉ huy": "sở chỉ huy",
    "Sợ chỉ huy": "Sở chỉ huy",
    "da đen": "đã đến",
    "tối đến": "tôi đến",
    "bàn thắng": "bạn thắng",
    "Bàn thắng": "Bạn thắng",
    "Bán qua màn": "Bạn qua màn",
    "Bán quả mận": "Bạn qua màn",
    "bán lại gần": "bạn lại gần",
    "bán càng ít": "bạn càng ít",
    "bán đang có": "bạn đang có",
    "bán dùng bộ binh": "bạn dùng bộ binh",
    "bán tự xử lý": "bạn tự xử lý",
    "bán được giao": "bạn được giao",
    "Hiếu chú": "Hiểu chứ",
    "Không để vay đau": "Không dễ vậy đâu",
    "về cang?": "về cảng?",
    "quá đáng nhi?": "quá đáng nhỉ?",
    "bất han nơi": "bắt hắn nói",
    "hạn cứ đuổi": "hắn cứ đuổi",
    "Nó đầu thế": "Nó đâu thể",
    "nhoc mạ": "nhóc mà",
    "Dung tiu nghiu": "Đừng tiu nghỉu",
    "Bắt ON": "Bật ON",
    "Sao a?": "Sao ạ?",
    "Ha?": "Hả?",
    "Gi?": "Gì?",
    "May qua!": "May quá!",
    "Thay sao?": "Thấy sao?",
    "Chao Eagle.": "Chào Eagle.",
}


def domain_corrections(candidate: str, original: str) -> str:
    def fix_tag(match: re.Match[str]) -> str:
        kind, value = match.group(1), match.group(2)
        key = strip_accents(value).lower()
        replacement = TAG_TERMS[kind].get(key)
        if replacement is None:
            return match.group()
        original_value = TAG_RE.match(original, match.start()).group(2)
        if original_value.isupper():
            replacement = replacement.upper()
        elif original_value[0].islower():
            replacement = replacement[0].lower() + replacement[1:]
        else:
            replacement = replacement[0].upper() + replacement[1:]
        return "{" + kind + "}" + replacement + "{NORMAL}"

    candidate = TAG_RE.sub(fix_tag, candidate)
    # Game dialogue uses quân for troops; quận and quần are model homophones.
    candidate = re.sub(r"\b(q[u]ận|q[u]ần|quan)\b", "quân", candidate)
    candidate = re.sub(r"\b(Q[u]ận|Q[u]ần|Quan)\b", "Quân", candidate)
    candidate = re.sub(r"\b[Hh]oa tiên\b", lambda m: "Hỏa tiễn" if m.group()[0].isupper() else "hỏa tiễn", candidate)
    candidate = re.sub(r"\b([Mm])ạn\b", lambda m: m.group(1) + "àn", candidate)
    candidate = re.sub(r"\b([Hh])iếu không\b", lambda m: m.group(1) + "iểu không", candidate)
    # Enemy is địch except in the fixed phrase chiến dịch.
    candidate = re.sub(r"\b([Dd])ịch\b", lambda m: ("Đ" if m.group(1) == "D" else "đ") + "ịch", candidate)
    candidate = re.sub(r"\b([Cc])hiến địch\b", lambda m: m.group(1) + "hiến dịch", candidate)
    for wrong, right in PHRASE_FIXES.items():
        candidate = candidate.replace(wrong, right)
    return candidate


def predictions() -> dict[str, str]:
    result = {}
    for line in PREDICTIONS.read_text(encoding="utf-8").splitlines():
        item = json.loads(line)
        result[item["source"]] = item["prediction"]
    return result


def model_input(page: str) -> str:
    return " ".join(TOKEN_RE.sub(" ", page).split())


def recase(old: str, suggestion: str) -> str:
    candidate = unicodedata.normalize("NFC", suggestion)
    if old.isupper():
        candidate = candidate.upper()
    elif old[0].isupper():
        candidate = candidate[0].upper() + candidate[1:].lower()
    else:
        candidate = candidate.lower()
    return candidate


def accent_page(page: str, prediction: str) -> tuple[str, int, int, bool]:
    masked = TOKEN_RE.sub(lambda match: " " * len(match.group()), page)
    old_words = list(WORD_RE.finditer(masked))
    new_words = list(WORD_RE.finditer(prediction))
    old_keys = [match.group().lower() for match in old_words]
    new_keys = [strip_accents(match.group()).lower() for match in new_words]
    pairs = []
    for block in difflib.SequenceMatcher(None, old_keys, new_keys, autojunk=False).get_matching_blocks():
        pairs.extend((block.a + i, block.b + i) for i in range(block.size))
    replacements = {}
    for old_index, new_index in pairs:
        old_match = old_words[old_index]
        old_word = old_match.group()
        if old_word == "CO" or old_word.lower() in PROTECTED:
            continue
        candidate = recase(old_word, new_words[new_index].group())
        if strip_accents(candidate) == old_word:
            replacements[old_match.start()] = (old_match.end(), candidate)
    result = []
    cursor = 0
    changed = 0
    for start, (end, candidate) in sorted(replacements.items()):
        result.append(page[cursor:start])
        result.append(candidate)
        if candidate != page[start:end]:
            changed += 1
        cursor = end
    result.append(page[cursor:])
    accented = "".join(result)
    if strip_accents(accented) != page:
        raise ValueError("Model transfer changed text beyond diacritics")
    return accented, changed, len(old_words), len(pairs) == len(old_words)


def main() -> None:
    with ORIGINAL_CSV.open("r", encoding="utf-8-sig", newline="") as file:
        rows = list(csv.DictReader(file))
    suggestions = predictions()
    output = []
    review = []
    counts = Counter()
    for row in rows:
        value = row["vietnamese"]
        if not value or value == row["english"]:
            output.append(row.copy())
            continue
        chunks = re.split(f"({BREAK_RE.pattern})", value)
        rebuilt = []
        for chunk in chunks:
            if BREAK_RE.fullmatch(chunk):
                rebuilt.append(chunk)
                continue
            plain = model_input(chunk)
            prediction = suggestions.get(plain)
            if not plain or prediction is None:
                rebuilt.append(chunk)
                if plain and re.search("[AEIOUYaeiouy]", plain):
                    counts["missing_predictions"] += 1
                continue
            accented, changed, words, aligned = accent_page(chunk, prediction)
            rebuilt.append(accented)
            counts["words"] += words
            counts["changed_words"] += changed
            if not aligned:
                counts["unaligned_pages"] += 1
                review.append((row["offset"], plain, prediction, "model word mismatch"))
        candidate = "".join(rebuilt)
        candidate = domain_corrections(candidate, value)
        if row["offset"] in UI_OVERRIDES:
            candidate = UI_OVERRIDES[row["offset"]]
        if row["offset"] in OVERRIDES:
            before, after = OVERRIDES[row["offset"]]
            if candidate.count(before) == 1:
                candidate = candidate.replace(before, after, 1)
            elif strip_accents(candidate).count(before) != 1:
                raise ValueError(f"Override source missing at {row['offset']}")
            else:
                # Other accents may already be present in this phrase; replace
                # exactly the span while keeping all remaining text unchanged.
                pos = strip_accents(candidate).index(before)
                candidate = candidate[:pos] + after + candidate[pos + len(before):]
        if strip_accents(candidate) != value:
            raise ValueError(f"Accent-only invariant failed at {row['offset']}: {candidate!r} vs {value!r}")
        updated = row.copy()
        updated["vietnamese"] = candidate
        output.append(updated)
    with ACCENTED_CSV.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=aw_vi_tool.CSV_FIELDS)
        writer.writeheader()
        writer.writerows(output)
    with REVIEW.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.writer(file)
        writer.writerow(("offset", "source", "prediction", "reason"))
        writer.writerows(review)
    print(dict(counts))
    print(f"accented rows: {sum(a['vietnamese'] != b['vietnamese'] for a, b in zip(rows, output))}")


if __name__ == "__main__":
    main()
