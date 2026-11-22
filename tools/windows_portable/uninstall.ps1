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
    Assert-NoReparsePointAncestor -Path $path -Label "Install state"
    try {
      $item = Get-Item -LiteralPath $path -Force -ErrorAction Stop
      if ($item -isnot [IO.FileInfo]) { throw "Expected a regular installed file: $path" }
    } catch [System.Management.Automation.ItemNotFoundException] {
      # An absent managed file needs no cleanup.
    }
  }

  Update-PortableUserPath -BinDir $binDir -Remove

  foreach ($path in $installedFiles) {
    if ([IO.File]::Exists($path)) {
      $attributes = [IO.File]::GetAttributes($path)
      if ($attributes -band [IO.FileAttributes]::ReadOnly) {
        [IO.File]::SetAttributes($path, ($attributes -band (-bnot [IO.FileAttributes]::ReadOnly)))
      }
      [IO.File]::Delete($path)
    }
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
