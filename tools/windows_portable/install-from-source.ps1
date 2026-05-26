Param(
  [Parameter(Mandatory = $false)]
  [string]$ManifestPath = (Join-Path $PSScriptRoot "manifest.windows-x64.json"),

  [Parameter(Mandatory = $false)]
  [string]$OutDir = "",

  [Parameter(Mandatory = $false)]
  [string]$CacheDir = "",

  [Parameter(Mandatory = $false)]
  [switch]$SkipSync
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

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

Ensure-UvOnPath

if ([string]::IsNullOrWhiteSpace($OutDir)) {
  $OutDir = Join-Path $repoRoot "dist\\frame-compare-portable-win-x64"
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

Push-Location $repoRoot
try {
  if (-not $SkipSync) {
    Write-Host "Syncing dev dependencies (frozen)..."
    uv sync --group dev --frozen
    Assert-LastExitCode -Label "uv sync"
  }

  Write-Host "Building portable bundle..."
  & $buildScript -ManifestPath $manifestFullPath -OutDir $outDirFullPath -CacheDir $cacheDirFullPath -RepoRoot $repoRoot
  if ($null -eq $LASTEXITCODE) {
    throw "build_portable.ps1 terminated unexpectedly."
  }
  Assert-LastExitCode -Label "build_portable.ps1"

  $installScript = Join-Path $outDirFullPath "install.ps1"
  if (!(Test-Path -LiteralPath $installScript)) {
    throw "Bundle installer not found: $installScript"
  }

  Write-Host "Installing shim from built bundle..."
  & $installScript
  if ($null -eq $LASTEXITCODE) {
    throw "install.ps1 terminated unexpectedly."
  }
  Assert-LastExitCode -Label "install.ps1"
} finally {
  Pop-Location
}

Write-Host ""
Write-Host "Source install complete."
Write-Host "Open a new terminal, then run: frame-compare --help"
