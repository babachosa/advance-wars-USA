"""Carry reviewed map names into duplicate prefixed menu entries."""

from __future__ import annotations

import csv
from pathlib import Path

from full_review_ledger import FIELDS, LEDGER, read_ledger

PREFIX = "{09}{81}"


def main() -> None:
    rows = read_ledger()
    by_english = {row["english"]: row for row in rows
                  if row["status"] in {"approved", "revised"}
                  and not row["english"].startswith("{")}
    count = 0
    for row in rows:
        if row["status"] != "pending" or not row["english"].startswith(PREFIX):
            continue
        base = by_english.get(row["english"][len(PREFIX):])
        if base is None:
            continue
        target = PREFIX + base["vietnamese"]
        row["status"] = "approved" if target == row["vietnamese"] else "revised"
        row["vietnamese"] = target
        row["note"] = f"Cùng tên màn đã rà tại {base['offset']}"
        count += 1
    with LEDGER.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    print(f"Propagated {count} duplicate map names")


if __name__ == "__main__":
    main()
