Param(
  [Parameter(Mandatory = $false)]
  [string]$ManifestPath = (Join-Path $PSScriptRoot "manifest.windows-x64.json"),

  [Parameter(Mandatory = $false)]
  [string]$OutDir = "",

  [Parameter(Mandatory = $false)]
  [string]$CacheDir = "",

  [Parameter(Mandatory = $false)]
  [switch]$SkipSync,

  [ValidateSet("Move", "Leave")]
  [string]$UserData = "Move"
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

if ($PSVersionTable.PSVersion.Major -lt 7) {
  throw "PowerShell 7 or newer is required to build Frame Compare from source. Run this installer with pwsh or install PowerShell 7, then rerun install.cmd."
}

function Assert-LastExitCode([string]$Label) {
  if ($LASTEXITCODE -ne 0) {
    throw "$Label failed with exit code $LASTEXITCODE"
  }
}

function Resolve-FullPath([string]$PathValue, [string]$BaseDir) {
  if ([System.IO.Path]::IsPathRooted($PathValue)) {
    return [System.IO.Path]::GetFullPath($PathValue)
  }
  return [System.IO.Path]::GetFullPath((Join-Path $BaseDir $PathValue))
}

function Update-ProcessPathFromRegistry() {
  $machine = [Environment]::GetEnvironmentVariable("Path", "Machine")
  $user = [Environment]::GetEnvironmentVariable("Path", "User")
  if ($null -eq $machine) { $machine = "" }
  if ($null -eq $user) { $user = "" }
  $env:Path = @($machine, $user) -join ";"
}

function Add-ToProcessPathIfMissing([string]$CandidateDir) {
  if ([string]::IsNullOrWhiteSpace($CandidateDir)) {
    return
  }
  if (!(Test-Path -LiteralPath $CandidateDir)) {
    return
  }
  if ($env:Path -like "*$CandidateDir*") {
    return
  }
  $env:Path = "$CandidateDir;$env:Path"
}

function Get-UserScriptsDir([string]$PythonExe) {
  try {
    $scripts = & $PythonExe -c "import sysconfig; print(sysconfig.get_path('scripts', scheme='nt_user'))"
    if ($LASTEXITCODE -ne 0) {
      return $null
    }
    if ([string]::IsNullOrWhiteSpace($scripts)) {
      return $null
    }
    return $scripts.Trim()
  } catch {
    return $null
  }
}

function Ensure-UvOnPath() {
  if (Get-Command uv -ErrorAction SilentlyContinue) {
    return
  }

  Write-Host "uv not found on PATH. Attempting automatic install..."

  if (Get-Command winget -ErrorAction SilentlyContinue) {
    $wingetIds = @(
      "astral-sh.uv",
      "AstralSh.uv",
      "astral.uv",
      "Astral.uv"
    )

    foreach ($wingetId in $wingetIds) {
      Write-Host "Attempting uv install via winget id '$wingetId'..."
      & winget install --id $wingetId -e --source winget --accept-source-agreements --accept-package-agreements
      if ($LASTEXITCODE -eq 0) {
        Write-Host "winget install succeeded with id '$wingetId'."
        Update-ProcessPathFromRegistry
        $wingetLinks = Join-Path $env:LOCALAPPDATA "Microsoft\\WinGet\\Links"
        Add-ToProcessPathIfMissing -CandidateDir $wingetLinks
        break
      }
      Write-Host "winget install failed for id '$wingetId' (exit code $LASTEXITCODE)."
    }
  } else {
    Write-Host "winget not found; skipping winget uv install attempts."
  }

  if (!(Get-Command uv -ErrorAction SilentlyContinue)) {
    if (Get-Command py -ErrorAction SilentlyContinue) {
      Write-Host "Attempting uv install via py -m pip install --user uv..."
      & py -m pip install --user uv
      if ($LASTEXITCODE -eq 0) {
        Write-Host "pip install via py succeeded."
        Update-ProcessPathFromRegistry
        $userScripts = Get-UserScriptsDir -PythonExe "py"
        Add-ToProcessPathIfMissing -CandidateDir $userScripts
      } else {
        Write-Host "pip install via py failed (exit code $LASTEXITCODE)."
      }
    } elseif (Get-Command python -ErrorAction SilentlyContinue) {
      Write-Host "Attempting uv install via python -m pip install --user uv..."
      & python -m pip install --user uv
      if ($LASTEXITCODE -eq 0) {
        Write-Host "pip install via python succeeded."
        Update-ProcessPathFromRegistry
        $userScripts = Get-UserScriptsDir -PythonExe "python"
        Add-ToProcessPathIfMissing -CandidateDir $userScripts
      } else {
        Write-Host "pip install via python failed (exit code $LASTEXITCODE)."
      }
    } else {
      Write-Host "Neither py nor python was found; skipping pip-based uv install attempts."
    }
  }

  if (!(Get-Command uv -ErrorAction SilentlyContinue)) {
    throw @"
uv is still not available on PATH.
Try one of the following commands, then re-run install.cmd:
  winget install --id astral-sh.uv -e --source winget
  py -m pip install --user uv
Docs: https://docs.astral.sh/uv/getting-started/installation/
"@
  }
}

if ([System.Environment]::OSVersion.Platform -ne [System.PlatformID]::Win32NT) {
  throw "install-from-source.ps1 is supported on Windows only."
}

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\\..")).Path
$buildScript = Join-Path $PSScriptRoot "build_portable.ps1"
if (!(Test-Path -LiteralPath $buildScript)) {
  throw "Build script not found: $buildScript"
}

if ([string]::IsNullOrWhiteSpace($OutDir)) {
  $OutDir = Join-Path $repoRoot ("dist\frame-compare-portable-win-x64-" + [DateTime]::UtcNow.ToString("yyyyMMdd-HHmmss") + "Z")
}
if ([string]::IsNullOrWhiteSpace($CacheDir)) {
  $CacheDir = Join-Path $repoRoot ".portable_cache"
}

$manifestFullPath = Resolve-FullPath -PathValue $ManifestPath -BaseDir $repoRoot
$outDirFullPath = Resolve-FullPath -PathValue $OutDir -BaseDir $repoRoot
$cacheDirFullPath = Resolve-FullPath -PathValue $CacheDir -BaseDir $repoRoot

if (!(Test-Path -LiteralPath $manifestFullPath)) {
  throw "Manifest not found: $manifestFullPath"
}

. (Join-Path $PSScriptRoot "path_safety.ps1")
$pointerPath = Join-Path $env:LOCALAPPDATA "Programs\FrameCompare\state\config.json"
$stateDirectory = Split-Path -Parent $pointerPath
$activationLockPath = Join-Path $stateDirectory "source-install.lock"
$pendingMigrationPath = Join-Path $stateDirectory "source-migration.pending.json"

function Read-ActivePointerBundle() {
  try {
    $pointer = Get-Content -LiteralPath $pointerPath -Raw | ConvertFrom-Json
    if ($pointer -isnot [pscustomobject] -or
        ($pointer.schema_version -isnot [int] -and $pointer.schema_version -isnot [long]) -or
        $pointer.schema_version -ne 1 -or $pointer.install_type -ne "portable_bundle" -or
        $pointer.bundle_path -isnot [string] -or
        !([IO.Path]::IsPathFullyQualified($pointer.bundle_path))) {
      return $null
    }
    return [IO.Path]::TrimEndingDirectorySeparator([IO.Path]::GetFullPath($pointer.bundle_path))
  } catch { return $null }
}

function Write-PendingMigrationRefusal([string]$MarkerPath) {
  Write-Warning "A pending source migration marker was found: $MarkerPath"
  try {
    $pending = Get-Content -LiteralPath $MarkerPath -Raw | ConvertFrom-Json
    $previous = [IO.Path]::TrimEndingDirectorySeparator([IO.Path]::GetFullPath($pending.previous_bundle))
    $candidate = [IO.Path]::TrimEndingDirectorySeparator([IO.Path]::GetFullPath($pending.candidate_bundle))
    $active = Read-ActivePointerBundle
    $locations = @(foreach ($folder in @($pending.folders)) {
      $sourceExists = Test-Path -LiteralPath $folder.source
      $targetExists = Test-Path -LiteralPath $folder.target
      $sourceHasData = Test-NonEmptyDirectory $folder.source
      $targetHasData = Test-NonEmptyDirectory $folder.target
      $state = "conflict"
      if ($sourceHasData -and !$targetHasData) { $state = "in place" }
      elseif ($targetHasData -and !$sourceExists) { $state = "moved" }
      [pscustomobject]@{
        Name = $folder.name; Source = $folder.source; Target = $folder.target
        SourceExists = $sourceExists; TargetExists = $targetExists; State = $state
      }
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
      Write-Warning "The migration completed. User data is in the candidate bundle: $candidate"
      Write-Warning "It is safe to delete the pending migration marker: $MarkerPath"
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
      Write-Warning "Migration state conflict. Active pointer path: $pointerPath; normalized bundle: $active"
      try { Write-Warning "Current pointer value: $([IO.File]::ReadAllText($pointerPath))" }
      catch { Write-Warning "Current pointer value unavailable: $($_.Exception.Message)" }
      Write-Warning "Do not move anything until every path and the pointer have been checked by hand."
    }
  } catch {
    Write-Warning "Could not read pending migration details: $($_.Exception.Message)"
    Write-Warning "Check the marker and folder locations by hand before retrying installation."
  }
  Write-Warning "No automatic recovery was attempted."
}

function Read-PreviousBundle() {
  # A single byte snapshot owns both interpretation and rollback. An inaccessible
  # existing pointer is unsafe, whereas absent/malformed/stale state is a first install.
  try { $bytes = [IO.File]::ReadAllBytes($pointerPath) }
  catch [IO.FileNotFoundException] { return $null }
  catch [IO.DirectoryNotFoundException] { return $null }
  try {
    $pointer = [Text.Encoding]::UTF8.GetString($bytes).TrimStart([char]0xFEFF) | ConvertFrom-Json
    if ($pointer -isnot [pscustomobject] -or
        ($pointer.schema_version -isnot [int] -and $pointer.schema_version -isnot [long]) -or
        $pointer.schema_version -ne 1 -or $pointer.install_type -ne "portable_bundle" -or
        $pointer.bundle_path -isnot [string] -or
        !([IO.Path]::IsPathFullyQualified($pointer.bundle_path))) {
      return $null
    }
    $candidate = [IO.Path]::TrimEndingDirectorySeparator([IO.Path]::GetFullPath($pointer.bundle_path))
  } catch {
    # Decode/shape errors are malformed state, never partially enabled migration.
    return $null
  }
  if (!(Test-Path -LiteralPath $candidate -PathType Container) -or
      !(Test-Path -LiteralPath (Join-Path $candidate "bundle_info.json") -PathType Leaf) -or
      $candidate -eq [IO.Path]::TrimEndingDirectorySeparator($outDirFullPath)) {
    return $null
  }
  Assert-NoReparsePointAncestor -Path $candidate -Label "Previous bundle"
  if ((Test-PathWithin $outDirFullPath $candidate) -or
      (Test-PathWithin $candidate $outDirFullPath)) {
    throw "New bundle $outDirFullPath must not nest with previous bundle $candidate"
  }
  return [pscustomobject]@{ Bundle = $candidate; PointerBytes = $bytes }
}

Assert-NoReparsePointAncestor -Path $outDirFullPath -Label "New bundle"
Assert-NoReparsePointAncestor -Path $pointerPath -Label "Install state"
Assert-NoReparsePointAncestor -Path $stateDirectory -Label "Install state"
[IO.Directory]::CreateDirectory($stateDirectory) | Out-Null
Assert-NoReparsePointAncestor -Path $activationLockPath -Label "Activation lock"
# This pre-build read guards containment only. Never use it for migration/rollback
# after a long build: another installer may have activated a different bundle.
$null = Read-PreviousBundle
$previousBundle = $null
$previousPointerBytes = $null

function Test-NonEmptyDirectory([string]$Path) {
  if (!(Test-Path -LiteralPath $Path)) { return $false }
  if (!(Test-Path -LiteralPath $Path -PathType Container)) {
    throw "User data location is not a folder: $Path"
  }
  return @((Get-ChildItem -LiteralPath $Path -Force)).Count -gt 0
}

function Write-PreviousPointer() {
  $temporary = $pointerPath + ".restore-" + [Guid]::NewGuid().ToString("N")
  try {
    [IO.File]::WriteAllBytes($temporary, $previousPointerBytes)
    Move-Item -LiteralPath $temporary -Destination $pointerPath -Force
  } finally {
    if (Test-Path -LiteralPath $temporary) { Remove-Item -LiteralPath $temporary -Force }
  }
}

function Get-RecoveryPathStatus([string]$Path) {
  try {
    if (Test-Path -LiteralPath $Path -ErrorAction Stop) { return "exists" }
    return "absent"
  } catch { return "status unavailable: $($_.Exception.Message)" }
}

function Write-RecoveryLocations([object[]]$Folders) {
  Write-Warning "Recovery stopped. Pointer: $pointerPath"
  try { Write-Warning ([IO.File]::ReadAllText($pointerPath)) }
  catch { Write-Warning "Pointer contents unavailable: $($_.Exception.Message)" }
  foreach ($folder in $Folders) {
    Write-Warning "User folder $($folder.Name): previous=$($folder.Source) ($(Get-RecoveryPathStatus $folder.Source)); new=$($folder.Target) ($(Get-RecoveryPathStatus $folder.Target))"
  }
  Write-Warning "No remaining user folders were deleted. Recover these paths before retrying installation."
}

function Write-PendingMigrationMarker([object[]]$Folders) {
  $record = [pscustomobject]@{
    previous_bundle = [IO.Path]::GetFullPath($previousBundle)
    candidate_bundle = [IO.Path]::GetFullPath($outDirFullPath)
    folders = @($Folders | ForEach-Object {
        [pscustomobject]@{
          name = $_.Name
          source = [IO.Path]::GetFullPath($_.Source)
          target = [IO.Path]::GetFullPath($_.Target)
        }
      })
    pointer_bytes_base64 = [Convert]::ToBase64String($previousPointerBytes)
  }
  $temporary = $pendingMigrationPath + ".tmp-" + [Guid]::NewGuid().ToString("N")
  try {
    $utf8NoBom = New-Object System.Text.UTF8Encoding($false)
    [IO.File]::WriteAllText($temporary, ($record | ConvertTo-Json -Depth 4), $utf8NoBom)
    [IO.File]::Move($temporary, $pendingMigrationPath)
  } finally {
    if (Test-Path -LiteralPath $temporary) { Remove-Item -LiteralPath $temporary -Force }
  }
}

function Remove-PendingMigrationMarker() {
  if (Test-Path -LiteralPath $pendingMigrationPath) {
    Remove-Item -LiteralPath $pendingMigrationPath -Force
  }
}

$folders = @()
$moved = [Collections.Generic.List[object]]::new()
$placeholders = [Collections.Generic.List[string]]::new()
$activationStarted = $false
$succeeded = $false
$activationLock = $null
$failure = $null
$recoveryFailure = $null
try {
  try {
    $activationLock = [IO.File]::Open($activationLockPath, [IO.FileMode]::OpenOrCreate, [IO.FileAccess]::ReadWrite, [IO.FileShare]::None)
  } catch {
    throw "Cannot own source-install activation lock $activationLockPath. Another source install may be activating; retry after it finishes. $($_.Exception.Message)"
  }

  if (Test-Path -LiteralPath $pendingMigrationPath) {
    Write-PendingMigrationRefusal -MarkerPath $pendingMigrationPath
    throw "A pending source migration must be repaired manually before another source install can run."
  }

  Push-Location $repoRoot
  try {
    Update-ProcessPathFromRegistry
    Ensure-UvOnPath
    if (-not $SkipSync) {
      Write-Host "Syncing dev dependencies (frozen)..."
      uv sync --group dev --frozen
      Assert-LastExitCode -Label "uv sync"
    }

    Write-Host "Building portable bundle..."
    & $buildScript -ManifestPath $manifestFullPath -OutDir $outDirFullPath -CacheDir $cacheDirFullPath -RepoRoot $repoRoot
    if ($null -eq $LASTEXITCODE) { throw "build_portable.ps1 terminated unexpectedly." }
    Assert-LastExitCode -Label "build_portable.ps1"
    $installScript = Join-Path $outDirFullPath "install.ps1"
    if (!(Test-Path -LiteralPath $installScript)) { throw "Bundle installer not found: $installScript" }

    # Re-read after the build AND after owning the activation boundary. Derive the
    # previous bundle and byte-exact rollback material from the same snapshot.
    $previous = Read-PreviousBundle
    if ($null -ne $previous) {
      $previousBundle = $previous.Bundle
      $previousPointerBytes = $previous.PointerBytes
    }

    if ($null -ne $previousBundle) {
      $folders = @(foreach ($name in @("config", "comparison_videos", "generated")) {
        $source = Join-Path $previousBundle $name
        if (Test-NonEmptyDirectory $source) {
          [pscustomobject]@{ Name = $name; Source = $source; Target = (Join-Path $outDirFullPath $name) }
        }
      })
    }
    if ($UserData -eq "Move") {
      # Check the whole set before the first rename. Directory.Move never falls back
      # to copy/delete across volumes (including mounted volumes).
      foreach ($folder in $folders) {
        if (!(Test-NonEmptyDirectory $folder.Source)) { throw "User folder changed: $($folder.Source)" }
        if (Test-NonEmptyDirectory $folder.Target) { throw "New user folder is occupied: $($folder.Target)" }
      }
      if ($folders.Count -gt 0) {
        Write-PendingMigrationMarker -Folders $folders
        foreach ($folder in $folders) {
          if (Test-Path -LiteralPath $folder.Target) {
            if (Test-NonEmptyDirectory $folder.Target) { throw "New user folder is occupied: $($folder.Target)" }
            [IO.Directory]::Delete($folder.Target)
            $placeholders.Add($folder.Target)
          }
          try { [IO.Directory]::Move($folder.Source, $folder.Target) }
          catch { throw "Cannot move $($folder.Source) to $($folder.Target). Move requires same-volume renames; use -UserData Leave and relocate data manually. $($_.Exception.Message)" }
          $moved.Add($folder)
        }
      }
    } elseif ($folders.Count -gt 0) {
      Write-Warning "User data left in previous bundle ${previousBundle}: $($folders.Name -join ', '). The shim may select an older AppData state config if the new bundle has no config\config.toml."
    }

    Write-Host "Installing shim from built bundle..."
    $activationStarted = $true
    & $installScript -ActivationLock $activationLock
    if ($null -eq $LASTEXITCODE) { throw "install.ps1 terminated unexpectedly." }
    Assert-LastExitCode -Label "install.ps1"
    $succeeded = $true
  } catch {
    $failure = $_
  } finally {
    $recoveryFailure = $null
    try {
      if ($succeeded) {
        Remove-PendingMigrationMarker
      } else {
        if ($activationStarted -and $null -ne $previousBundle) {
          # Activation can throw after replacing the pointer but before finishing PATH.
          $active = Get-Content -LiteralPath $pointerPath -Raw | ConvertFrom-Json
          if ([IO.Path]::TrimEndingDirectorySeparator([IO.Path]::GetFullPath($active.bundle_path)) -eq
              [IO.Path]::TrimEndingDirectorySeparator($outDirFullPath)) {
            Write-PreviousPointer
          } elseif ([IO.Path]::TrimEndingDirectorySeparator([IO.Path]::GetFullPath($active.bundle_path)) -ne $previousBundle) {
            throw "Pointer changed unexpectedly during activation; refusing data reversal."
          }
        }
        for ($index = $moved.Count - 1; $index -ge 0; $index--) {
          $folder = $moved[$index]
          [IO.Directory]::Move($folder.Target, $folder.Source)
        }
        foreach ($placeholder in $placeholders) {
          if (!(Test-Path -LiteralPath $placeholder)) { [IO.Directory]::CreateDirectory($placeholder) | Out-Null }
        }
        if ($activationStarted -and $null -ne $previousBundle) {
          & (Join-Path $previousBundle "install.ps1") -ActivationLock $activationLock
          Assert-LastExitCode -Label "previous bundle install.ps1 (shim restoration)"
          # Preserve the original pointer bytes even if reinstall serialized it differently.
          Write-PreviousPointer
        }
        Remove-PendingMigrationMarker
      }
    } catch {
      $recoveryFailure = $_
      Write-RecoveryLocations -Folders $folders
    } finally {
      Pop-Location
    }
  }
  if ($null -ne $failure) {
    if ($null -ne $recoveryFailure) {
      throw "Installation failed: $($failure.Exception.Message). Recovery failed: $($recoveryFailure.Exception.Message)"
    }
    throw $failure
  }
  if ($null -ne $recoveryFailure) {
    throw "Source install completed, but the pending migration marker could not be removed: $($recoveryFailure.Exception.Message)"
  }
} finally {
  if ($null -ne $activationLock) { $activationLock.Dispose() }
}

Write-Host ""
Write-Host "Source install complete."
if ($null -ne $previousBundle) {
  Write-Host "Previous bundle retained: $previousBundle. Remove it manually only after accepting the new installation."
  if ($UserData -eq "Move" -and $moved.Count -gt 0) {
    Write-Host "Moved user data to $outDirFullPath. Path-keyed caches recompute once; absolute paths in your config were not rewritten."
  }
}
Write-Host "Open a new terminal, then run: frame-compare --help"
