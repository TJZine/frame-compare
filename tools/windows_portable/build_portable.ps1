Param(
  [Parameter(Mandatory = $false)]
  [string]$ManifestPath = (Join-Path $PSScriptRoot "manifest.windows-x64.json"),

  [Parameter(Mandatory = $false)]
  [string]$OutDir = (Join-Path $PWD "dist\\frame-compare-portable-win-x64"),

  [Parameter(Mandatory = $false)]
  [string]$CacheDir = (Join-Path $PWD ".portable_cache"),

  [Parameter(Mandatory = $false)]
  [string]$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\\..")).Path
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest
$PSNativeCommandUseErrorActionPreference = $true

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
  Invoke-WebRequest -Uri $url -OutFile $dest | Out-Null
  Assert-Sha256 -FilePath $dest -ExpectedHex $sha256
  return $dest
}

function Expand-Zip([string]$ZipPath, [string]$Destination) {
  if (Test-Path -LiteralPath $Destination) {
    Remove-Item -Recurse -Force -LiteralPath $Destination
  }
  Ensure-Directory -Path $Destination
  Expand-Archive -LiteralPath $ZipPath -DestinationPath $Destination -Force
}

function Install-Artifact([string]$BundleRoot, [pscustomobject]$Artifact, [string]$DownloadedPath) {
  $artifactId = Get-RequiredStringProperty -Object $Artifact -Name "id" -Context "artifact"
  $install = Get-RequiredProperty -Object $Artifact -Name "install" -Context "artifact '$artifactId'"

  $type = Get-RequiredStringProperty -Object $install -Name "type" -Context "artifact '$artifactId' install"
  $destRel = Get-RequiredStringProperty -Object $install -Name "destination" -Context "artifact '$artifactId' install"
  $dest = Join-Path $BundleRoot $destRel

  if ($type -eq "extract") {
    $stripPrefix = Get-OptionalStringProperty -Object $install -Name "strip_prefix"
    if ($stripPrefix -ne "") {
      $tmp = Join-Path $CacheDir ("tmp_extract_" + $artifactId)
      Expand-Zip -ZipPath $DownloadedPath -Destination $tmp
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
      Expand-Zip -ZipPath $DownloadedPath -Destination $dest
    }
    return
  }

  if ($type -eq "copy_file") {
    $sourcePath = Get-RequiredStringProperty -Object $install -Name "source_path" -Context "artifact '$artifactId' install"
    $tmp = Join-Path $CacheDir ("tmp_extract_" + $artifactId)
    Expand-Zip -ZipPath $DownloadedPath -Destination $tmp
    $sourcePathNorm = ($sourcePath -replace "/", "\\").TrimStart("\\")
    $src = Join-Path $tmp $sourcePathNorm
    if (!(Test-Path -LiteralPath $src)) {
      throw "Expected file not found in archive: $sourcePath (artifact $artifactId)"
    }
    Ensure-Directory -Path (Split-Path -Parent $dest)
    Copy-Item -Force -LiteralPath $src -Destination $dest
    Remove-Item -Recurse -Force -LiteralPath $tmp
    return
  }

  throw "Unknown install.type '$type' for artifact $artifactId"
}

function Write-LauncherFiles([string]$BundleRoot) {
  $ps1Path = Join-Path $BundleRoot "frame-compare.ps1"
  $cmdPath = Join-Path $BundleRoot "frame-compare.cmd"

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
$env:VAPOURSYNTH_CONF_PATH = "$bundleRoot\\vs\\core\\portable.vs"
$env:VAPOURSYNTH_PLUGIN_PATH = "$bundleRoot\\vs\\plugins"
$vsCore = Join-Path $bundleRoot "vs\\core"
$ffmpegRoot = Join-Path $bundleRoot "ffmpeg"
$vsRuntimeCandidates = @()
if (Test-Path -LiteralPath $vsCore) {
  $vsRuntimeCandidates = @(Get-ChildItem -LiteralPath $vsCore -Filter "VSScript.dll" -File -Recurse)
}
$vsRuntimeDir = $null
if ($vsRuntimeCandidates.Count -gt 0) {
  $vsRuntimeDir = Split-Path -Parent $vsRuntimeCandidates[0].FullName
  $env:VAPOURSYNTH_HOME = $vsRuntimeDir
}
$pathEntries = @(
  (Join-Path $bundleRoot "python"),
  $vsCore,
  (Join-Path $bundleRoot "vs\\plugins"),
  $ffmpegRoot
)
if ($null -ne $vsRuntimeDir -and $vsRuntimeDir -ne "") {
  $pathEntries = @($vsRuntimeDir) + $pathEntries
}
if (Test-Path -LiteralPath $vsCore) {
  Get-ChildItem -LiteralPath $vsCore -Directory -Recurse | ForEach-Object {
    $pathEntries += $_.FullName
  }
}
if (Test-Path -LiteralPath $ffmpegRoot) {
  Get-ChildItem -LiteralPath $ffmpegRoot -Directory -Recurse | ForEach-Object {
    $pathEntries += $_.FullName
  }
}
$env:PATH = (($pathEntries -join ";") + ";" + $env:PATH)

& $python -m frame_compare.cli_entry @args
exit $LASTEXITCODE
'@

  $cmd = @'
@echo off
setlocal
set SCRIPT_DIR=%~dp0
powershell -NoProfile -ExecutionPolicy Bypass -File "%SCRIPT_DIR%frame-compare.ps1" %*
exit /b %ERRORLEVEL%
'@

  Set-Content -LiteralPath $ps1Path -Value $ps1 -Encoding UTF8
  Set-Content -LiteralPath $cmdPath -Value $cmd -Encoding ASCII
}

