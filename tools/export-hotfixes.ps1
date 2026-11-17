# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Vince Bono
#
# Read-only export of installed Windows updates for patch_report.py.
# Usage: .\export-hotfixes.ps1 -ComputerName PC-001, SRV-FILE -Path hotfixes.csv
# Computers that cannot be reached are listed on screen and left out of the file.
param(
    [string[]]$ComputerName = $env:COMPUTERNAME,
    [string]$Path = "hotfixes.csv"
)

$rows = foreach ($computer in $ComputerName) {
    try {
        Get-HotFix -ComputerName $computer -ErrorAction Stop |
            Select-Object @{ n = 'Computer'; e = { $computer } }, HotFixID,
                @{ n = 'InstalledOn'; e = { '{0:s}' -f $_.InstalledOn } }
    } catch {
        Write-Warning "$computer not reached: $($_.Exception.Message)"
    }
}
$rows | Export-Csv -Path $Path -NoTypeInformation -Encoding UTF8
