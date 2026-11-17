# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Vince Bono
import gzip
import hashlib
import os
import sys
import tempfile
import unittest
import zipfile
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))

import ad_hygiene  # noqa: E402
import asset_inventory  # noqa: E402
import backup_verify  # noqa: E402

FIXTURE = Path(__file__).parent / "fixtures" / "users.csv"
NOW = datetime(2026, 11, 1)


class AdHygieneTest(unittest.TestCase):
    def findings(self):
        return ad_hygiene.check(ad_hygiene.load(FIXTURE), NOW)

    def test_flags_each_problem_and_ranks_admins_first(self):
        got = [(f["account"], f["severity"], f["issue"]) for f in self.findings()]
        self.assertEqual(
            got,
            [
                ("old.admin", "high", "no sign-in for 303 days"),
                ("old.admin", "high", "password never expires"),
                ("never.used", "medium", "enabled but never signed in"),
                ("stale.user", "medium", "no sign-in for 122 days"),
                ("stale.user", "low", "password is 669 days old"),
                ("svc.print", "low", "password never expires"),
            ],
        )

    def test_healthy_and_disabled_accounts_are_not_flagged(self):
        accounts = {f["account"] for f in self.findings()}
        self.assertFalse({"good.user", "left.company"} & accounts)

    def test_missing_column_is_an_error_not_a_clean_report(self):
        with tempfile.TemporaryDirectory() as d:
            bad = Path(d, "bad.csv")
            bad.write_text("SamAccountName,Enabled\nx,True\n", encoding="utf-8")
            with self.assertRaises(ValueError):
                ad_hygiene.load(bad)
            self.assertEqual(ad_hygiene.main([str(bad)]), 2)


class AssetInventoryTest(unittest.TestCase):
    def test_counts_enabled_computers_and_flags_unsupported_and_stale(self):
        rows = ad_hygiene.load(FIXTURE.with_name("computers.csv"), asset_inventory.REQUIRED)
        counts, findings = asset_inventory.check(rows, NOW)
        self.assertEqual(counts["Windows 11 Pro"], 2)
        self.assertEqual(counts["unknown"], 1)
        self.assertNotIn("Windows 7 Professional", counts)  # disabled
        self.assertEqual(
            [(f["computer"], f["severity"], f["issue"]) for f in findings],
            [
                ("PC-OLD", "high", "Windows 10 Pro is out of support"),
                ("SRV-FILE", "high", "Windows Server 2012 R2 Standard is out of support"),
                ("PC-002", "medium", "not seen for 152 days"),
                ("PC-GHOST", "medium", "enabled but never seen on the domain"),
            ],
        )

    def test_users_export_is_rejected(self):
        self.assertEqual(asset_inventory.main([str(FIXTURE)]), 2)


class BackupVerifyTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def good_zip(self, name="backup.zip"):
        path = self.dir / name
        with zipfile.ZipFile(path, "w") as z:
            z.writestr("data.txt", "hello" * 100)
        return path

    def test_good_backup_passes(self):
        self.good_zip()
        self.assertEqual(backup_verify.verify(self.dir, "*.zip", 26, 10), [])
        self.assertEqual(backup_verify.main([str(self.dir), "--pattern", "*.zip"]), 0)

    def test_old_small_or_missing_backup_fails(self):
        self.assertIn("no files match", backup_verify.verify(self.dir, "*.zip", 26, 1)[0])
        path = self.good_zip()
        two_days_ago = path.stat().st_mtime - 48 * 3600
        os.utime(path, (two_days_ago, two_days_ago))
        problems = backup_verify.verify(self.dir, "*.zip", 26, 10**9)
        self.assertEqual(len(problems), 2)
        self.assertIn("hours old", problems[0])
        self.assertIn("minimum", problems[1])
        self.assertEqual(backup_verify.main([str(self.dir)]), 1)

    def test_corrupt_archives_fail(self):
        (self.dir / "a.zip").write_bytes(b"this is not a zip")
        self.assertIn("unreadable archive", backup_verify.verify(self.dir, "*.zip", 26, 1)[0])
        whole = gzip.compress(b"x" * 100_000)
        (self.dir / "b.gz").write_bytes(whole[: len(whole) // 2])
        self.assertIn("unreadable archive", backup_verify.verify(self.dir, "*.gz", 26, 1)[0])

    def test_uppercase_extension_is_still_checked(self):
        (self.dir / "NIGHTLY.ZIP").write_bytes(b"this is not a zip")
        self.assertIn("unreadable archive", backup_verify.verify(self.dir, "*", 26, 1)[0])

    def test_checksum_sidecar_is_compared(self):
        path = self.good_zip()
        sidecar = self.dir / "backup.zip.sha256"
        sidecar.write_text(hashlib.sha256(path.read_bytes()).hexdigest() + "  backup.zip\n", encoding="utf-8")
        self.assertEqual(backup_verify.verify(self.dir, "*", 26, 1), [])
        sidecar.write_text("0" * 64 + "  backup.zip\n", encoding="utf-8")
        self.assertIn("does not match", backup_verify.verify(self.dir, "*.zip", 26, 1)[0])


if __name__ == "__main__":
    unittest.main()
