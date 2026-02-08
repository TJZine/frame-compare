$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

function Normalize-PathEntry([string]$PathEntry) {
  if ([string]::IsNullOrWhiteSpace($PathEntry)) {
    return ""
  }
  return $PathEntry.Trim().Trim('"').TrimEnd('\').ToLowerInvariant()
}

$installRoot = Join-Path (Join-Path $env:LOCALAPPDATA "Programs") "FrameCompare"
$binDir = Join-Path $installRoot "bin"

$userPath = [Environment]::GetEnvironmentVariable("Path", "User")
$entries = @()
if (-not [string]::IsNullOrWhiteSpace($userPath)) {
  $entries = @($userPath -split ";" | Where-Object { -not [string]::IsNullOrWhiteSpace($_) })
}

$normalizedBinDir = Normalize-PathEntry -PathEntry $binDir
$filtered = @()
foreach ($entry in $entries) {
  if ((Normalize-PathEntry -PathEntry $entry) -ne $normalizedBinDir) {
    $filtered += $entry
  }
}
[Environment]::SetEnvironmentVariable("Path", ($filtered -join ";"), "User")

if (Test-Path -LiteralPath $installRoot) {
  Remove-Item -Recurse -Force -LiteralPath $installRoot
}

Write-Host "Uninstalled Frame Compare shim."
Write-Host "Open a new terminal to observe PATH changes."
