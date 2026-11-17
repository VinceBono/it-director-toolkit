# it-director-toolkit

Small, read-only checks an IT lead at a plant or small company runs every week. Each one answers a question
an auditor or an insurer will ask, and each one exits non-zero when something is wrong so it can run as a
scheduled task.

No dependencies beyond Python 3.10+. Nothing here changes a system; the tools only read files.

| Tool | Question it answers |
|---|---|
| [`tools/ad_hygiene.py`](tools/ad_hygiene.py) | Which enabled accounts are stale, never used, or have passwords that never expire? |
| [`tools/asset_inventory.py`](tools/asset_inventory.py) | How many computers run each operating system, and which are unsupported or gone? |
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

## Asset inventory

```powershell
.\tools\export-ad-computers.ps1 -Path computers.csv
python tools\asset_inventory.py computers.csv
```

```
    2  Windows 11 Pro
    1  Windows 10 Pro
    1  Windows 10 Enterprise LTSC
    1  Windows Server 2012 R2 Standard
    1  Windows Server 2022 Standard
    1  unknown

HIGH   PC-OLD                  Windows 10 Pro is out of support
HIGH   SRV-FILE                Windows Server 2012 R2 Standard is out of support
MEDIUM PC-002                  not seen for 152 days
MEDIUM PC-GHOST                enabled but never seen on the domain

7 enabled computer(s), 4 finding(s)
```

- Counts and findings cover enabled computer accounts only. `--stale-days 90` and `--json` work as above.
- "Out of support" is a fixed list in the script, current as of November 2026. Windows 10 LTSC is not
  flagged because its editions end on different dates; check those by hand.
- It only knows what Active Directory knows. Machines that never joined the domain (PLCs, workgroup HMIs,
  phones, printers) are not in the export.

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
  `export-ad-users.ps1` and `export-ad-computers.ps1` have not been run against a real domain.
- **A readable archive is not a restorable backup.** `backup_verify.py` proves the file is fresh and intact.
  Only a test restore proves you can recover.
- **Last sign-in is approximate.** Active Directory replicates it between domain controllers with up to
  14 days of lag, so don't set `--stale-days` below about 30.
- **Planned, not built:** patch reporting.

## Development

```bash
python -m unittest discover -s tests -v
python scripts/commitguard.py --all
```

## License

MIT. See [LICENSE](LICENSE).
