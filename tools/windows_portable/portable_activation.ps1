. (Join-Path $PSScriptRoot "path_safety.ps1")

function Get-PortableStateDirectory() {
  return (Join-Path $env:LOCALAPPDATA "Programs\FrameCompare\state")
}

function ConvertTo-NormalizedPathEntry([string]$PathEntry) {
  return $PathEntry.Trim().Trim('"').TrimEnd('\').ToLowerInvariant()
}

function ConvertTo-PortableBundlePath([string]$Path) {
  # Require a drive-absolute or UNC share path. GetFullPath alone also accepts
  # drive-relative and current-drive-root-relative paths on Windows.
  if ($Path -notmatch '^(?:[A-Za-z]:[\\/]|[\\/]{2}[^\\/?\.][^\\/]*[\\/][^\\/]+(?:[\\/]|$))') {
    throw "Bundle path is not fully qualified: $Path"
  }
  $full = [IO.Path]::GetFullPath($Path)
  $root = [IO.Path]::GetPathRoot($full)
  if ($full.Length -gt $root.Length) { return $full.TrimEnd('\', '/') }
  return $full
}

function Open-PortableActivationLock([string]$StateDirectory) {
  $path = Join-Path $StateDirectory "source-install.lock"
  Assert-NoReparsePointAncestor -Path $path -Label "Activation lock"
  [IO.Directory]::CreateDirectory($StateDirectory) | Out-Null
  try {
    return [IO.File]::Open($path, [IO.FileMode]::OpenOrCreate, [IO.FileAccess]::ReadWrite, [IO.FileShare]::None)
  } catch {
    throw "Cannot own source-install activation lock $path. Another installer may be activating; retry after it finishes. $($_.Exception.Message)"
  }
}

function Read-OptionalPortableFile([string]$Path) {
  try { return ,([IO.File]::ReadAllBytes($Path)) }
  catch [IO.FileNotFoundException] { return $null }
  catch [IO.DirectoryNotFoundException] { return $null }
}

function ConvertFrom-PortableUtf8([byte[]]$Bytes) {
  return [Text.UTF8Encoding]::new($false, $true).GetString($Bytes).TrimStart([char]0xFEFF)
}

function Get-PortablePointerBundle([byte[]]$Bytes) {
  if ($null -eq $Bytes) { return $null }
  try {
    $json = ConvertFrom-PortableUtf8 $Bytes
    if (!$json.TrimStart().StartsWith("{")) { return $null }
    $pointer = $json | ConvertFrom-Json
    if ($pointer -isnot [pscustomobject] -or
        ($pointer.schema_version -isnot [int] -and $pointer.schema_version -isnot [long]) -or
        $pointer.schema_version -ne 1 -or $pointer.install_type -isnot [string] -or
        $pointer.install_type -cne "portable_bundle" -or
        $pointer.bundle_path -isnot [string]) {
      return $null
    }
    return (ConvertTo-PortableBundlePath $pointer.bundle_path)
  } catch {
    return $null
  }
}

function Get-PortableMoveSource([byte[]]$PointerBytes, [string]$BundleRoot) {
  $previous = Get-PortablePointerBundle $PointerBytes
  if ($null -eq $previous -or $previous -eq $BundleRoot) { return $null }
  # A disconnected drive has no ancestry to inspect. Check the mounted letter
  # explicitly so errors from existing drives or UNC paths still fail closed.
  $root = [IO.Path]::GetPathRoot($previous)
  if ($root -match '^[A-Za-z]:\\$' -and $root -notin [IO.Directory]::GetLogicalDrives()) {
    return $null
  }
  Assert-NoReparsePointAncestor -Path $previous -Label "Previous bundle"
  if (!(Test-Path -LiteralPath $previous -PathType Container) -or
      !(Test-Path -LiteralPath (Join-Path $previous "bundle_info.json") -PathType Leaf)) {
    return $null
  }
  if ((Test-PathWithin $BundleRoot $previous) -or (Test-PathWithin $previous $BundleRoot)) {
    throw "New bundle $BundleRoot must not nest with previous bundle $previous"
  }
  return $previous
}

function Get-PortableUserFolderState([string]$Path) {
  Assert-NoReparsePointAncestor -Path $Path -Label "User data location"
  try { $item = Get-Item -LiteralPath $Path -Force -ErrorAction Stop }
  catch [System.Management.Automation.ItemNotFoundException] { return "absent" }
  if (!$item.PSIsContainer) { throw "User data location is not a folder: $Path" }
  if (@(Get-ChildItem -LiteralPath $Path -Force -ErrorAction Stop).Count -gt 0) { return "populated" }
  return "empty"
}

function Get-PortableMigrationLocation($Folder) {
  $source = Get-PortableUserFolderState $Folder.Source
  $target = Get-PortableUserFolderState $Folder.Target
  $state = "conflict"
  if ($source -eq "populated" -and $target -ne "populated") { $state = "in place" }
  elseif ($source -eq "absent" -and $target -eq "populated") { $state = "moved" }
  return [pscustomobject]@{
    Name = $Folder.Name; Source = $Folder.Source; Target = $Folder.Target
    SourceExists = $source -ne "absent"; TargetExists = $target -ne "absent"; State = $state
  }
}

function Write-PendingMigrationRefusal([string]$MarkerPath, [string]$PointerPath) {
  Write-Warning "A pending source migration marker was found: $MarkerPath"
  try {
    $pending = (ConvertFrom-PortableUtf8 ([IO.File]::ReadAllBytes($MarkerPath))) | ConvertFrom-Json
    $previous = (ConvertTo-PortableBundlePath $pending.previous_bundle)
    $candidate = (ConvertTo-PortableBundlePath $pending.candidate_bundle)
    $active = $null
    try { $active = Get-PortablePointerBundle (Read-OptionalPortableFile $PointerPath) }
    catch { Write-Warning "Active pointer unavailable: $($_.Exception.Message)" }
    $locations = @(foreach ($folder in @($pending.folders)) {
      Get-PortableMigrationLocation $folder
    })
    if ($locations.Count -eq 0) { throw "Marker contains no user folders" }
    Write-Warning "Previous bundle: $previous"
    Write-Warning "Candidate bundle: $candidate"
    foreach ($folder in $locations) {
      Write-Warning "User folder $($folder.Name): source=$($folder.Source) (exists=$($folder.SourceExists)); target=$($folder.Target) (exists=$($folder.TargetExists)); $($folder.State)"
    }
    $movedFolders = @($locations | Where-Object { $_.State -eq "moved" })
    $conflicts = @($locations | Where-Object { $_.State -eq "conflict" })
    if ($active -eq $candidate -and $movedFolders.Count -eq $locations.Count) {
      Write-Warning "The active pointer names the candidate bundle, and the listed user folders are there: $candidate"
      Write-Warning "Activation may be incomplete: configuration and PATH setup occur after pointer publication. Keep user data in the candidate bundle."
      Write-Warning "Retain the pending marker until candidate activation is verified: check its config\config.toml (or state\config.toml), installed shim, and user PATH; then open a new terminal and confirm frame-compare launches the candidate."
      Write-Warning "Only after those checks succeed, delete the pending migration marker before retrying installation: $MarkerPath"
    } elseif ($active -eq $previous -and $conflicts.Count -eq 0) {
      Write-Warning "The migration was not committed. The active pointer still names the previous bundle."
      foreach ($folder in $locations) {
        if ($folder.State -eq "moved") {
          Write-Warning "Move back manually: $($folder.Target) -> $($folder.Source)"
        } else {
          Write-Warning "Already in place: $($folder.Source)"
        }
      }
      if ($movedFolders.Count -eq 0) {
        Write-Warning "No folder moved. It is safe to delete the pending migration marker: $MarkerPath"
      } else {
        Write-Warning "After restoring the listed folders, delete $MarkerPath before retrying installation."
      }
    } else {
      Write-Warning "Migration state conflict. Active pointer path: $PointerPath; normalized bundle: $active"
      try { Write-Warning "Current pointer value: $([IO.File]::ReadAllText($PointerPath, [Text.Encoding]::UTF8))" }
      catch { Write-Warning "Current pointer value unavailable: $($_.Exception.Message)" }
      Write-Warning "Do not move anything until every path and the pointer have been checked by hand."
    }
  } catch {
    Write-Warning "Could not read pending migration details: $($_.Exception.Message)"
    Write-Warning "Check the marker and folder locations by hand before retrying installation."
  }
  Write-Warning "No automatic recovery was attempted."
}

function Assert-NoPendingPortableMigration([string]$StateDirectory) {
  $marker = Join-Path $StateDirectory "source-migration.pending.json"
  Assert-NoReparsePointAncestor -Path $marker -Label "Pending source migration marker"
  if (Test-Path -LiteralPath $marker) {
    Write-PendingMigrationRefusal -MarkerPath $marker -PointerPath (Join-Path $StateDirectory "config.json")
    throw "A pending source migration must be repaired manually before another activation or uninstall can run."
  }
}

function Write-PortableFile([string]$Path, [byte[]]$Bytes, [switch]$NewOnly) {
  $temporary = "$Path.tmp-$([Guid]::NewGuid().ToString('N'))"
  try {
    [IO.File]::WriteAllBytes($temporary, $Bytes)
    if (!$NewOnly -and [IO.File]::Exists($Path)) {
      [IO.File]::Replace($temporary, $Path, [NullString]::Value)
    } else {
      [IO.File]::Move($temporary, $Path)
    }
  } finally {
    if ([IO.File]::Exists($temporary)) { [IO.File]::Delete($temporary) }
  }
}

function Write-PendingMigrationMarker(
  [string]$Path, [string]$PreviousBundle, [string]$BundleRoot, [object[]]$Folders, [byte[]]$PointerBytes
) {
  $record = @{
    previous_bundle = $PreviousBundle
    candidate_bundle = $BundleRoot
    folders = @($Folders | ForEach-Object {
      @{ name = $_.Name; source = $_.Source; target = $_.Target }
    })
    pointer_bytes_base64 = [Convert]::ToBase64String($PointerBytes)
  }
  Write-PortableFile -Path $Path -Bytes ([Text.Encoding]::UTF8.GetBytes(($record | ConvertTo-Json -Depth 4))) -NewOnly
}

function Write-RecoveryLocations([string]$PointerPath, [object[]]$Folders) {
  Write-Warning "Recovery stopped. Pointer: $PointerPath"
  try {
    $bytes = Read-OptionalPortableFile $PointerPath
    if ($null -eq $bytes) { Write-Warning "Pointer is absent." }
    else {
      Write-Warning "Current pointer value: $([Text.Encoding]::UTF8.GetString($bytes).TrimStart([char]0xFEFF))"
      Write-Warning "Current pointer bytes (base64): $([Convert]::ToBase64String($bytes))"
    }
  } catch { Write-Warning "Pointer contents unavailable: $($_.Exception.Message)" }
  foreach ($folder in $Folders) {
    Write-Warning "User folder $($folder.Name): previous=$($folder.Source) (exists=$(Test-Path -LiteralPath $folder.Source -ErrorAction SilentlyContinue)); new=$($folder.Target) (exists=$(Test-Path -LiteralPath $folder.Target -ErrorAction SilentlyContinue))"
  }
  Write-Warning "Recover these paths before retrying installation."
}

function Get-PortableShimNames() {
  return @("frame-compare.ps1", "frame-compare.cmd")
}

function Get-OptionalPortableRegularFile([string]$Path) {
  Assert-NoReparsePointAncestor -Path $Path -Label "Install state"
  try {
    $item = Get-Item -LiteralPath $Path -Force -ErrorAction Stop
    if ($item -isnot [IO.FileInfo] -or ($item.Attributes -band [IO.FileAttributes]::ReparsePoint)) {
      throw "Expected a regular installed file: $Path"
    }
    return $item
  } catch [System.Management.Automation.ItemNotFoundException] {
    return $null
  }
}

function Clear-PortableReadOnly([IO.FileInfo]$File) {
  $attributes = $File.Attributes
  if ($attributes -band [IO.FileAttributes]::ReadOnly) {
    [IO.File]::SetAttributes($File.FullName, ($attributes -band (-bnot [IO.FileAttributes]::ReadOnly)))
  }
}

function Remove-OptionalPortableRegularFile([string]$Path) {
  $item = Get-OptionalPortableRegularFile $Path
  if ($null -ne $item) {
    Clear-PortableReadOnly $item
    [IO.File]::Delete($Path)
  }
}

function Remove-LegacyUpdaterLeaves([string]$StateDirectory) {
  $binDir = Join-Path (Split-Path -Parent $StateDirectory) "bin"
  try {
    Assert-NoReparsePointAncestor -Path $binDir -Label "Installed shims"
  } catch {
    Write-Warning "The new installation is active. Could not inspect legacy leaves in ${binDir}: $($_.Exception.Message)"
    return
  }

  foreach ($name in @(
    "frame-compare-update.ps1", "frame-compare-update.cmd", "frame-compare-version.ps1",
    "update_public_key.xml"
  )) {
    $path = Join-Path $binDir $name
    try {
      Remove-OptionalPortableRegularFile $path
    } catch {
      Write-Warning "The new installation is active. Could not remove legacy file ${path}: $($_.Exception.Message)"
    }
  }
}

function Get-PortableUserPath() {
  $key = [Microsoft.Win32.Registry]::CurrentUser.OpenSubKey("Environment")
  if ($null -eq $key) { return $null }
  try {
    $value = $key.GetValue("Path", $null, [Microsoft.Win32.RegistryValueOptions]::DoNotExpandEnvironmentNames)
    if ($null -eq $value) { return $null }
    $kind = $key.GetValueKind("Path")
    return [pscustomobject]@{ Value = $value; Kind = $kind }
  } finally {
    $key.Dispose()
  }
}

function Send-PortableEnvironmentChange() {
  try {
    if (-not ("FrameCompareEnvironmentChange" -as [type])) {
      Add-Type @"
using System;
using System.Runtime.InteropServices;
public static class FrameCompareEnvironmentChange {
    [DllImport("user32.dll", CharSet = CharSet.Unicode)]
    public static extern IntPtr SendMessageTimeout(
        IntPtr window, uint message, UIntPtr wParam, string lParam,
        uint flags, uint timeoutMilliseconds, out UIntPtr result);
}
"@
    }
    # HWND_BROADCAST, WM_SETTINGCHANGE, SMTO_ABORTIFHUNG.
    $result = [UIntPtr]::Zero
    $null = [FrameCompareEnvironmentChange]::SendMessageTimeout(
      [IntPtr]0xffff, 0x001a, [UIntPtr]::Zero, "Environment", 0x0002, 1000, [ref]$result
    )
  } catch {
    Write-Warning "Could not notify running applications of the user Path change: $($_.Exception.Message)"
  }
}

function Set-PortableUserPath($State) {
  $key = [Microsoft.Win32.Registry]::CurrentUser.CreateSubKey("Environment")
  try {
    if ($null -eq $State) { $key.DeleteValue("Path", $false) }
    else { $key.SetValue("Path", $State.Value, $State.Kind) }
  } finally {
    $key.Dispose()
  }
  Send-PortableEnvironmentChange
}

function Test-PortableUserPathEqual($Left, $Right) {
  if ($null -eq $Left -or $null -eq $Right) {
    return ($null -eq $Left -and $null -eq $Right)
  }
  if ($Left.Kind -ne $Right.Kind -or $Left.Value -isnot [string] -or $Right.Value -isnot [string]) {
    return $false
  }
  return [string]::Equals($Left.Value, $Right.Value, [StringComparison]::Ordinal)
}

function Update-PortableUserPath([string]$BinDir, [switch]$Remove, [hashtable]$Changes) {
  $original = Get-PortableUserPath
  if ($null -eq $original) {
    if ($Remove) { return }
    $updated = [pscustomobject]@{ Value = $BinDir; Kind = [Microsoft.Win32.RegistryValueKind]::String }
  } else {
    # Rollback can observe another writer's registry kind. Only prospective
    # PATH edits require a value that can be interpreted as a path list.
    if ($original.Kind -notin @([Microsoft.Win32.RegistryValueKind]::String, [Microsoft.Win32.RegistryValueKind]::ExpandString)) {
      throw "The user Path registry value has unsupported type: $($original.Kind)"
    }
    $normalizedBinDir = ConvertTo-NormalizedPathEntry $BinDir
    $hasEntry = $false
    $entries = @(foreach ($entry in ($original.Value -split ";")) {
      $comparison = $entry
      if ($original.Kind -eq [Microsoft.Win32.RegistryValueKind]::ExpandString) {
        $comparison = [Environment]::ExpandEnvironmentVariables($comparison)
      }
      if ((ConvertTo-NormalizedPathEntry $comparison) -eq $normalizedBinDir) {
        $keep = !$Remove -and !$hasEntry
        $hasEntry = $true
        if (!$keep) { continue }
      }
      $entry
    })
    if (!$Remove -and !$hasEntry) {
      if ($original.Value.Length -eq 0) { $entries = @() }
      $entries += $BinDir
    }
    $updated = [pscustomobject]@{ Value = ($entries -join ";"); Kind = $original.Kind }
    if (Test-PortableUserPathEqual $original $updated) { return }
  }
  if ($null -ne $Changes) {
    $Changes.OriginalPath = $original
    $Changes.CandidatePath = $updated
  }
  Set-PortableUserPath $updated
}

function Set-PortableRegistration(
  [string]$BundleRoot, [string]$StateDirectory, [string]$PointerPath, [byte[]]$CandidatePointer,
  [hashtable]$Changes
) {
  $binDir = Join-Path (Split-Path -Parent $StateDirectory) "bin"
  Assert-NoReparsePointAncestor -Path $binDir -Label "Installed shims"
  $shimSource = Join-Path $BundleRoot "shim"
  $shims = @(foreach ($name in Get-PortableShimNames) {
    $source = Join-Path $shimSource $name
    $target = Join-Path $binDir $name
    Assert-NoReparsePointAncestor -Path $source -Label "Bundle shim"
    Assert-NoReparsePointAncestor -Path $target -Label "Installed shim"
    if (!(Test-Path -LiteralPath $source -PathType Leaf)) {
      throw "Shim file is missing: $source"
    }
    [pscustomobject]@{
      Path = $target
      OriginalBytes = (Read-OptionalPortableFile $target)
      WrittenBytes = [IO.File]::ReadAllBytes($source)
    }
  })

  [IO.Directory]::CreateDirectory($binDir) | Out-Null
  foreach ($shim in $shims) {
    $Changes.Files.Add($shim)
    if (Test-PortableBytesEqual $shim.OriginalBytes $shim.WrittenBytes) { continue }
    $installed = Get-OptionalPortableRegularFile $shim.Path
    if ($null -ne $installed) { Clear-PortableReadOnly $installed }
    Write-PortableFile -Path $shim.Path -Bytes $shim.WrittenBytes
  }
  $Changes.PointerWriteStarted = $true
  Write-PortableFile -Path $PointerPath -Bytes $CandidatePointer

  $portableConfigToml = Join-Path $StateDirectory "config.toml"
  if (!(Test-Path -LiteralPath $portableConfigToml)) {
    $bundleConfigToml = Join-Path (Join-Path $BundleRoot "config") "config.toml"
    if (Test-Path -LiteralPath $bundleConfigToml) {
      $fallback = [IO.File]::ReadAllBytes($bundleConfigToml)
    } else {
      $defaultPortableConfigToml = @"
[paths]
input_dir = "comparison_videos"
generated_dir = "generated"
config_dir = "config"
"@
      $fallback = [Text.Encoding]::UTF8.GetBytes($defaultPortableConfigToml)
    }
    Assert-NoReparsePointAncestor -Path $portableConfigToml -Label "Fallback config"
    $originalFallback = Read-OptionalPortableFile $portableConfigToml
    $Changes.Files.Add([pscustomobject]@{ Path = $portableConfigToml; OriginalBytes = $originalFallback; WrittenBytes = $fallback })
    if (!(Test-PortableBytesEqual $originalFallback $fallback)) {
      Write-PortableFile -Path $portableConfigToml -Bytes $fallback -NewOnly
    }
  }

  Update-PortableUserPath -BinDir $binDir -Changes $Changes
}

function Test-PortableBytesEqual([byte[]]$Left, [byte[]]$Right) {
  if ($null -eq $Left -or $null -eq $Right) {
    return ($null -eq $Left -and $null -eq $Right)
  }
  return [Collections.StructuralComparisons]::StructuralEqualityComparer.Equals($Left, $Right)
}

function Restore-PortableFile([string]$Path, [byte[]]$Bytes) {
  Assert-NoReparsePointAncestor -Path $Path -Label "Registration recovery"
  if ($null -eq $Bytes) { [IO.File]::Delete($Path) }
  else { Write-PortableFile -Path $Path -Bytes $Bytes }
}

function Restore-PortableRegistration(
  [string]$PointerPath, [byte[]]$OriginalPointer, [byte[]]$CandidatePointer, [hashtable]$Changes
) {
  Assert-NoReparsePointAncestor -Path $PointerPath -Label "Install state"
  $active = Read-OptionalPortableFile $PointerPath
  if (!(Test-PortableBytesEqual $active $OriginalPointer)) {
    if (!$Changes.PointerWriteStarted -or !(Test-PortableBytesEqual $active $CandidatePointer)) {
      throw "Pointer changed unexpectedly during activation; refusing data reversal."
    }
    Restore-PortableFile -Path $PointerPath -Bytes $OriginalPointer
  }

  for ($index = $Changes.Files.Count - 1; $index -ge 0; $index--) {
    $file = $Changes.Files[$index]
    try {
      Assert-NoReparsePointAncestor -Path $file.Path -Label "Registration recovery"
      $currentBytes = Read-OptionalPortableFile $file.Path
    } catch {
      Write-Warning "Registration rollback conflict: could not verify $($file.Path): $($_.Exception.Message)"
      continue
    }
    if (Test-PortableBytesEqual $currentBytes $file.OriginalBytes) { continue }
    if (Test-PortableBytesEqual $currentBytes $file.WrittenBytes) {
      Restore-PortableFile -Path $file.Path -Bytes $file.OriginalBytes
    } else {
      Write-Warning "Registration rollback conflict: preserving changed file $($file.Path)"
    }
  }
  if ($null -ne $Changes.CandidatePath -and (Test-PortableUserPathEqual (Get-PortableUserPath) $Changes.CandidatePath)) {
    Set-PortableUserPath $Changes.OriginalPath
  }
}

function Assert-PortableLauncherVersion([string]$Launcher) {
  $versionTimeoutMs = 120000
  $stdout = $null
  $stderr = $null
  $probe = $null
  try {
    $stdout = [IO.Path]::GetTempFileName()
    $stderr = [IO.Path]::GetTempFileName()
    # Use the same interpreter edition as the installer and the entrypoint used by the shim.
    $shell = if ($PSVersionTable.PSEdition -eq "Desktop") { "powershell.exe" } else { "pwsh.exe" }
    $arguments = '-NoProfile -ExecutionPolicy Bypass -File "{0}" version' -f $Launcher
    $probe = Start-Process -FilePath (Join-Path $PSHOME $shell) -ArgumentList $arguments `
      -PassThru -NoNewWindow -RedirectStandardOutput $stdout -RedirectStandardError $stderr
    $null = $probe.Handle
    if (!$probe.WaitForExit($versionTimeoutMs)) {
      throw "Version probe timed out after $versionTimeoutMs ms."
    }
    if ($probe.ExitCode -ne 0 -or !([IO.File]::ReadAllLines($stdout) -cmatch '^frame-compare ')) {
      throw "Expected exit code 0 and a line starting with 'frame-compare ' (exit code: $($probe.ExitCode))."
    }
  } finally {
    try {
      if ($null -ne $probe -and !$probe.HasExited) {
        $taskkill = Join-Path ([Environment]::SystemDirectory) "taskkill.exe"
        & $taskkill /T /F /PID $probe.Id | Out-Null
        if (!$probe.WaitForExit(5000)) { throw "Could not terminate version probe process $($probe.Id)." }
      }
    } finally {
      if ($null -ne $probe) { $probe.Dispose() }
      if ($null -ne $stdout) { [IO.File]::Delete($stdout) }
      if ($null -ne $stderr) { [IO.File]::Delete($stderr) }
    }
  }
}

function Invoke-PortableActivation(
  [string]$BundleRoot, [string]$StateDirectory,
  [ValidateSet("Move", "Leave")][string]$UserData = "Move",
  [IO.FileStream]$ActivationLock = $null
) {
  $BundleRoot = ConvertTo-PortableBundlePath $BundleRoot
  Assert-NoReparsePointAncestor -Path $BundleRoot -Label "New bundle"
  $installRoot = ConvertTo-PortableBundlePath (Split-Path -Parent $StateDirectory)
  $managedPaths = @((Join-Path $installRoot "bin"), (ConvertTo-PortableBundlePath $StateDirectory))
  foreach ($managedPath in $managedPaths) {
    if ($BundleRoot -eq $installRoot -or $BundleRoot -eq $managedPath -or
        (Test-PathWithin $BundleRoot $managedPath) -or (Test-PathWithin $managedPath $BundleRoot)) {
      throw "Bundle must not overlap the Frame Compare install root: $BundleRoot (install root: $installRoot)"
    }
  }

  $launcher = Join-Path $BundleRoot "frame-compare.ps1"
  Assert-NoReparsePointAncestor -Path $launcher -Label "Bundle launcher"
  if (!(Test-Path -LiteralPath $launcher -PathType Leaf)) {
    throw "Bundle launcher not found: $launcher"
  }

  $ownsLock = $null -eq $ActivationLock
  $lockPath = Join-Path $StateDirectory "source-install.lock"
  if ($ownsLock) { $ActivationLock = Open-PortableActivationLock $StateDirectory }
  elseif (!$ActivationLock.CanWrite -or $ActivationLock.SafeFileHandle.IsClosed -or
          ![string]::Equals($ActivationLock.Name, $lockPath, [StringComparison]::OrdinalIgnoreCase)) {
    throw "The supplied activation lock does not own $lockPath"
  }

  try {
    Assert-NoPendingPortableMigration $StateDirectory
    $bundleInfo = Join-Path $BundleRoot "bundle_info.json"
    Assert-NoReparsePointAncestor -Path $bundleInfo -Label "Bundle runtime identity"
    if (!(Test-Path -LiteralPath $bundleInfo -PathType Leaf)) {
      throw "Bundle runtime identity not found: $bundleInfo"
    }
    try {
      Assert-PortableLauncherVersion $launcher
    } catch {
      throw "Bundle launcher version check failed for ${launcher}: $($_.Exception.Message)"
    }

    $pointerPath = Join-Path $StateDirectory "config.json"
    $pendingMigrationPath = Join-Path $StateDirectory "source-migration.pending.json"
    Assert-NoReparsePointAncestor -Path $pointerPath -Label "Install state"
    $originalPointer = Read-OptionalPortableFile $pointerPath
    $previousBundle = Get-PortableMoveSource -PointerBytes $originalPointer -BundleRoot $BundleRoot
    $candidatePointer = [Text.Encoding]::UTF8.GetBytes((@{
      schema_version = 1
      install_type = "portable_bundle"
      bundle_path = $BundleRoot
    } | ConvertTo-Json))

    $folders = @()
    if ($UserData -eq "Move" -and $null -ne $previousBundle) {
      $folders = @(foreach ($name in @("config", "comparison_videos", "generated")) {
        $source = Join-Path $previousBundle $name
        if ((Get-PortableUserFolderState $source) -eq "populated") {
          [pscustomobject]@{ Name = $name; Source = $source; Target = (Join-Path $BundleRoot $name) }
        }
      })
    }

    $changes = @{
      Files = [Collections.Generic.List[object]]::new()
      PointerWriteStarted = $false
      CandidatePath = $null
      OriginalPath = $null
    }
    $placeholders = [Collections.Generic.List[string]]::new()
    $markerWritten = $false
    $registrationStarted = $false
    $committed = $false
    $failure = $null
    try {
      if ($folders.Count -gt 0) {
        foreach ($folder in $folders) {
          if ((Get-PortableUserFolderState $folder.Target) -eq "populated") { throw "New user folder is occupied: $($folder.Target)" }
        }
        Write-PendingMigrationMarker -Path $pendingMigrationPath -PreviousBundle $previousBundle -BundleRoot $BundleRoot -Folders $folders -PointerBytes $originalPointer
        $markerWritten = $true
        foreach ($folder in $folders) {
          if ((Get-PortableUserFolderState $folder.Source) -ne "populated") { throw "User folder changed: $($folder.Source)" }
          $targetState = Get-PortableUserFolderState $folder.Target
          if ($targetState -eq "populated") { throw "New user folder is occupied: $($folder.Target)" }
          if ($targetState -eq "empty") {
            $placeholders.Add($folder.Target)
            [IO.Directory]::Delete($folder.Target)
          }
          try { [IO.Directory]::Move($folder.Source, $folder.Target) }
          catch [System.Management.Automation.PipelineStoppedException] { throw }
          catch { throw "Cannot move $($folder.Source) to $($folder.Target). Move requires same-volume renames; use -UserData Leave and relocate data manually. $($_.Exception.Message)" }
        }
      } elseif ($UserData -eq "Leave" -and $null -ne $previousBundle) {
        Write-Warning "User data left in previous bundle $previousBundle. The shim may select an older AppData state config if the new bundle has no config\config.toml."
      }

      $registrationStarted = $true
      if (!(Test-PortableBytesEqual (Read-OptionalPortableFile $pointerPath) $originalPointer)) {
        throw "Pointer changed unexpectedly before registration."
      }
      Set-PortableRegistration -BundleRoot $BundleRoot -StateDirectory $StateDirectory -PointerPath $pointerPath -CandidatePointer $candidatePointer -Changes $changes
      $committed = $true
    } catch {
      $failure = $_
    } finally {
      if (!$committed -and ($markerWritten -or $registrationStarted)) {
        try {
          Restore-PortableRegistration -PointerPath $pointerPath -OriginalPointer $originalPointer -CandidatePointer $candidatePointer -Changes $changes
          if ($markerWritten) {
            $unreconciled = @()
            for ($index = $folders.Count - 1; $index -ge 0; $index--) {
              $folder = $folders[$index]
              $location = Get-PortableMigrationLocation $folder
              if ($location.State -eq "in place") { continue }
              if ($location.State -eq "moved") {
                [IO.Directory]::Move($folder.Target, $folder.Source)
                continue
              }
              $unreconciled += $folder.Name
            }
            foreach ($placeholder in $placeholders) {
              Assert-NoReparsePointAncestor -Path $placeholder -Label "User data placeholder"
              [IO.Directory]::CreateDirectory($placeholder) | Out-Null
            }
            if ($unreconciled.Count -gt 0) {
              throw "Could not reconcile user folders: $($unreconciled -join ', ')"
            }
            Remove-Item -LiteralPath $pendingMigrationPath -Force
          }
        } catch {
          Write-RecoveryLocations -PointerPath $pointerPath -Folders $folders
          $reason = if ($null -ne $failure) { $failure.Exception.Message } else { "Activation interrupted" }
          throw "Installation failed: $reason. Recovery failed: $($_.Exception.Message)"
        }
      }
    }
    if ($null -ne $failure) { throw $failure }

    Remove-LegacyUpdaterLeaves -StateDirectory $StateDirectory

    if ($markerWritten) {
      try { Remove-Item -LiteralPath $pendingMigrationPath -Force }
      catch { throw "The new installation is active at $BundleRoot, but the pending migration marker could not be removed: $pendingMigrationPath. $($_.Exception.Message)" }
    }
    if ($null -ne $previousBundle) {
      Write-Host "Previous bundle retained: $previousBundle"
    }
    if ($folders.Count -gt 0) {
      Write-Host "Moved user data to $BundleRoot. Path-keyed caches recompute once; absolute paths in your config were not rewritten."
    }
    Write-Host "Installed Frame Compare shim."
    Write-Host "Open a new terminal, then run: frame-compare --help"
  } finally {
    if ($ownsLock) { $ActivationLock.Dispose() }
  }
}
