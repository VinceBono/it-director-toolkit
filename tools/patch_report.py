#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Vince Bono
"""List computers whose newest installed Windows update is too old. Reads a CSV export; never touches a machine."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timedelta
from pathlib import Path

from ad_hygiene import _date, load

REQUIRED = {"Computer", "HotFixID", "InstalledOn"}


def check(rows: list[dict[str, str]], now: datetime, max_days: int = 45) -> list[dict[str, str]]:
    """One finding per computer whose newest dated update is older than `max_days`, oldest first."""
    newest: dict[str, tuple[datetime, str] | None] = {}
    for row in rows:
        name = row["Computer"].strip()
        installed = _date(row["InstalledOn"])
        newest.setdefault(name, None)
        current = newest[name]
        if installed and (current is None or installed > current[0]):
            newest[name] = (installed, row["HotFixID"].strip())
    findings = []
    for name, last in newest.items():
        if last is None:
            findings.append({"computer": name, "days": "", "issue": "no update has an install date"})
        elif now - last[0] > timedelta(days=max_days):
            days = (now - last[0]).days
            findings.append({"computer": name, "days": str(days), "issue": f"last update {last[1]} was {days} days ago"})
    return sorted(findings, key=lambda f: (-int(f["days"] or 10**6), f["computer"].lower()))


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("csv", type=Path, help="export from export-hotfixes.ps1")
    ap.add_argument("--max-days", type=int, default=45, help="flag computers with no update in this long (default 45)")
    ap.add_argument("--json", action="store_true", help="machine-readable output")
    args = ap.parse_args(argv)

    try:
        rows = load(args.csv, REQUIRED)
        findings = check(rows, datetime.now(), args.max_days)
    except (OSError, ValueError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    if args.json:
        print(json.dumps(findings, indent=2))
    else:
        for f in findings:
            print(f"{f['computer']:<24}{f['issue']}")
        print(f"\n{len({r['Computer'].strip() for r in rows})} computer(s) in the export, {len(findings)} behind")
    return 1 if findings else 0


if __name__ == "__main__":
    sys.exit(main())
