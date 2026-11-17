# it-director-toolkit

Small, read-only checks an IT lead at a plant or small company runs every week. Each one answers a question
an auditor or an insurer will ask, and each one exits non-zero when something is wrong so it can run as a
scheduled task.

No dependencies beyond Python 3.10+. Nothing here changes a system; the tools only read files.

| Tool | Question it answers |
|---|---|
| [`tools/ad_hygiene.py`](tools/ad_hygiene.py) | Which enabled accounts are stale, never used, or have passwords that never expire? |
| [`tools/backup_verify.py`](tools/backup_verify.py) | Did last night's backup actually run, and can the file be read? |

## Account hygiene

Export users once on a machine with the ActiveDirectory PowerShell module, then analyse the file anywhere:

```powershell
.\tools\export-ad-users.ps1 -Path users.csv
python tools\ad_hygiene.py users.csv
```

```
HIGH   old.admin               no sign-in for 303 days
HIGH   old.admin               password never expires
MEDIUM never.used              enabled but never signed in
MEDIUM stale.user              no sign-in for 122 days
LOW    stale.user              password is 669 days old
LOW    svc.print               password never expires

6 finding(s)
```

- Only enabled accounts are reported. Privileged accounts (`AdminCount = 1`) are always rated high.
- `--stale-days 90` and `--password-days 365` set the limits. `--json` gives machine-readable output.
- Exit code: `0` clean, `1` findings, `2` the file could not be read.

The export is the only step that talks to Active Directory, and it only reads. `users.csv` holds account
names, so keep it out of git; this repo's `.gitignore` already excludes `*.csv`.

## Backup verification

```bash
python tools/backup_verify.py /mnt/backups/sql --pattern "*.zip" --max-age-hours 26 --min-bytes 1000000
```

It looks at the newest matching file and fails if it is too old, too small, or a corrupt `.zip`, `.gz` or
`.tgz`. If a `<file>.sha256` sits next to it, the checksum is compared too.

```
FAIL: sql-2026-11-01.zip is 49.3 hours old (limit 26)
```

Run it from Task Scheduler or cron and alert on a non-zero exit code.

## Limits

- **Tested on made-up data only.** The tests use a synthetic user list and files created in a temp folder.
  `export-ad-users.ps1` has not been run against a real domain.
- **A readable archive is not a restorable backup.** `backup_verify.py` proves the file is fresh and intact.
  Only a test restore proves you can recover.
- **Last sign-in is approximate.** Active Directory replicates it between domain controllers with up to
  14 days of lag, so don't set `--stale-days` below about 30.
- **Planned, not built:** asset inventory and patch reporting.

## Development

```bash
python -m unittest discover -s tests -v
python scripts/commitguard.py --all
```

## License

MIT. See [LICENSE](LICENSE).
