#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Vince Bono
"""Find risky Active Directory accounts in a CSV export. Reads a file; never touches AD."""

from __future__ import annotations

import argparse
import csv
import json
import sys
from datetime import datetime, timedelta
from pathlib import Path

REQUIRED = {"SamAccountName", "Enabled", "LastLogon", "PasswordNeverExpires", "PasswordLastSet", "AdminCount"}
NEVER = datetime(1700, 1, 1)  # AD reports "never" as a date in 1601


def _date(value: str) -> datetime | None:
    value = (value or "").strip()
    if not value:
        return None
    parsed = datetime.fromisoformat(value)
    return parsed if parsed > NEVER else None


def _true(value: str) -> bool:
    return (value or "").strip().lower() in {"true", "1"}


def check(rows: list[dict[str, str]], now: datetime, stale_days: int = 90, password_days: int = 365) -> list[dict[str, str]]:
    """One finding per problem, on enabled accounts only. Disabled accounts can't sign in."""
    findings = []

    def add(row: dict[str, str], severity: str, issue: str) -> None:
        findings.append({"account": row["SamAccountName"], "severity": severity, "issue": issue})

    for row in rows:
        if not _true(row["Enabled"]):
            continue
        admin = (row["AdminCount"] or "").strip() == "1"
        logon, pw_set = _date(row["LastLogon"]), _date(row["PasswordLastSet"])
        if logon is None:
            add(row, "high" if admin else "medium", "enabled but never signed in")
        elif now - logon > timedelta(days=stale_days):
            add(row, "high" if admin else "medium", f"no sign-in for {(now - logon).days} days")
        if _true(row["PasswordNeverExpires"]):
            add(row, "high" if admin else "low", "password never expires")
        if pw_set is not None and now - pw_set > timedelta(days=password_days):
            add(row, "high" if admin else "low", f"password is {(now - pw_set).days} days old")
    order = {"high": 0, "medium": 1, "low": 2}
    return sorted(findings, key=lambda f: (order[f["severity"]], f["account"].lower()))


def load(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        missing = REQUIRED - set(reader.fieldnames or [])
        if missing:
            raise ValueError(f"{path}: missing columns {', '.join(sorted(missing))}")
        return list(reader)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("csv", type=Path, help="export from export-ad-users.ps1")
    ap.add_argument("--stale-days", type=int, default=90, help="flag no sign-in for this long (default 90)")
    ap.add_argument("--password-days", type=int, default=365, help="flag passwords older than this (default 365)")
    ap.add_argument("--json", action="store_true", help="machine-readable output")
    args = ap.parse_args(argv)

    try:
        findings = check(load(args.csv), datetime.now(), args.stale_days, args.password_days)
    except (OSError, ValueError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    if args.json:
        print(json.dumps(findings, indent=2))
    else:
        for f in findings:
            print(f"{f['severity'].upper():<7}{f['account']:<24}{f['issue']}")
        print(f"\n{len(findings)} finding(s)")
    return 1 if findings else 0


if __name__ == "__main__":
    sys.exit(main())
