$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

function ConvertTo-NormalizedPathEntry([string]$PathEntry) {
  if ([string]::IsNullOrWhiteSpace($PathEntry)) {
    return ""
  }
  return $PathEntry.Trim().Trim('"').TrimEnd('\').ToLowerInvariant()
}

function Remove-DirectoryIfEmpty([string]$Path) {
  if (
    (Test-Path -LiteralPath $Path -PathType Container) -and
    @(Get-ChildItem -LiteralPath $Path -Force).Count -eq 0
  ) {
    Remove-Item -LiteralPath $Path -Force
  }
}

$installRoot = Join-Path (Join-Path $env:LOCALAPPDATA "Programs") "FrameCompare"
$binDir = Join-Path $installRoot "bin"
$stateDir = Join-Path $installRoot "state"

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

foreach ($file in @("config.json", "config.json.tmp")) {
  $path = Join-Path $stateDir $file
  if (Test-Path -LiteralPath $path) {
    Remove-Item -LiteralPath $path -Force
  }
}

Remove-DirectoryIfEmpty -Path $binDir
Remove-DirectoryIfEmpty -Path $stateDir
Remove-DirectoryIfEmpty -Path $installRoot

Write-Host "Uninstalled Frame Compare shim."
Write-Host "Open a new terminal to observe PATH changes."
