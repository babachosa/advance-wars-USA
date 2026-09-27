"""Apply hand-written translations to the exported CSV and verify each edit."""

import csv
import json
from pathlib import Path

import aw_vi_tool as tool

ROOT = Path(__file__).resolve().parent
TITLES = json.loads((ROOT / "manual_translations.json").read_text(encoding="utf-8"))
OFFSETS = {}
for path in [ROOT / "manual_offsets.json", *sorted(ROOT.glob("manual_offsets_*.json"))]:
    data = json.loads(path.read_text(encoding="utf-8"))
    overlap = OFFSETS.keys() & data.keys()
    if overlap:
        raise RuntimeError(f"Duplicate offsets in {path}: {sorted(overlap)}")
    OFFSETS.update(data)

rows = list(csv.DictReader(tool.DEFAULT_CSV.open(encoding="utf-8-sig", newline="")))
used_offsets = set()
known_by_english = {}

def title_translation(source):
    if source in TITLES:
        return TITLES[source]
    for prefix in ("{09}{81}", "{09}{NORMAL}", "{09}{COMMAND}", "{09}{UNIT}"):
        if source.startswith(prefix) and source[len(prefix):] in TITLES:
            return prefix + TITLES[source[len(prefix):]]
    return None

for row in rows:
    value = OFFSETS.get(row["offset"])
    if value is not None:
        used_offsets.add(row["offset"])
    else:
        value = title_translation(row["english"])
    if value is None:
        value = known_by_english.get(row["english"])
    if value is None:
        continue
    tool.validate_translation(bytes.fromhex(row["original_hex"]),
                              tool.parse_translation(value), int(row["offset"], 16))
    row["vietnamese"] = value
    known_by_english[row["english"]] = value

# Some duplicate English strings appear earlier than the manually translated
# occurrence. Fill them on the second pass, without replacing any unique edit.
for row in rows:
    if row["vietnamese"]:
        continue
    value = known_by_english.get(row["english"])
    if value:
        try:
            tool.validate_translation(bytes.fromhex(row["original_hex"]),
                                      tool.parse_translation(value), int(row["offset"], 16))
        except tool.ToolError:
            continue
        row["vietnamese"] = value

missing = OFFSETS.keys() - used_offsets
if missing:
    raise RuntimeError(f"Unknown offsets: {sorted(missing)}")

with tool.DEFAULT_CSV.open("w", encoding="utf-8-sig", newline="") as file:
    writer = csv.DictWriter(file, fieldnames=tool.CSV_FIELDS)
    writer.writeheader()
    writer.writerows(rows)
print(f"Translated: {sum(bool(row['vietnamese']) for row in rows)}/{len(rows)}")