function Copy-InstallerFiles([string]$BundleRoot) {
  $sourceDir = $PSScriptRoot
  $shimSource = Join-Path $sourceDir "shim"
  $shimDest = Join-Path $BundleRoot "shim"

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
  if (Test-Path -LiteralPath $shimDest) {
    Remove-Item -Recurse -Force -LiteralPath $shimDest
  }
  Copy-Item -Recurse -Force -LiteralPath $shimSource -Destination $shimDest
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
    uv export --frozen --no-dev --no-emit-project --format requirements.txt --output-file $reqFile | Out-Null
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
  uv pip install --only-binary :all: --target $sitePackages $vsWheel
  Assert-LastExitCode -CommandLabel "uv pip install vapoursynth wheel"

  # Some wheel layouts place vapoursynth.dll under Lib/site-packages; normalize it
  # beside vapoursynth.pyd so default Windows DLL lookup resolves it reliably.
  $vsDllRoot = Join-Path $sitePackages "vapoursynth.dll"
  $vsDllNested = Join-Path $sitePackages "Lib\\site-packages\\vapoursynth.dll"
  if ((Test-Path -LiteralPath $vsDllNested) -and !(Test-Path -LiteralPath $vsDllRoot)) {
    Copy-Item -Force -LiteralPath $vsDllNested -Destination $vsDllRoot
  }
  if (!(Test-Path -LiteralPath $vsDllRoot) -and !(Test-Path -LiteralPath $vsDllNested)) {
    throw "vapoursynth.dll not found after wheel install in $sitePackages"
  }
}

function Assert-BundleRuntime([string]$BundleRoot) {
  $python = Join-Path $BundleRoot "python\\python.exe"
  if (!(Test-Path -LiteralPath $python)) {
    throw "Embedded python not found for runtime validation: $python"
  }

  $env:PYTHONUTF8 = "1"
  $env:PYTHONPATH = "$BundleRoot\\app\\src;$BundleRoot\\app\\site-packages"
  $env:VAPOURSYNTH_PLUGIN_PATH = "$BundleRoot\\vs\\plugins"
  $env:PATH = "$BundleRoot\\python;$BundleRoot\\vs\\core;$BundleRoot\\vs\\plugins;$BundleRoot\\ffmpeg;$env:PATH"

  & $python -c "import tomli_w; import typer; import rich; import frame_compare"
  Assert-LastExitCode -CommandLabel "bundle runtime import validation"
}

function Copy-Licenses([string]$BundleRoot, [pscustomobject[]]$Artifacts) {
  $licensesDir = Join-Path $BundleRoot "licenses"
  Ensure-Directory -Path $licensesDir

  # Project license
  Copy-Item -Force -LiteralPath (Join-Path $RepoRoot "LICENSE") -Destination (Join-Path $licensesDir "frame-compare-LICENSE.txt")

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

    # Download license text for artifacts that don't ship one in their zip.
    if ($id -eq "vapoursynth-portable-r73" -or $id -eq "vs-plugin-lsmas-vA.3j" -or $id -eq "vs-plugin-vs-placebo-1.4.4") {
      $dest = Join-Path $licensesDir ("{0}-{1}.txt" -f $id, $spdx)
      Write-Host "Fetching license for $id ($spdx)"
      Invoke-WebRequest -Uri $licenseUrl -OutFile $dest | Out-Null
    }
  }
}

function Consolidate-VapourSynthPlugins([string]$BundleRoot) {
  $vsCore = Join-Path $BundleRoot "vs\\core"
  $vsPlugins = Join-Path $BundleRoot "vs\\plugins"
  Ensure-Directory -Path $vsPlugins
  $blockedPluginNames = @("AvsCompat.dll")

  # Consolidate core plugins into the normative plugin directory.
  $corePluginsDir = Join-Path $vsCore "vs-coreplugins"
  $pluginsDir = Join-Path $vsCore "vs-plugins"

  foreach ($dir in @($corePluginsDir, $pluginsDir)) {
    if (Test-Path -LiteralPath $dir) {
      Get-ChildItem -LiteralPath $dir -Filter "*.dll" | ForEach-Object {
        if ($blockedPluginNames -contains $_.Name) {
          return
        }
        Copy-Item -Force -LiteralPath $_.FullName -Destination (Join-Path $vsPlugins $_.Name)
      }
    }
  }

  # Remove original plugin directories from vs/core after consolidation.
  if (Test-Path -LiteralPath $corePluginsDir) { Remove-Item -Recurse -Force -LiteralPath $corePluginsDir }
  if (Test-Path -LiteralPath $pluginsDir) { Remove-Item -Recurse -Force -LiteralPath $pluginsDir }
}

function Main() {
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

  # Post-process VS portable layout to match SSOT plugin directory.
  Consolidate-VapourSynthPlugins -BundleRoot $OutDir

  # Layout: app/
  Copy-RepoApp -BundleRoot $OutDir
  Install-PythonDeps -BundleRoot $OutDir -VsCoreRoot (Join-Path $OutDir "vs\\core")
  Configure-EmbeddedPython -BundleRoot $OutDir
  Assert-BundleRuntime -BundleRoot $OutDir

  # Launchers
  Write-LauncherFiles -BundleRoot $OutDir
  Copy-InstallerFiles -BundleRoot $OutDir

  # Licenses
  Copy-Licenses -BundleRoot $OutDir -Artifacts $artifacts

  Write-Host "OK: portable bundle assembled at $OutDir"
}

Main
