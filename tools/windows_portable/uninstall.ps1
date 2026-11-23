$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

. (Join-Path $PSScriptRoot "portable_activation.ps1")

$stateDir = Get-PortableStateDirectory
$installRoot = Split-Path -Parent $stateDir
$binDir = Join-Path $installRoot "bin"

$activationLock = Open-PortableActivationLock $stateDir
try {
  Assert-NoPendingPortableMigration $stateDir
  Assert-NoReparsePointAncestor -Path $binDir -Label "Installed shims"
  $shimPaths = @(Get-PortableShimNames | ForEach-Object { Join-Path $binDir $_ })
  $pointerPaths = @("config.json", "config.json.tmp" | ForEach-Object { Join-Path $stateDir $_ })
  $installedFiles = $shimPaths + $pointerPaths
  foreach ($path in $installedFiles) {
    $null = Get-OptionalPortableRegularFile $path
  }

  Update-PortableUserPath -BinDir $binDir -Remove

  foreach ($path in $installedFiles) {
    Remove-OptionalPortableRegularFile $path
  }

  if ([IO.Directory]::Exists($binDir) -and
      @(Get-ChildItem -LiteralPath $binDir -Force).Count -eq 0) {
    [IO.Directory]::Delete($binDir)
  }
} finally {
  $activationLock.Dispose()
}

Write-Host "Uninstalled Frame Compare shim."
Write-Host "Open a new terminal to observe PATH changes."
