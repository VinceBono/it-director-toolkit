#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Vince Bono
"""Count computers by operating system and flag unsupported or stale ones. Reads a CSV export; never touches AD."""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from datetime import datetime, timedelta
from pathlib import Path

from ad_hygiene import _date, _true, load

REQUIRED = {"Name", "Enabled", "OperatingSystem", "LastLogon"}
# Out of vendor support as of 2026-11. Matched as a prefix of the AD OperatingSystem string.
# shortcut: a fixed list, review it when Microsoft retires another release (Server 2016 ends 2027-01-12).
UNSUPPORTED = (
    "Windows 2000",
    "Windows XP",
    "Windows Vista",
    "Windows 7",
    "Windows 8",
    "Windows 10",
    "Windows Server 2003",
    "Windows Server 2008",
    "Windows Server 2012",
)


def unsupported(os_name: str) -> bool:
    # Windows 10 LTSC releases have their own, later end dates; check those by hand.
    return os_name.startswith(UNSUPPORTED) and "LTSC" not in os_name


def check(rows: list[dict[str, str]], now: datetime, stale_days: int = 90) -> tuple[dict[str, int], list[dict[str, str]]]:
    """OS counts and findings, for enabled computers only."""
    counts: Counter[str] = Counter()
    findings = []
    for row in rows:
        if not _true(row["Enabled"]):
            continue
        os_name = (row["OperatingSystem"] or "").strip() or "unknown"
        counts[os_name] += 1
        seen = _date(row["LastLogon"])
        if unsupported(os_name):
            findings.append({"computer": row["Name"], "severity": "high", "issue": f"{os_name} is out of support"})
        if seen is None:
            findings.append({"computer": row["Name"], "severity": "medium", "issue": "enabled but never seen on the domain"})
        elif now - seen > timedelta(days=stale_days):
            findings.append({"computer": row["Name"], "severity": "medium", "issue": f"not seen for {(now - seen).days} days"})
    findings.sort(key=lambda f: (f["severity"] != "high", f["computer"].lower()))
    return dict(counts.most_common()), findings


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("csv", type=Path, help="export from export-ad-computers.ps1")
    ap.add_argument("--stale-days", type=int, default=90, help="flag computers not seen for this long (default 90)")
    ap.add_argument("--json", action="store_true", help="machine-readable output")
    args = ap.parse_args(argv)

    try:
        counts, findings = check(load(args.csv, REQUIRED), datetime.now(), args.stale_days)
    except (OSError, ValueError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    if args.json:
        print(json.dumps({"operating_systems": counts, "findings": findings}, indent=2))
    else:
        for os_name, n in counts.items():
            print(f"{n:>5}  {os_name}")
        print()
        for f in findings:
            print(f"{f['severity'].upper():<7}{f['computer']:<24}{f['issue']}")
        print(f"\n{sum(counts.values())} enabled computer(s), {len(findings)} finding(s)")
    return 1 if findings else 0


if __name__ == "__main__":
    sys.exit(main())
