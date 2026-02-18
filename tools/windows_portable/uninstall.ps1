$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

function ConvertTo-NormalizedPathEntry([string]$PathEntry) {
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

$normalizedBinDir = ConvertTo-NormalizedPathEntry -PathEntry $binDir
$filtered = @()
foreach ($entry in $entries) {
  if ((ConvertTo-NormalizedPathEntry -PathEntry $entry) -ne $normalizedBinDir) {
    $filtered += $entry
  }
}
[Environment]::SetEnvironmentVariable("Path", ($filtered -join ";"), "User")

foreach ($file in @("frame-compare.ps1", "frame-compare.cmd", "frame-compare-update.ps1", "frame-compare-update.cmd", "update_public_key.xml")) {
  $path = Join-Path $binDir $file
  if (Test-Path -LiteralPath $path) {
    Remove-Item -LiteralPath $path -Force
  }
}

if (Test-Path -LiteralPath $installRoot) {
  Remove-Item -Recurse -Force -LiteralPath $installRoot
}

Write-Host "Uninstalled Frame Compare shim."
Write-Host "Open a new terminal to observe PATH changes."
