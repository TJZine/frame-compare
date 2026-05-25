Param(
  [Parameter(Mandatory = $false)]
  [string]$ManifestPath = (Join-Path $PSScriptRoot "manifest.windows-x64.json"),

  [Parameter(Mandatory = $false)]
  [string]$OutDir = (Join-Path $PWD "dist\\frame-compare-portable-win-x64"),

  [Parameter(Mandatory = $false)]
  [string]$CacheDir = (Join-Path $PWD ".portable_cache"),

  [Parameter(Mandatory = $false)]
  [string]$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\\..")).Path,

  [Parameter(Mandatory = $false)]
  [switch]$RequireReleasePublicKey
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest
$PSNativeCommandUseErrorActionPreference = $true

. (Join-Path $PSScriptRoot "version_utils.ps1")

function Ensure-Directory([string]$Path) {
  if (!(Test-Path -LiteralPath $Path)) {
    New-Item -ItemType Directory -Path $Path | Out-Null
  }
}

function Get-Manifest() {
  if (!(Test-Path -LiteralPath $ManifestPath)) {
    throw "Manifest not found: $ManifestPath"
  }
  return (Get-Content -LiteralPath $ManifestPath -Raw | ConvertFrom-Json)
}

function Get-OptionalStringProperty([object]$Object, [string]$Name) {
  if ($null -eq $Object) {
    return ""
  }
  $prop = $Object.PSObject.Properties[$Name]
  if ($null -eq $prop -or $null -eq $prop.Value) {
    return ""
  }
  return [string]$prop.Value
}

function Get-OptionalProperty([object]$Object, [string]$Name) {
  if ($null -eq $Object) {
    return $null
  }
  $prop = $Object.PSObject.Properties[$Name]
  if ($null -eq $prop) {
    return $null
  }
  return $prop.Value
}

function Get-RequiredStringProperty([object]$Object, [string]$Name, [string]$Context) {
  $value = Get-OptionalStringProperty -Object $Object -Name $Name
  if ($value -eq "") {
    throw "$Context is missing required property '$Name'"
  }
  return $value
}

function Get-RequiredProperty([object]$Object, [string]$Name, [string]$Context) {
  $value = Get-OptionalProperty -Object $Object -Name $Name
  if ($null -eq $value) {
    throw "$Context is missing required property '$Name'"
  }
  return $value
}

function Assert-Sha256([string]$FilePath, [string]$ExpectedHex) {
  $hash = (Get-FileHash -Algorithm SHA256 -LiteralPath $FilePath).Hash.ToLowerInvariant()
  if ($hash -ne $ExpectedHex.ToLowerInvariant()) {
    throw "SHA256 mismatch for $FilePath`nExpected: $ExpectedHex`nActual:   $hash"
  }
}

function Assert-LastExitCode([string]$CommandLabel) {
  if ($LASTEXITCODE -ne 0) {
    throw "$CommandLabel failed with exit code $LASTEXITCODE"
  }
}

function Assert-ReleasePublicKey() {
  $validator = Join-Path $PSScriptRoot "validate_update_public_key.ps1"
  $publicKey = Join-Path $PSScriptRoot "update_public_key.xml"
  & $validator -PublicKeyPath $publicKey
}

function Download-Artifact([pscustomobject]$Artifact) {
  $id = Get-RequiredStringProperty -Object $Artifact -Name "id" -Context "artifact"
  $url = Get-RequiredStringProperty -Object $Artifact -Name "url" -Context "artifact '$id'"
  $sha256 = Get-RequiredStringProperty -Object $Artifact -Name "sha256" -Context "artifact '$id'"

  $fileName = Split-Path -Leaf $url
  $dest = Join-Path $CacheDir $fileName

  if (Test-Path -LiteralPath $dest) {
    Assert-Sha256 -FilePath $dest -ExpectedHex $sha256
    return $dest
  }

  Write-Host "Downloading $id -> $fileName"
  try {
    Invoke-WebRequest -Uri $url -OutFile $dest | Out-Null
  } catch {
    if (Test-Path -LiteralPath $dest) {
      Remove-Item -Force -LiteralPath $dest
    }
    throw "Failed to download artifact '$id' from $url. The upstream artifact may have moved or expired; update $ManifestPath with a reachable URL and matching sha256. Original error: $($_.Exception.Message)"
  }
  Assert-Sha256 -FilePath $dest -ExpectedHex $sha256
  return $dest
}

function Expand-ArchiveFile([string]$ArchivePath, [string]$Destination) {
  if (Test-Path -LiteralPath $Destination) {
    Remove-Item -Recurse -Force -LiteralPath $Destination
  }
  Ensure-Directory -Path $Destination

  $extension = [System.IO.Path]::GetExtension($ArchivePath).ToLowerInvariant()
  if ($extension -eq ".zip" -or $extension -eq ".whl") {
    Expand-Archive -LiteralPath $ArchivePath -DestinationPath $Destination -Force
    return
  }
  if ($extension -eq ".7z") {
    if (Get-Command 7z -ErrorAction SilentlyContinue) {
      7z x -y "-o$Destination" $ArchivePath | Out-Null
      Assert-LastExitCode -CommandLabel "7z extract $ArchivePath"
      return
    }
    if (Get-Command tar -ErrorAction SilentlyContinue) {
      tar -xf $ArchivePath -C $Destination
      Assert-LastExitCode -CommandLabel "tar extract $ArchivePath"
      return
    }
    throw "7z or tar is required on PATH to extract .7z artifact: $ArchivePath"
  }

  throw "Unsupported archive extension '$extension' for $ArchivePath"
}

function Install-Artifact([string]$BundleRoot, [pscustomobject]$Artifact, [string]$DownloadedPath) {
  $artifactId = Get-RequiredStringProperty -Object $Artifact -Name "id" -Context "artifact"
  $install = Get-RequiredProperty -Object $Artifact -Name "install" -Context "artifact '$artifactId'"

  $type = Get-RequiredStringProperty -Object $install -Name "type" -Context "artifact '$artifactId' install"

  if ($type -eq "python_wheel") {
    return
  }

  $destRel = Get-RequiredStringProperty -Object $install -Name "destination" -Context "artifact '$artifactId' install"
  $dest = Join-Path $BundleRoot $destRel

  if ($type -eq "extract") {
    $stripPrefix = Get-OptionalStringProperty -Object $install -Name "strip_prefix"
    if ($stripPrefix -ne "") {
      $tmp = Join-Path $CacheDir ("tmp_extract_" + $artifactId)
      Expand-ArchiveFile -ArchivePath $DownloadedPath -Destination $tmp
      $stripPrefixNorm = ($stripPrefix -replace "/", "\\").TrimEnd("\\")
      $prefixPath = Join-Path $tmp $stripPrefixNorm
      if (!(Test-Path -LiteralPath $prefixPath)) {
        throw "strip_prefix path not found after extraction: $stripPrefix (artifact $artifactId)"
      }
      Ensure-Directory -Path $dest
      Get-ChildItem -LiteralPath $prefixPath -Force | ForEach-Object {
        Copy-Item -Recurse -Force -LiteralPath $_.FullName -Destination $dest
      }
      Remove-Item -Recurse -Force -LiteralPath $tmp
    } else {
      Expand-ArchiveFile -ArchivePath $DownloadedPath -Destination $dest
    }
    return
  }

  if ($type -eq "copy_file") {
    $sourcePath = Get-RequiredStringProperty -Object $install -Name "source_path" -Context "artifact '$artifactId' install"
    $tmp = Join-Path $CacheDir ("tmp_extract_" + $artifactId)
    Expand-ArchiveFile -ArchivePath $DownloadedPath -Destination $tmp
    $sourcePathNorm = ($sourcePath -replace "/", "\\").TrimStart("\\")
    $src = Join-Path $tmp $sourcePathNorm
    if (!(Test-Path -LiteralPath $src)) {
      throw "Expected file not found in archive: $sourcePath (artifact $artifactId)"
    }
    Ensure-Directory -Path (Split-Path -Parent $dest)
    Copy-Item -Force -LiteralPath $src -Destination $dest
    $manifestEntry = Get-OptionalStringProperty -Object $install -Name "manifest"
    if ($manifestEntry -ne "") {
      $manifestPath = Join-Path (Split-Path -Parent $dest) "manifest.vs"
      $manifestContent = "[VapourSynth Manifest V1]`r`n$manifestEntry`r`n"
      Set-Content -LiteralPath $manifestPath -Value $manifestContent -Encoding ASCII
    }
    Remove-Item -Recurse -Force -LiteralPath $tmp
    return
  }

  throw "Unknown install.type '$type' for artifact $artifactId"
}

function Write-LauncherFiles([string]$BundleRoot) {
  $ps1Path = Join-Path $BundleRoot "frame-compare.ps1"
  $cmdPath = Join-Path $BundleRoot "frame-compare.cmd"
  $updatePs1Path = Join-Path $BundleRoot "frame-compare-update.ps1"
  $updateCmdPath = Join-Path $BundleRoot "frame-compare-update.cmd"

  $ps1 = @'
$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$bundleRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$python = Join-Path $bundleRoot "python\\python.exe"

if (!(Test-Path -LiteralPath $python)) {
  throw "Embedded python not found: $python"
}

$env:PYTHONUTF8 = "1"
$env:PYTHONPATH = "$bundleRoot\\app\\src;$bundleRoot\\app\\site-packages"
$env:VAPOURSYNTH_EXTRA_PLUGIN_PATH = "$bundleRoot\\vs\\extra-plugins"
Remove-Item Env:VAPOURSYNTH_PLUGIN_PATH -ErrorAction SilentlyContinue
$sitePackages = Join-Path $bundleRoot "app\\site-packages"
$vsPackage = Join-Path $sitePackages "vapoursynth"
$vsPluginDir = Join-Path $vsPackage "plugins"
$extraPluginRoot = Join-Path $bundleRoot "vs\\extra-plugins"
$ffmpegRoot = Join-Path $bundleRoot "ffmpeg"
$ffmpegBin = Join-Path $ffmpegRoot "bin"
$qtBin = Join-Path $bundleRoot "app\\site-packages\\PyQt6\\Qt6\\bin"
$pathEntries = @(
  (Join-Path $bundleRoot "python"),
  $vsPackage,
  $vsPluginDir,
  $extraPluginRoot,
  $ffmpegBin,
  $ffmpegRoot
)
if (Test-Path -LiteralPath $qtBin) {
  $pathEntries = @($qtBin) + $pathEntries
}
foreach ($runtimeRoot in @($vsPackage, $extraPluginRoot, $ffmpegRoot)) {
  if (Test-Path -LiteralPath $runtimeRoot) {
    Get-ChildItem -LiteralPath $runtimeRoot -Directory -Recurse | ForEach-Object {
      $pathEntries += $_.FullName
    }
  }
}
if (Test-Path -LiteralPath $sitePackages) {
  Get-ChildItem -LiteralPath $sitePackages -Filter "*.dll" -File -Recurse | ForEach-Object {
    $runtimeDir = Split-Path -Parent $_.FullName
    if ($pathEntries -notcontains $runtimeDir) {
      $pathEntries += $runtimeDir
    }
  }
}
$env:PATH = (($pathEntries | Where-Object { $_ -and (Test-Path -LiteralPath $_) } | Select-Object -Unique) -join ";") + ";" + $env:PATH

$exitCode = 0
Push-Location $bundleRoot
try {
  & $python -m frame_compare.cli.entry @args
  if ($null -eq $LASTEXITCODE) {
    $exitCode = 1
  } else {
    $exitCode = $LASTEXITCODE
  }
} finally {
  Pop-Location
}
exit $exitCode
'@

  $cmd = @'
@echo off
setlocal
set SCRIPT_DIR=%~dp0
where pwsh >nul 2>nul
if %ERRORLEVEL% EQU 0 (
  pwsh -NoProfile -ExecutionPolicy Bypass -File "%SCRIPT_DIR%frame-compare.ps1" %*
) else (
  powershell -NoProfile -ExecutionPolicy Bypass -File "%SCRIPT_DIR%frame-compare.ps1" %*
)
exit /b %ERRORLEVEL%
'@

  $updatePs1 = @'
$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$bundleRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$updater = Join-Path $bundleRoot "shim\\frame-compare-update.ps1"

if (!(Test-Path -LiteralPath $updater)) {
  throw "Updater shim not found: $updater"
}

& $updater @args
if ($null -eq $LASTEXITCODE) {
  exit 1
}
exit $LASTEXITCODE
'@

  $updateCmd = @'
@echo off
setlocal
set SCRIPT_DIR=%~dp0
where pwsh >nul 2>nul
if %ERRORLEVEL% EQU 0 (
  pwsh -NoProfile -ExecutionPolicy Bypass -File "%SCRIPT_DIR%frame-compare-update.ps1" %*
) else (
  powershell -NoProfile -ExecutionPolicy Bypass -File "%SCRIPT_DIR%frame-compare-update.ps1" %*
)
exit /b %ERRORLEVEL%
'@

  Set-Content -LiteralPath $ps1Path -Value $ps1 -Encoding UTF8
  Set-Content -LiteralPath $cmdPath -Value $cmd -Encoding ASCII
  Set-Content -LiteralPath $updatePs1Path -Value $updatePs1 -Encoding UTF8
  Set-Content -LiteralPath $updateCmdPath -Value $updateCmd -Encoding ASCII
}

function Copy-InstallerFiles([string]$BundleRoot) {
  $sourceDir = $PSScriptRoot
  $shimSource = Join-Path $sourceDir "shim"
  $shimDest = Join-Path $BundleRoot "shim"
  $publicKeySource = Join-Path $sourceDir "update_public_key.xml"

  foreach ($file in @("install.ps1", "uninstall.ps1", "install.cmd", "uninstall.cmd", "README.txt")) {
    $src = Join-Path $sourceDir $file
    if (!(Test-Path -LiteralPath $src)) {
      throw "Installer file not found: $src"
    }
    Copy-Item -Force -LiteralPath $src -Destination (Join-Path $BundleRoot $file)
  }

  if (!(Test-Path -LiteralPath $shimSource)) {
    throw "Shim directory not found: $shimSource"
  }
  if (!(Test-Path -LiteralPath $publicKeySource)) {
    throw "Update public key not found: $publicKeySource"
  }
  if (Test-Path -LiteralPath $shimDest) {
    Remove-Item -Recurse -Force -LiteralPath $shimDest
  }
  Copy-Item -Recurse -Force -LiteralPath $shimSource -Destination $shimDest
  Copy-Item -Force -LiteralPath $publicKeySource -Destination (Join-Path $shimDest "update_public_key.xml")
}

function Copy-RepoApp([string]$BundleRoot) {
  $appRoot = Join-Path $BundleRoot "app"
  $srcRoot = Join-Path $appRoot "src"
  $sitePackages = Join-Path $appRoot "site-packages"

  Ensure-Directory -Path $appRoot
  Ensure-Directory -Path $srcRoot
  Ensure-Directory -Path $sitePackages

  $pkgSrc = Join-Path $RepoRoot "src\\frame_compare"
  if (!(Test-Path -LiteralPath $pkgSrc)) {
    throw "Repo package not found: $pkgSrc"
  }
  Copy-Item -Recurse -Force -LiteralPath $pkgSrc -Destination (Join-Path $srcRoot "frame_compare")
}

function Configure-EmbeddedPython([string]$BundleRoot) {
  $pythonDir = Join-Path $BundleRoot "python"
  $pthCandidates = @(Get-ChildItem -LiteralPath $pythonDir -Filter "python*._pth" -File)
  if ($pthCandidates.Count -ne 1) {
    throw "Expected exactly one embedded Python ._pth file in $pythonDir, found $($pthCandidates.Count)"
  }
  $pth = $pthCandidates[0].FullName
  $pthBase = [System.IO.Path]::GetFileNameWithoutExtension($pthCandidates[0].Name)
  $pythonZip = "$pthBase.zip"

  # The embeddable distribution uses python313._pth to define sys.path and typically ignores
  # PYTHONPATH/environment. Make the bundle self-contained by pinning the app paths here.
  $lines = @(
    $pythonZip,
    ".",
    "..\\app\\site-packages",
    "..\\app\\src",
    "import site"
  )
  $content = ($lines -join "`r`n") + "`r`n"
  Set-Content -LiteralPath $pth -Value $content -Encoding ASCII
}

function Install-PythonDeps([string]$BundleRoot, [string]$VsCoreRoot) {
  if (!(Get-Command uv -ErrorAction SilentlyContinue)) {
    throw "uv is required on PATH to build the portable bundle."
  }

  $appRoot = Join-Path $BundleRoot "app"
  $sitePackages = Join-Path $appRoot "site-packages"
  $reqFile = Join-Path $BundleRoot "requirements.lock.txt"

  Push-Location $RepoRoot
  try {
    # Export pinned, hashed requirements from uv.lock (exclude project itself; we run from app/src via PYTHONPATH).
    uv export --frozen --no-dev --no-emit-project --extra vspreview --format requirements.txt --output-file $reqFile | Out-Null
    Assert-LastExitCode -CommandLabel "uv export"
  } finally {
    Pop-Location
  }

  # Install project dependencies into app/site-packages.
  uv pip install --reinstall --strict --exact --require-hashes --python-version 3.13 --python-platform windows --target $sitePackages -r $reqFile
  Assert-LastExitCode -CommandLabel "uv pip install requirements"
  $tomliWModule = Join-Path $sitePackages "tomli_w"
  $tomliWDistInfo = @(Get-ChildItem -LiteralPath $sitePackages -Filter "tomli_w-*.dist-info" -Directory -ErrorAction SilentlyContinue)
  if (!(Test-Path -LiteralPath $tomliWModule) -and $tomliWDistInfo.Count -eq 0) {
    throw "tomli_w was not installed into bundle site-packages: $sitePackages"
  }

  # Install VapourSynth python module from the pinned VS portable distribution (no PyPI dependency).
  $wheelDir = Join-Path $VsCoreRoot "wheel"
  $vsWheelCandidates = @(Get-ChildItem -LiteralPath $wheelDir -Filter "vapoursynth-*-abi3-win_amd64.whl" -File)
  if ($vsWheelCandidates.Count -ne 1) {
    throw "Expected exactly one VapourSynth wheel in $wheelDir, found $($vsWheelCandidates.Count)"
  }
  $vsWheel = $vsWheelCandidates[0].FullName
  uv pip install --no-deps --only-binary :all: --target $sitePackages $vsWheel
  Assert-LastExitCode -CommandLabel "uv pip install vapoursynth wheel"

  # R76 wheels carry the runtime DLL inside the vapoursynth package directory.
  # The launcher and validation PATH include this directory for Windows DLL lookup.
  $vsDllPackage = Join-Path $sitePackages "vapoursynth\\libvapoursynth.dll"
  if (!(Test-Path -LiteralPath $vsDllPackage)) {
    throw "libvapoursynth.dll not found after wheel install in expected R76 package layout: $vsDllPackage"
  }
}

function Install-PythonWheelArtifacts([string]$BundleRoot, [pscustomobject[]]$Artifacts, [hashtable]$Downloaded) {
  $sitePackages = Join-Path $BundleRoot "app\\site-packages"

  foreach ($artifact in $Artifacts) {
    $artifactId = Get-RequiredStringProperty -Object $artifact -Name "id" -Context "artifact"
    $install = Get-RequiredProperty -Object $artifact -Name "install" -Context "artifact '$artifactId'"
    $type = Get-RequiredStringProperty -Object $install -Name "type" -Context "artifact '$artifactId' install"
    if ($type -ne "python_wheel") {
      continue
    }
    $wheelPath = [string]$Downloaded[$artifactId]
    if (!(Test-Path -LiteralPath $wheelPath)) {
      throw "Python wheel artifact was not downloaded: $artifactId"
    }
    $sha256 = Get-RequiredStringProperty -Object $artifact -Name "sha256" -Context "artifact '$artifactId'"
    Assert-Sha256 -FilePath $wheelPath -ExpectedHex $sha256
    uv pip install --reinstall --strict --no-deps --target $sitePackages $wheelPath
    Assert-LastExitCode -CommandLabel "uv pip install $artifactId"
  }
}

function Set-BundleRuntimeEnvironment([string]$BundleRoot) {
  $env:PYTHONUTF8 = "1"
  $env:PYTHONPATH = "$BundleRoot\\app\\src;$BundleRoot\\app\\site-packages"
  $env:VAPOURSYNTH_EXTRA_PLUGIN_PATH = "$BundleRoot\\vs\\extra-plugins"
  Remove-Item Env:VAPOURSYNTH_PLUGIN_PATH -ErrorAction SilentlyContinue

  $sitePackages = Join-Path $BundleRoot "app\\site-packages"
  $vsPackage = Join-Path $sitePackages "vapoursynth"
  $vsPluginDir = Join-Path $vsPackage "plugins"
  $extraPluginRoot = Join-Path $BundleRoot "vs\\extra-plugins"
  $ffmpegRoot = Join-Path $BundleRoot "ffmpeg"
  $ffmpegBin = Join-Path $ffmpegRoot "bin"
  $qtBin = Join-Path $BundleRoot "app\\site-packages\\PyQt6\\Qt6\\bin"

  $pathEntries = @(
    (Join-Path $BundleRoot "python"),
    $vsPackage,
    $vsPluginDir,
    $extraPluginRoot,
    $ffmpegBin,
    $ffmpegRoot
  )
  if (Test-Path -LiteralPath $qtBin) {
    $pathEntries = @($qtBin) + $pathEntries
  }
  foreach ($runtimeRoot in @($vsPackage, $extraPluginRoot, $ffmpegRoot)) {
    if (Test-Path -LiteralPath $runtimeRoot) {
      Get-ChildItem -LiteralPath $runtimeRoot -Directory -Recurse | ForEach-Object {
        $pathEntries += $_.FullName
      }
    }
  }
  if (Test-Path -LiteralPath $sitePackages) {
    Get-ChildItem -LiteralPath $sitePackages -Filter "*.dll" -File -Recurse | ForEach-Object {
      $runtimeDir = Split-Path -Parent $_.FullName
      if ($pathEntries -notcontains $runtimeDir) {
        $pathEntries += $runtimeDir
      }
    }
  }
  $existingEntries = $pathEntries | Where-Object { $_ -and (Test-Path -LiteralPath $_) } | Select-Object -Unique
  $env:PATH = (($existingEntries -join ";") + ";" + $env:PATH)
}

function Write-BundleInfo([string]$BundleRoot, [string]$AppVersion) {
  $requirementsLockPath = Join-Path $BundleRoot "requirements.lock.txt"
  if (!(Test-Path -LiteralPath $requirementsLockPath)) {
    throw "requirements.lock.txt not found for bundle info: $requirementsLockPath"
  }

  $requirementsLockSha256 = (Get-FileHash -Algorithm SHA256 -LiteralPath $requirementsLockPath).Hash.ToLowerInvariant()
  $bundleInfo = [ordered]@{
    schema_version = 1
    bundle_kind = "full"
    app_version = $AppVersion
    requirements_lock_sha256 = $requirementsLockSha256
    manifest_version = 1
    platform = "windows-x64"
  }
  $bundleInfoPath = Join-Path $BundleRoot "bundle_info.json"
  $bundleInfoJson = $bundleInfo | ConvertTo-Json
  $utf8NoBom = New-Object System.Text.UTF8Encoding($false)
  [System.IO.File]::WriteAllText($bundleInfoPath, ($bundleInfoJson + "`n"), $utf8NoBom)
}

function Invoke-BundleRuntimeProof(
  [string]$Python,
  [string]$SmokePath,
  [string]$Phase,
  [string]$MediaPath,
  [bool]$Required
) {
  Write-Host "WINDOWS_BUNDLE_PROOF phase=$Phase start"
  $previousNativeCommandPreference = $PSNativeCommandUseErrorActionPreference
  $PSNativeCommandUseErrorActionPreference = $false
  try {
    & $Python $SmokePath $Phase $MediaPath
    $exitCode = $LASTEXITCODE
  } finally {
    $PSNativeCommandUseErrorActionPreference = $previousNativeCommandPreference
  }

  if ($exitCode -ne 0) {
    $message = "bundle runtime validation phase '$Phase' failed with exit code $exitCode"
    Write-Host "WINDOWS_BUNDLE_PROOF phase=$Phase failed exit_code=$exitCode"
    if ($Required) {
      throw $message
    }
    Write-Warning $message
    return
  }

  Write-Host "WINDOWS_BUNDLE_PROOF phase=$Phase ok"
}

function Assert-BundleRuntime([string]$BundleRoot) {
  $python = Join-Path $BundleRoot "python\\python.exe"
  if (!(Test-Path -LiteralPath $python)) {
    throw "Embedded python not found for runtime validation: $python"
  }

  Set-BundleRuntimeEnvironment -BundleRoot $BundleRoot

  $ffmpeg = Join-Path $BundleRoot "ffmpeg\\bin\\ffmpeg.exe"
  $mediaPath = Join-Path $BundleRoot "runtime-smoke.mp4"
  if (Test-Path -LiteralPath $ffmpeg) {
    & $ffmpeg -hide_banner -loglevel error -f lavfi -i "testsrc2=size=32x32:rate=1:duration=1" -frames:v 1 -pix_fmt yuv420p -y $mediaPath
    Assert-LastExitCode -CommandLabel "ffmpeg tiny media generation"
  }

  $smokePath = Join-Path $BundleRoot "runtime-smoke.py"
  $smokeScript = @'
from __future__ import annotations

import os
import sys
from pathlib import Path


def assert_true(condition: object, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def proof(message: str) -> None:
    print(f"WINDOWS_BUNDLE_PROOF {message}", flush=True)


def prove_package_imports() -> None:
    import frame_compare  # noqa: F401
    import rich  # noqa: F401
    import tomli_w  # noqa: F401
    import typer  # noqa: F401

    proof("package_imports=ok modules=frame_compare,rich,tomli_w,typer")


def prove_vapoursynth_environment() -> None:
    import vapoursynth as vs

    core = vs.core
    version = getattr(vs, "__version__", None)
    version_major = getattr(version, "release_major", None)
    version_minor = getattr(version, "release_minor", None)
    plugin_dir = Path(vs.get_plugin_dir())
    extra_plugin_path = os.environ.get("VAPOURSYNTH_EXTRA_PLUGIN_PATH", "")
    plugins = list(core.plugins())
    plugin_namespaces = sorted(plugin.namespace for plugin in plugins)

    assert_true(version_major == 76 and version_minor == 0, f"expected VapourSynth R76, got {version!r}")
    assert_true(plugin_dir.is_dir(), f"vapoursynth.get_plugin_dir() is not a directory: {plugin_dir}")
    assert_true("vapoursynth" in str(plugin_dir).replace("\\", "/"), f"unexpected plugin dir: {plugin_dir}")
    assert_true(extra_plugin_path, "VAPOURSYNTH_EXTRA_PLUGIN_PATH is not set")
    assert_true("VAPOURSYNTH_PLUGIN_PATH" not in os.environ, "legacy VAPOURSYNTH_PLUGIN_PATH should not be set")
    assert_true(plugin_namespaces, "core.plugins() returned no plugins")

    proof(f"vapoursynth_import=ok version=R{version_major}")
    proof(f"plugin_dir={plugin_dir}")
    proof(f"extra_plugin_path={extra_plugin_path}")
    proof(f"core_plugins={','.join(plugin_namespaces)}")


def prove_lwlibavsource(media_path: Path) -> None:
    import vapoursynth as vs

    from frame_compare.vs.env import candidate_lsmas_plugin_path_details, try_load_lsmas_plugin

    core = vs.core
    lsmas_loaded_path = None
    if not (hasattr(core, "lsmas") and hasattr(core.lsmas, "LWLibavSource")):
        lsmas_loaded_path = try_load_lsmas_plugin(core)

    assert_true(hasattr(core, "lsmas"), "core.lsmas namespace missing")
    assert_true(hasattr(core.lsmas, "LWLibavSource"), "core.lsmas.LWLibavSource missing")

    if media_path.is_file():
        clip = core.lsmas.LWLibavSource(str(media_path))
        frame = clip.get_frame(0)
        assert_true(frame.width == 32 and frame.height == 32, "LWLibavSource frame render failed")
    else:
        candidates = [{"source": candidate.source, "path": candidate.path} for candidate in candidate_lsmas_plugin_path_details()]
        raise AssertionError(f"tiny media proof missing: {media_path}; candidates={candidates}")

    proof(f"lwlibavsource=ok namespace=lsmas loaded_path={lsmas_loaded_path}")


def build_placebo_clip():
    import vapoursynth as vs

    core = vs.core
    assert_true(hasattr(core, "placebo"), "core.placebo namespace missing")
    assert_true(hasattr(core.placebo, "Tonemap"), "core.placebo.Tonemap missing")

    tonemap_clip = core.std.BlankClip(width=16, height=16, format=vs.RGB48, length=1, color=[32768, 32768, 32768])
    tonemap_clip = tonemap_clip.std.SetFrameProps(_Matrix=0, _Range=0, _Transfer=16, _Primaries=9)
    return core.placebo.Tonemap(
        tonemap_clip,
        src_max=1000,
        dst_max=203,
        tone_mapping_function=2,
        dst_csp=0,
        dst_prim=1,
        src_csp=1,
    ), tonemap_clip


def prove_placebo_tonemap_api() -> None:
    import vapoursynth as vs

    core = vs.core
    assert_true(hasattr(core, "placebo"), "core.placebo namespace missing")
    assert_true(hasattr(core.placebo, "Tonemap"), "core.placebo.Tonemap missing")
    proof("placebo_tonemap_api=ok namespace=placebo function=Tonemap")


def prove_placebo_tonemap_frame() -> None:
    direct_out, _tonemap_clip = build_placebo_clip()
    direct_frame = direct_out.get_frame(0)
    assert_true(direct_frame.width == 16 and direct_frame.height == 16, "placebo direct frame render failed")
    proof("placebo_direct_frame=ok")


def prove_apply_tonemap_frame() -> None:
    import vapoursynth as vs

    from frame_compare.vs.tonemap import _libplacebo_runtime_usable, apply_tonemap
    from frame_compare.vs.types import TonemapSettings

    core = vs.core
    tonemap_clip = core.std.BlankClip(width=16, height=16, format=vs.RGB48, length=1, color=[32768, 32768, 32768])
    tonemap_clip = tonemap_clip.std.SetFrameProps(_Matrix=0, _Range=0, _Transfer=16, _Primaries=9)

    libplacebo_runtime_usable = _libplacebo_runtime_usable()
    app_out = apply_tonemap(tonemap_clip, TonemapSettings(enabled=True))
    app_frame = app_out.get_frame(0)
    assert_true(app_frame.width == 16 and app_frame.height == 16, "apply_tonemap frame render failed")

    proof(f"apply_tonemap=ok frame=rendered fallback_aware=true libplacebo_runtime_usable={str(libplacebo_runtime_usable).lower()}")


def prove_vspreview_pyqt6() -> None:
    import PyQt6  # noqa: F401

    proof("pyqt6_import=ok")

    import vspreview  # noqa: F401

    proof("vspreview_pyqt6=ok")


phase = sys.argv[1]
media_path = Path(sys.argv[2])
if phase == "package_imports":
    prove_package_imports()
elif phase == "vapoursynth_environment":
    prove_vapoursynth_environment()
elif phase == "lwlibavsource_frame":
    prove_lwlibavsource(media_path)
elif phase == "placebo_tonemap_api":
    prove_placebo_tonemap_api()
elif phase == "apply_tonemap_frame":
    prove_apply_tonemap_frame()
elif phase == "placebo_tonemap_frame":
    prove_placebo_tonemap_frame()
elif phase == "vspreview_pyqt6_import":
    prove_vspreview_pyqt6()
else:
    raise AssertionError(f"unknown runtime proof phase: {phase}")
'@
  Set-Content -LiteralPath $smokePath -Value $smokeScript -Encoding UTF8
  try {
    Invoke-BundleRuntimeProof -Python $python -SmokePath $smokePath -Phase "package_imports" -MediaPath $mediaPath -Required $true
    Invoke-BundleRuntimeProof -Python $python -SmokePath $smokePath -Phase "vapoursynth_environment" -MediaPath $mediaPath -Required $true
    Invoke-BundleRuntimeProof -Python $python -SmokePath $smokePath -Phase "lwlibavsource_frame" -MediaPath $mediaPath -Required $true
    Invoke-BundleRuntimeProof -Python $python -SmokePath $smokePath -Phase "placebo_tonemap_api" -MediaPath $mediaPath -Required $true
    Invoke-BundleRuntimeProof -Python $python -SmokePath $smokePath -Phase "apply_tonemap_frame" -MediaPath $mediaPath -Required $true
    Invoke-BundleRuntimeProof -Python $python -SmokePath $smokePath -Phase "placebo_tonemap_frame" -MediaPath $mediaPath -Required $false
    Invoke-BundleRuntimeProof -Python $python -SmokePath $smokePath -Phase "vspreview_pyqt6_import" -MediaPath $mediaPath -Required $false
  } finally {
    Remove-Item -Force -LiteralPath $smokePath -ErrorAction SilentlyContinue
    Remove-Item -Force -LiteralPath $mediaPath -ErrorAction SilentlyContinue
  }
}

function Copy-PythonDistLicenses([string]$SitePackages, [string]$LicensesPythonDir) {
  Ensure-Directory -Path $LicensesPythonDir
  $licensePatterns = @("LICENSE*", "COPYING*")
  $distInfoDirs = @(Get-ChildItem -LiteralPath $SitePackages -Directory -Filter "*.dist-info" -ErrorAction SilentlyContinue)
  foreach ($distInfo in $distInfoDirs) {
    # Some wheels ship license texts under *.dist-info\licenses (not just LICENSE* at dist-info root).
    foreach ($pattern in $licensePatterns) {
      $licenseFiles = @(Get-ChildItem -LiteralPath $distInfo.FullName -File -Filter $pattern -ErrorAction SilentlyContinue)
      foreach ($match in $licenseFiles) {
        $destName = "{0}__{1}" -f $distInfo.Name, $match.Name
        Copy-Item -Force -LiteralPath $match.FullName -Destination (Join-Path $LicensesPythonDir $destName)
      }
    }

    $distInfoLicenses = Join-Path $distInfo.FullName "licenses"
    if (Test-Path -LiteralPath $distInfoLicenses -PathType Container) {
      $destDir = Join-Path $LicensesPythonDir ("{0}__licenses" -f $distInfo.Name)
      Copy-Item -Recurse -Force -LiteralPath $distInfoLicenses -Destination $destDir
    }
  }

  $qtLicenses = Join-Path $SitePackages "PyQt6\\Qt6\\licenses"
  if (Test-Path -LiteralPath $qtLicenses) {
    Copy-Item -Recurse -Force -LiteralPath $qtLicenses -Destination (Join-Path $LicensesPythonDir "PyQt6-Qt-licenses")
  }
}

function Copy-Licenses([string]$BundleRoot, [pscustomobject[]]$Artifacts) {
  $licensesDir = Join-Path $BundleRoot "licenses"
  Ensure-Directory -Path $licensesDir
  $pythonLicensesDir = Join-Path $licensesDir "python"
  Ensure-Directory -Path $pythonLicensesDir

  # Project license
  Copy-Item -Force -LiteralPath (Join-Path $RepoRoot "LICENSE") -Destination (Join-Path $licensesDir "frame-compare-LICENSE.txt")
  Copy-PythonDistLicenses -SitePackages (Join-Path $BundleRoot "app\\site-packages") -LicensesPythonDir $pythonLicensesDir

  $sourceUrls = @(
    "Qt source: https://download.qt.io/official_releases/qt/",
    "FFmpeg source: https://ffmpeg.org/download.html",
    "VapourSynth source: https://github.com/vapoursynth/vapoursynth",
    "L-SMASH-Works source: https://github.com/HomeOfAviSynthPlusEvolution/L-SMASH-Works",
    "vs-placebo source: https://github.com/Lypheo/vs-placebo"
  )
  Set-Content -LiteralPath (Join-Path $licensesDir "SOURCE_URLS.txt") -Value ($sourceUrls -join "`r`n") -Encoding ASCII

  foreach ($artifact in $Artifacts) {
    $id = Get-RequiredStringProperty -Object $artifact -Name "id" -Context "artifact"
    $url = Get-RequiredStringProperty -Object $artifact -Name "url" -Context "artifact '$id'"
    $fileName = Split-Path -Leaf $url
    $license = Get-RequiredProperty -Object $artifact -Name "license" -Context "artifact '$id'"
    $licenseUrl = Get-RequiredStringProperty -Object $license -Name "url" -Context "artifact '$id' license"
    $spdx = Get-RequiredStringProperty -Object $license -Name "spdx" -Context "artifact '$id' license"

    if ($fileName -like "*.zip") {
      # Best-effort: copy LICENSE.txt if present in the zip.
      if ($id -like "ffmpeg-*") {
        $ffmpegLicense = Join-Path $BundleRoot "ffmpeg\\LICENSE.txt"
        if (Test-Path -LiteralPath $ffmpegLicense) {
          Copy-Item -Force -LiteralPath $ffmpegLicense -Destination (Join-Path $licensesDir "ffmpeg-LICENSE.txt")
        }
      }
      if ($id -eq "python-embed-amd64") {
        $pyLicense = Join-Path $BundleRoot "python\\LICENSE.txt"
        if (Test-Path -LiteralPath $pyLicense) {
          Copy-Item -Force -LiteralPath $pyLicense -Destination (Join-Path $licensesDir "python-LICENSE.txt")
        }
      }
    }

    # Download license text for artifacts that do not consistently ship one in the installed path.
    if ($id -like "vapoursynth-*" -or $id -like "vs-plugin-*") {
      $dest = Join-Path $licensesDir ("{0}-{1}.txt" -f $id, $spdx)
      Write-Host "Fetching license for $id ($spdx)"
      Invoke-WebRequest -Uri $licenseUrl -OutFile $dest | Out-Null
    }
  }
}

function Main() {
  if ($RequireReleasePublicKey) {
    Assert-ReleasePublicKey
  }

  Ensure-Directory -Path $CacheDir
  if (Test-Path -LiteralPath $OutDir) {
    Remove-Item -Recurse -Force -LiteralPath $OutDir
  }
  Ensure-Directory -Path $OutDir

  $manifest = Get-Manifest
  $artifacts = @(Get-RequiredProperty -Object $manifest -Name "artifacts" -Context "manifest")

  $downloaded = @{}
  foreach ($artifact in $artifacts) {
    $path = Download-Artifact -Artifact $artifact
    $downloaded[(Get-RequiredStringProperty -Object $artifact -Name "id" -Context "artifact")] = $path
  }

  # Copy pin manifest into the bundle root.
  Copy-Item -Force -LiteralPath $ManifestPath -Destination (Join-Path $OutDir "manifest.json")

  # Install artifacts per manifest mapping.
  foreach ($artifact in $artifacts) {
    $id = Get-RequiredStringProperty -Object $artifact -Name "id" -Context "artifact"
    $path = $downloaded[$id]
    Install-Artifact -BundleRoot $OutDir -Artifact $artifact -DownloadedPath $path
  }

  # Layout: app/
  Copy-RepoApp -BundleRoot $OutDir
  Install-PythonDeps -BundleRoot $OutDir -VsCoreRoot (Join-Path $OutDir "vs\\core")
  Install-PythonWheelArtifacts -BundleRoot $OutDir -Artifacts $artifacts -Downloaded $downloaded
  Write-BundleInfo -BundleRoot $OutDir -AppVersion (Get-AppVersionFromSource -RepoRootPath $RepoRoot)
  Configure-EmbeddedPython -BundleRoot $OutDir
  Assert-BundleRuntime -BundleRoot $OutDir

  # Launchers
  Write-LauncherFiles -BundleRoot $OutDir
  Copy-InstallerFiles -BundleRoot $OutDir

  # Create default workspace directories in the bundle so users can drop in
  # config and sources without passing explicit paths.
  $bundleConfigDir = Join-Path $OutDir "config"
  $bundleInputDir = Join-Path $OutDir "comparison_videos"
  Ensure-Directory -Path $bundleConfigDir
  Ensure-Directory -Path $bundleInputDir

  # Licenses
  Copy-Licenses -BundleRoot $OutDir -Artifacts $artifacts

  Write-Host "OK: portable bundle assembled at $OutDir"
}

Main
