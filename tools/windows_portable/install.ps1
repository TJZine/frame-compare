$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

function Initialize-Directory([string]$Path) {
  if (!(Test-Path -LiteralPath $Path)) {
    New-Item -ItemType Directory -Path $Path | Out-Null
  }
}

function ConvertTo-NormalizedPathEntry([string]$PathEntry) {
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
$updateShimPs1Source = Join-Path $shimSource "frame-compare-update.ps1"
$updateShimCmdSource = Join-Path $shimSource "frame-compare-update.cmd"
$updatePublicKeySource = Join-Path $shimSource "update_public_key.xml"
if (
  !(Test-Path -LiteralPath $shimPs1Source) -or
  !(Test-Path -LiteralPath $shimCmdSource) -or
  !(Test-Path -LiteralPath $updateShimPs1Source) -or
  !(Test-Path -LiteralPath $updateShimCmdSource) -or
  !(Test-Path -LiteralPath $updatePublicKeySource)
) {
  throw "Shim files are missing under: $shimSource"
}

$installRoot = Join-Path (Join-Path $env:LOCALAPPDATA "Programs") "FrameCompare"
$binDir = Join-Path $installRoot "bin"
$stateDir = Join-Path $installRoot "state"
$configPath = Join-Path $stateDir "config.json"
$configTmpPath = Join-Path $stateDir "config.json.tmp"

Initialize-Directory -Path $installRoot
Initialize-Directory -Path $binDir
Initialize-Directory -Path $stateDir

Copy-Item -LiteralPath $shimPs1Source -Destination (Join-Path $binDir "frame-compare.ps1") -Force
Copy-Item -LiteralPath $shimCmdSource -Destination (Join-Path $binDir "frame-compare.cmd") -Force
Copy-Item -LiteralPath $updateShimPs1Source -Destination (Join-Path $binDir "frame-compare-update.ps1") -Force
Copy-Item -LiteralPath $updateShimCmdSource -Destination (Join-Path $binDir "frame-compare-update.cmd") -Force
Copy-Item -LiteralPath $updatePublicKeySource -Destination (Join-Path $binDir "update_public_key.xml") -Force

$config = @{
  schema_version = 1
  install_type = "portable_bundle"
  bundle_path = $bundleRoot
} | ConvertTo-Json
$utf8NoBom = New-Object System.Text.UTF8Encoding($false)
[System.IO.File]::WriteAllText($configTmpPath, $config, $utf8NoBom)
Move-Item -LiteralPath $configTmpPath -Destination $configPath -Force

$portableConfigToml = Join-Path $stateDir "config.toml"
if (!(Test-Path -LiteralPath $portableConfigToml)) {
  $bundleConfigToml = Join-Path (Join-Path $bundleRoot "config") "config.toml"
  if (Test-Path -LiteralPath $bundleConfigToml) {
    Copy-Item -LiteralPath $bundleConfigToml -Destination $portableConfigToml -Force
  } else {
    $defaultPortableConfigToml = @"
[paths]
input_dir = "comparison_videos"
screenshots_dir = "screenshots"
generated_dir = "generated"
config_dir = "config"
"@
    [System.IO.File]::WriteAllText($portableConfigToml, $defaultPortableConfigToml, $utf8NoBom)
  }
}

$userPath = [Environment]::GetEnvironmentVariable("Path", "User")
$entries = @()
if (-not [string]::IsNullOrWhiteSpace($userPath)) {
  $entries = @($userPath -split ";" | Where-Object { -not [string]::IsNullOrWhiteSpace($_) })
}

$normalizedBinDir = ConvertTo-NormalizedPathEntry -PathEntry $binDir
$hasEntry = $false
foreach ($entry in $entries) {
  if ((ConvertTo-NormalizedPathEntry -PathEntry $entry) -eq $normalizedBinDir) {
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
Write-Host "Updater command: frame-compare-update --help"
