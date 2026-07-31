Param(
  [Parameter(Mandatory = $false)]
  [switch]$SkipSync
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

& (Join-Path $PSScriptRoot "tools/windows_portable/install-from-source.ps1") -SkipSync:$SkipSync
exit $LASTEXITCODE
