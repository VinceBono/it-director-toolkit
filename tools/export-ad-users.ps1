# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Vince Bono
#
# Read-only export of user accounts for ad_hygiene.py. Needs the ActiveDirectory module (RSAT).
# Usage: .\export-ad-users.ps1 -Path users.csv
param([string]$Path = "users.csv")

Get-ADUser -Filter * -Properties LastLogonDate, PasswordNeverExpires, PasswordLastSet, AdminCount |
    Select-Object SamAccountName, Enabled,
        @{ n = 'LastLogon'; e = { '{0:s}' -f $_.LastLogonDate } },
        PasswordNeverExpires,
        @{ n = 'PasswordLastSet'; e = { '{0:s}' -f $_.PasswordLastSet } },
        AdminCount |
    Export-Csv -Path $Path -NoTypeInformation -Encoding UTF8
