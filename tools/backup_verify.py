#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Vince Bono
"""Check that the newest backup file is recent, big enough and not corrupt. Exit 1 if not.

Reads only. Archives (.zip, .gz, .tgz) are read end to end; a `<file>.sha256` sidecar is compared if present.
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import sys
import time
import zipfile
from pathlib import Path

CHUNK = 1 << 20


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as f:
        while chunk := f.read(CHUNK):
            digest.update(chunk)
    return digest.hexdigest()


def _archive_error(path: Path) -> str | None:
    suffix = path.suffix.lower()  # Windows backup jobs often write .ZIP
    try:
        if suffix == ".zip":
            with zipfile.ZipFile(path) as z:
                bad = z.testzip()
                return f"corrupt member {bad}" if bad else None
        if suffix in {".gz", ".tgz"}:
            with gzip.open(path, "rb") as f:
                while f.read(CHUNK):
                    pass
    except (OSError, EOFError, zipfile.BadZipFile) as e:
        return f"unreadable archive: {e}"
    return None


def verify(folder: Path, pattern: str, max_age_hours: float, min_bytes: int, now: float | None = None) -> list[str]:
    """Problems with the newest file matching `pattern`. Empty list means the backup looks good."""
    files = [p for p in folder.glob(pattern) if p.is_file() and p.suffix != ".sha256"]
    if not files:
        return [f"no files match {pattern} in {folder}"]
    newest = max(files, key=lambda p: p.stat().st_mtime)
    stat = newest.stat()
    problems = []
    age_hours = ((now or time.time()) - stat.st_mtime) / 3600
    if age_hours > max_age_hours:
        problems.append(f"{newest.name} is {age_hours:.1f} hours old (limit {max_age_hours:g})")
    if stat.st_size < min_bytes:
        problems.append(f"{newest.name} is {stat.st_size} bytes (minimum {min_bytes})")
    if error := _archive_error(newest):
        problems.append(f"{newest.name}: {error}")
    sidecar = newest.with_name(newest.name + ".sha256")
    if sidecar.exists():
        fields = sidecar.read_text(encoding="utf-8").split()
        if not fields or fields[0].lower() != _sha256(newest):
            problems.append(f"{newest.name} does not match {sidecar.name}")
    return problems


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("folder", type=Path, help="where the backup job writes its files")
    ap.add_argument("--pattern", default="*", help='file name pattern, e.g. "*.zip" (default: any file)')
    ap.add_argument("--max-age-hours", type=float, default=26, help="newest file must be younger than this (default 26)")
    ap.add_argument("--min-bytes", type=int, default=1, help="newest file must be at least this big (default 1)")
    args = ap.parse_args(argv)

    if not args.folder.is_dir():
        print(f"FAIL: {args.folder} is not a folder", file=sys.stderr)
        return 1
    problems = verify(args.folder, args.pattern, args.max_age_hours, args.min_bytes)
    for p in problems:
        print(f"FAIL: {p}", file=sys.stderr)
    if not problems:
        print("OK: newest backup is recent, big enough and readable")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
