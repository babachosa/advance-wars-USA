"""Track a complete English-to-Vietnamese editorial review by ROM offset."""

from __future__ import annotations

import argparse
import csv
import json
from collections import Counter
from pathlib import Path

from build_full_accent_rom import rows_from

BASE = Path(__file__).resolve().parent
SOURCE = BASE / "advance_wars_vi_context_review_4.csv"
LEDGER = BASE / "full_context_review_ledger.csv"
FIELDS = ("offset", "english", "vietnamese", "status", "note")
STATES = {"pending", "approved", "revised", "excluded"}


def read_ledger() -> list[dict[str, str]]:
    with LEDGER.open(encoding="utf-8-sig", newline="") as file:
        reader = csv.DictReader(file)
        if tuple(reader.fieldnames or ()) != FIELDS:
            raise ValueError("Review ledger fields changed")
        return list(reader)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("init", "stats", "batch", "apply", "amend", "check"))
    parser.add_argument("--start", type=int, default=0)
    parser.add_argument("--size", type=int, default=30)
    parser.add_argument("--decisions", type=Path)
    args = parser.parse_args()
    source = rows_from(SOURCE)
    if args.action == "init":
        if LEDGER.exists():
            raise SystemExit("Refusing to overwrite existing review ledger")
        with LEDGER.open("w", encoding="utf-8-sig", newline="") as file:
            writer = csv.DictWriter(file, fieldnames=FIELDS)
            writer.writeheader()
            for row in source:
                writer.writerow({"offset": row["offset"], "english": row["english"],
                                 "vietnamese": row["vietnamese"],
                                 "status": "pending", "note": ""})
        print(f"Initialized {len(source)} pending entries")
        return
    rows = read_ledger()
    if len(rows) != len(source) or len({row["offset"] for row in rows}) != len(rows):
        raise ValueError("Review ledger has missing or duplicate rows")
    by_offset = {row["offset"]: row for row in source}
    for row in rows:
        original = by_offset.get(row["offset"])
        if original is None or row["english"] != original["english"]:
            raise ValueError(f"English source changed at {row['offset']}")
        if row["status"] not in STATES:
            raise ValueError(f"Invalid status at {row['offset']}")
        if row["status"] == "excluded" and not row["note"].strip():
            raise ValueError(f"Excluded entry has no reason at {row['offset']}")
        if row["status"] == "revised" and row["vietnamese"] == original["vietnamese"]:
            raise ValueError(f"Revised entry is unchanged at {row['offset']}")
    if args.action in {"apply", "amend"}:
        if args.decisions is None:
            raise ValueError("--decisions is required")
        decisions = json.loads(args.decisions.read_text(encoding="utf-8"))
        start, size = decisions["start"], decisions["size"]
        revisions = decisions.get("revisions", {})
        replacements = decisions.get("replacements", {})
        exclusions = decisions.get("exclusions", {})
        deferred = set(decisions.get("deferred", []))
        window = rows[start:start + size]
        if set(revisions) & set(replacements):
            raise ValueError("Offset has both a full revision and phrase replacements")
        if len(window) != size or not (set(revisions | replacements | exclusions) | deferred) <= {r["offset"] for r in window}:
            raise ValueError("Decision offsets outside requested batch")
        target_status = {"pending"} if args.action == "apply" else {"approved", "revised"}
        if any(row["status"] not in target_status for row in window
               if row["offset"] in revisions or row["offset"] in replacements
               or row["offset"] in exclusions or row["offset"] in deferred):
            raise ValueError(f"Decision target must be one of {sorted(target_status)}")
        for row in window:
            if row["status"] not in target_status:
                continue
            offset = row["offset"]
            if offset in revisions:
                row["vietnamese"] = revisions[offset]
                row["status"] = "revised"
            elif offset in replacements:
                value = row["vietnamese"]
                for change in replacements[offset]:
                    wrong, right = change[:2]
                    expected_count = change[2] if len(change) == 3 else 1
                    if value.count(wrong) != expected_count:
                        raise ValueError(f"Phrase count differs at {offset}: {wrong!r} "
                                         f"({value.count(wrong)} vs {expected_count})")
                    value = value.replace(wrong, right)
                row["vietnamese"] = value
                row["status"] = "revised"
            elif offset in exclusions:
                row["status"] = "excluded"
                row["note"] = exclusions[offset]
            elif offset in deferred:
                row["note"] = "Cần tra ngữ cảnh tên màn."
            elif args.action == "apply":
                row["status"] = "approved"
        with LEDGER.open("w", encoding="utf-8-sig", newline="") as file:
            writer = csv.DictWriter(file, fieldnames=FIELDS)
            writer.writeheader()
            writer.writerows(rows)
        print(f"Reviewed rows {start}-{start + size - 1}: "
              f"{len(revisions) + len(replacements)} revised, "
              f"{len(exclusions)} excluded, {len(deferred)} deferred")
        return
    if args.action == "batch":
        for row in rows[args.start:args.start + args.size]:
            print(f"{row['offset']} [{row['status']}] EN: {row['english']}")
            print(f"         VI: {row['vietnamese']}")
    else:
        print(dict(Counter(row["status"] for row in rows)))
        if args.action == "check" and any(row["status"] == "pending" for row in rows):
            raise SystemExit("Editorial review incomplete")


if __name__ == "__main__":
    main()
