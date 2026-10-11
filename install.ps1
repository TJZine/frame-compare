Param(
  [Parameter(Mandatory = $false)]
  [switch]$SkipSync
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

if ($PSVersionTable.PSVersion.Major -lt 7) {
  throw "PowerShell 7 or newer is required to build Frame Compare from source. Run this installer with pwsh or install PowerShell 7, then rerun install.cmd."
}

& (Join-Path $PSScriptRoot "tools/windows_portable/install-from-source.ps1") -SkipSync:$SkipSync
exit $LASTEXITCODE
