$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$shimDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$installRoot = Split-Path -Parent $shimDir
$configPath = Join-Path $installRoot "state\\config.json"

if (!(Test-Path -LiteralPath $configPath)) {
  Write-Error "Config not found: $configPath`nRun install.cmd from the portable bundle."
  exit 10
}

try {
  $config = Get-Content -LiteralPath $configPath -Raw | ConvertFrom-Json
} catch {
  Write-Error "Invalid config file: $configPath`nRun install.cmd from the portable bundle."
  exit 11
}
if ($null -eq $config) {
  Write-Error "Invalid config file: $configPath`nRun install.cmd from the portable bundle."
  exit 11
}

$schemaVersion = 0
$schemaProp = $config.PSObject.Properties["schema_version"]
if ($null -ne $schemaProp -and $null -ne $schemaProp.Value) {
  $schemaVersion = [int]$schemaProp.Value
}
if ($schemaVersion -ne 1) {
  Write-Error "Unsupported config schema version '$schemaVersion' in $configPath`nRun install.cmd from the portable bundle."
  exit 15
}

$installType = [string]$config.install_type
if ($installType -ne "portable_bundle") {
  Write-Error "Unsupported install_type '$installType' in $configPath"
  exit 16
}

$bundlePath = [string]$config.bundle_path
if ([string]::IsNullOrWhiteSpace($bundlePath)) {
  Write-Error "bundle_path is missing in config: $configPath`nRun install.cmd from the portable bundle."
  exit 12
}

if (!(Test-Path -LiteralPath $bundlePath)) {
  Write-Error "Portable bundle directory not found: $bundlePath`nRun install.cmd from the bundle's current location."
  exit 13
}

$bundleLauncher = Join-Path $bundlePath "frame-compare.ps1"
if (!(Test-Path -LiteralPath $bundleLauncher)) {
  Write-Error "Bundle launcher not found: $bundleLauncher`nRebuild or re-extract the portable bundle, then run install.cmd again."
  exit 14
}

& $bundleLauncher @args
if ($null -eq $LASTEXITCODE) {
  exit 1
}
exit $LASTEXITCODE
