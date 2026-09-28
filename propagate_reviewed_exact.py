"""Copy decisions only when source English and original Vietnamese are exact duplicates."""

import csv
from collections import defaultdict
from pathlib import Path

from build_full_accent_rom import rows_from
from full_review_ledger import FIELDS, LEDGER, SOURCE, read_ledger

source = {r["offset"]: r for r in rows_from(SOURCE)}
rows = read_ledger()
approved = defaultdict(list)
for row in rows:
    if row["status"] in {"approved", "revised"}:
        key = (row["english"], source[row["offset"]]["vietnamese"])
        approved[key].append(row)

count = 0
for row in rows:
    if row["status"] != "pending":
        continue
    key = (row["english"], source[row["offset"]]["vietnamese"])
    matches = approved.get(key, [])
    if matches and len({x["vietnamese"] for x in matches}) == 1:
        exemplar = matches[0]
        row["vietnamese"] = exemplar["vietnamese"]
        row["status"] = exemplar["status"]
        row["note"] = f"Trùng nguyên văn Anh–Việt với {exemplar['offset']}; đã đối chiếu."
        count += 1

with LEDGER.open("w", encoding="utf-8-sig", newline="") as file:
    writer = csv.DictWriter(file, fieldnames=FIELDS)
    writer.writeheader()
    writer.writerows(rows)
print(f"Propagated {count} exact duplicates")
