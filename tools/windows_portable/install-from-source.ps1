$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

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

if (-not $IsWindows) {
  throw "install-from-source.ps1 is supported on Windows only."
}

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\\..")).Path
$buildScript = Join-Path $PSScriptRoot "build_portable.ps1"
if (!(Test-Path -LiteralPath $buildScript)) {
  throw "Build script not found: $buildScript"
}

if (!(Get-Command uv -ErrorAction SilentlyContinue)) {
  throw "uv is required on PATH. Install uv first: https://docs.astral.sh/uv/getting-started/installation/"
}

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

  $installCmd = Join-Path $outDirFullPath "install.cmd"
  if (!(Test-Path -LiteralPath $installCmd)) {
    throw "Bundle installer not found: $installCmd"
  }

  Write-Host "Installing shim from built bundle..."
  & $installCmd
  if ($null -eq $LASTEXITCODE) {
    throw "install.cmd terminated unexpectedly."
  }
  Assert-LastExitCode -Label "install.cmd"
} finally {
  Pop-Location
}

Write-Host ""
Write-Host "Source install complete."
Write-Host "Open a new terminal, then run: frame-compare --help"
