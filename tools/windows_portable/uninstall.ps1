$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

. (Join-Path $PSScriptRoot "portable_activation.ps1")

function Remove-DirectoryIfEmpty([string]$Path) {
  if (
    (Test-Path -LiteralPath $Path -PathType Container) -and
    @(Get-ChildItem -LiteralPath $Path -Force).Count -eq 0
  ) {
    Remove-Item -LiteralPath $Path -Force
  }
}

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
    Assert-NoReparsePointAncestor -Path $path -Label "Install state"
  }

  Update-PortableUserPath -BinDir $binDir -Remove

  foreach ($path in $installedFiles) {
    if (Test-Path -LiteralPath $path) {
      Remove-Item -LiteralPath $path -Force
    }
  }

  Remove-DirectoryIfEmpty -Path $binDir
} finally {
  $activationLock.Dispose()
}

Write-Host "Uninstalled Frame Compare shim."
Write-Host "Open a new terminal to observe PATH changes."
