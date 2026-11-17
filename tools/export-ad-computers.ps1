# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Vince Bono
#
# Read-only export of computer accounts for asset_inventory.py. Needs the ActiveDirectory module (RSAT).
# Usage: .\export-ad-computers.ps1 -Path computers.csv
param([string]$Path = "computers.csv")

Get-ADComputer -Filter * -Properties OperatingSystem, LastLogonDate |
    Select-Object Name, Enabled, OperatingSystem,
        @{ n = 'LastLogon'; e = { '{0:s}' -f $_.LastLogonDate } } |
    Export-Csv -Path $Path -NoTypeInformation -Encoding UTF8
