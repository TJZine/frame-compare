$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

function Ensure-Directory([string]$Path) {
  if (!(Test-Path -LiteralPath $Path)) {
    New-Item -ItemType Directory -Path $Path | Out-Null
  }
}

function Normalize-PathEntry([string]$PathEntry) {
  if ([string]::IsNullOrWhiteSpace($PathEntry)) {
    return ""
  }
  return $PathEntry.Trim().Trim('"').TrimEnd('\').ToLowerInvariant()
}

$bundleRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$bundleLauncher = Join-Path $bundleRoot "frame-compare.ps1"
if (!(Test-Path -LiteralPath $bundleLauncher)) {
  throw "Bundle launcher not found: $bundleLauncher"
}

$shimSource = Join-Path $bundleRoot "shim"
$shimPs1Source = Join-Path $shimSource "frame-compare.ps1"
$shimCmdSource = Join-Path $shimSource "frame-compare.cmd"
if (!(Test-Path -LiteralPath $shimPs1Source) -or !(Test-Path -LiteralPath $shimCmdSource)) {
  throw "Shim files are missing under: $shimSource"
}

$installRoot = Join-Path (Join-Path $env:LOCALAPPDATA "Programs") "FrameCompare"
$binDir = Join-Path $installRoot "bin"
$stateDir = Join-Path $installRoot "state"
$configPath = Join-Path $stateDir "config.json"
$configTmpPath = Join-Path $stateDir "config.json.tmp"

Ensure-Directory -Path $installRoot
Ensure-Directory -Path $binDir
Ensure-Directory -Path $stateDir

Copy-Item -LiteralPath $shimPs1Source -Destination (Join-Path $binDir "frame-compare.ps1") -Force
Copy-Item -LiteralPath $shimCmdSource -Destination (Join-Path $binDir "frame-compare.cmd") -Force

$config = @{
  schema_version = 1
  install_type = "portable_bundle"
  bundle_path = $bundleRoot
} | ConvertTo-Json
$utf8NoBom = New-Object System.Text.UTF8Encoding($false)
[System.IO.File]::WriteAllText($configTmpPath, $config, $utf8NoBom)
Move-Item -LiteralPath $configTmpPath -Destination $configPath -Force

$userPath = [Environment]::GetEnvironmentVariable("Path", "User")
$entries = @()
if (-not [string]::IsNullOrWhiteSpace($userPath)) {
  $entries = @($userPath -split ";" | Where-Object { -not [string]::IsNullOrWhiteSpace($_) })
}

$normalizedBinDir = Normalize-PathEntry -PathEntry $binDir
$hasEntry = $false
foreach ($entry in $entries) {
  if ((Normalize-PathEntry -PathEntry $entry) -eq $normalizedBinDir) {
    $hasEntry = $true
    break
  }
}

if (-not $hasEntry) {
  $entries += $binDir
  $newUserPath = $entries -join ";"
  [Environment]::SetEnvironmentVariable("Path", $newUserPath, "User")
  Write-Host "Added to user PATH: $binDir"
} else {
  Write-Host "User PATH already contains: $binDir"
}

Write-Host ""
Write-Host "Installed Frame Compare shim."
Write-Host "Open a new terminal, then run: frame-compare --help"
