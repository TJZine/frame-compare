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

$DownloadMaxAttempts = 4
$DownloadRetryDelaySeconds = 5

# Convert caller-supplied relative paths once, before they are embedded in
# runtime environment variables or passed across process working directories.
$currentLocation = $PWD.ProviderPath
$ManifestPath = [System.IO.Path]::GetFullPath($ManifestPath, $currentLocation)
$OutDir = [System.IO.Path]::GetFullPath($OutDir, $currentLocation)
$CacheDir = [System.IO.Path]::GetFullPath($CacheDir, $currentLocation)
$RepoRoot = [System.IO.Path]::GetFullPath($RepoRoot, $currentLocation)

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

function Resolve-ManifestRelativePath([string]$RelativePath) {
  $manifestDir = Split-Path -Parent $ManifestPath
  $candidate = Join-Path $manifestDir $RelativePath
  if (!(Test-Path -LiteralPath $candidate)) {
    throw "Manifest-relative path not found: $RelativePath ($candidate)"
  }
  return (Resolve-Path -LiteralPath $candidate).Path
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

function Assert-FileSize([string]$FilePath, [int64]$ExpectedBytes) {
  $actualBytes = (Get-Item -LiteralPath $FilePath).Length
  if ($actualBytes -ne $ExpectedBytes) {
    throw "Byte-size mismatch for $FilePath`nExpected: $ExpectedBytes`nActual:   $actualBytes"
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
  $expectedBytes = [int64](Get-RequiredProperty -Object $Artifact -Name "bytes" -Context "artifact '$id'")

  $fileName = Split-Path -Leaf $url
  $dest = Join-Path $CacheDir $fileName

  if (Test-Path -LiteralPath $dest) {
    Assert-FileSize -FilePath $dest -ExpectedBytes $expectedBytes
    Assert-Sha256 -FilePath $dest -ExpectedHex $sha256
    return $dest
  }

  Write-Host "Downloading $id -> $fileName"
  $lastErrorMessage = ""
  for ($attempt = 1; $attempt -le $DownloadMaxAttempts; $attempt++) {
    try {
      Invoke-WebRequest -Uri $url -OutFile $dest | Out-Null
      Assert-FileSize -FilePath $dest -ExpectedBytes $expectedBytes
      Assert-Sha256 -FilePath $dest -ExpectedHex $sha256
      return $dest
    } catch {
      $lastErrorMessage = $_.Exception.Message
      if (Test-Path -LiteralPath $dest) {
        Remove-Item -Force -LiteralPath $dest
      }
      if ($attempt -lt $DownloadMaxAttempts) {
        Write-Warning "Download attempt $attempt/$DownloadMaxAttempts failed for artifact '$id': $lastErrorMessage. Retrying in $DownloadRetryDelaySeconds seconds."
        Start-Sleep -Seconds $DownloadRetryDelaySeconds
      }
    }
  }
  throw "Failed to download artifact '$id' from $url after $DownloadMaxAttempts attempts. The upstream artifact may have moved or expired; update $ManifestPath with a reachable URL and matching sha256. Original error: $lastErrorMessage"
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

function Get-FrameCompareLauncherEnvironmentValue([string]$Name) {
  return [Environment]::GetEnvironmentVariable($Name, "Process")
}

function Restore-FrameCompareLauncherEnvironmentValue([string]$Name, [object]$Value) {
  if ($null -eq $Value) {
    Remove-Item -LiteralPath "Env:$Name" -ErrorAction SilentlyContinue
    return
  }
  [Environment]::SetEnvironmentVariable($Name, [string]$Value, "Process")
}

$originalPath = Get-FrameCompareLauncherEnvironmentValue -Name "PATH"
$originalPythonUtf8 = Get-FrameCompareLauncherEnvironmentValue -Name "PYTHONUTF8"
$originalPythonDontWriteBytecode = Get-FrameCompareLauncherEnvironmentValue -Name "PYTHONDONTWRITEBYTECODE"
$originalPythonPath = Get-FrameCompareLauncherEnvironmentValue -Name "PYTHONPATH"
$originalVsExtraPluginPath = Get-FrameCompareLauncherEnvironmentValue -Name "VAPOURSYNTH_EXTRA_PLUGIN_PATH"
$originalVsPluginPath = Get-FrameCompareLauncherEnvironmentValue -Name "VAPOURSYNTH_PLUGIN_PATH"
$originalMediaRuntimeFingerprint = Get-FrameCompareLauncherEnvironmentValue -Name "FRAME_COMPARE_MEDIA_RUNTIME_FINGERPRINT"
$originalRuntimeKind = Get-FrameCompareLauncherEnvironmentValue -Name "FRAME_COMPARE_RUNTIME_KIND"
$originalRuntimeFfms2Required = Get-FrameCompareLauncherEnvironmentValue -Name "FRAME_COMPARE_RUNTIME_FFMS2_REQUIRED"
$originalFfmpegExecutable = Get-FrameCompareLauncherEnvironmentValue -Name "FRAME_COMPARE_FFMPEG_EXECUTABLE"
$originalFfprobeExecutable = Get-FrameCompareLauncherEnvironmentValue -Name "FRAME_COMPARE_FFPROBE_EXECUTABLE"

$exitCode = 1
$locationPushed = $false
try {
  $bundleInfoPath = Join-Path $bundleRoot "bundle_info.json"
  if (!(Test-Path -LiteralPath $bundleInfoPath -PathType Leaf)) {
    throw "Bundle runtime identity not found: $bundleInfoPath"
  }
  $bundleInfo = Get-Content -LiteralPath $bundleInfoPath -Raw | ConvertFrom-Json
  $runtimeFingerprintProperty = $bundleInfo.PSObject.Properties["media_runtime_fingerprint"]
  if ($null -eq $runtimeFingerprintProperty -or [string]::IsNullOrWhiteSpace([string]$runtimeFingerprintProperty.Value)) {
    throw "Bundle runtime identity is missing media_runtime_fingerprint: $bundleInfoPath"
  }

  $env:PYTHONUTF8 = "1"
  $env:PYTHONDONTWRITEBYTECODE = "1"
  $env:PYTHONPATH = "$bundleRoot\app\src;$bundleRoot\app\site-packages"
  $env:VAPOURSYNTH_EXTRA_PLUGIN_PATH = "$bundleRoot\vs\extra-plugins"
  Remove-Item Env:VAPOURSYNTH_PLUGIN_PATH -ErrorAction SilentlyContinue
  $env:FRAME_COMPARE_MEDIA_RUNTIME_FINGERPRINT = [string]$runtimeFingerprintProperty.Value
  $env:FRAME_COMPARE_RUNTIME_KIND = "windows-portable"
  $env:FRAME_COMPARE_RUNTIME_FFMS2_REQUIRED = "0"
  $env:FRAME_COMPARE_FFMPEG_EXECUTABLE = "$bundleRoot\ffmpeg\bin\ffmpeg.exe"
  $env:FRAME_COMPARE_FFPROBE_EXECUTABLE = "$bundleRoot\ffmpeg\bin\ffprobe.exe"

  $sitePackages = Join-Path $bundleRoot "app\site-packages"
  $vsPackage = Join-Path $sitePackages "vapoursynth"
  $pathEntries = @(
    (Join-Path $bundleRoot "python"),
    $sitePackages,
    $vsPackage,
    (Join-Path $vsPackage "plugins"),
    (Join-Path $sitePackages "vapoursynth.libs"),
    (Join-Path $sitePackages "vs_placebo"),
    (Join-Path $sitePackages "vs_placebo.libs"),
    (Join-Path $bundleRoot "vs\extra-plugins\lsmas")
  )
  $existingPathEntries = @(
    $pathEntries |
      Where-Object { $_ -and (Test-Path -LiteralPath $_ -PathType Container) } |
      Select-Object -Unique
  )
  $env:PATH = (($existingPathEntries -join ";") + ";" + $env:PATH)

  Push-Location $bundleRoot
  $locationPushed = $true
  & $python -m frame_compare.cli.entry @args
  if ($null -eq $LASTEXITCODE) {
    $exitCode = 1
  } else {
    $exitCode = $LASTEXITCODE
  }
} finally {
  if ($locationPushed) {
    Pop-Location
  }
  Restore-FrameCompareLauncherEnvironmentValue -Name "PATH" -Value $originalPath
  Restore-FrameCompareLauncherEnvironmentValue -Name "PYTHONUTF8" -Value $originalPythonUtf8
  Restore-FrameCompareLauncherEnvironmentValue -Name "PYTHONDONTWRITEBYTECODE" -Value $originalPythonDontWriteBytecode
  Restore-FrameCompareLauncherEnvironmentValue -Name "PYTHONPATH" -Value $originalPythonPath
  Restore-FrameCompareLauncherEnvironmentValue -Name "VAPOURSYNTH_EXTRA_PLUGIN_PATH" -Value $originalVsExtraPluginPath
  Restore-FrameCompareLauncherEnvironmentValue -Name "VAPOURSYNTH_PLUGIN_PATH" -Value $originalVsPluginPath
  Restore-FrameCompareLauncherEnvironmentValue -Name "FRAME_COMPARE_MEDIA_RUNTIME_FINGERPRINT" -Value $originalMediaRuntimeFingerprint
  Restore-FrameCompareLauncherEnvironmentValue -Name "FRAME_COMPARE_RUNTIME_KIND" -Value $originalRuntimeKind
  Restore-FrameCompareLauncherEnvironmentValue -Name "FRAME_COMPARE_RUNTIME_FFMS2_REQUIRED" -Value $originalRuntimeFfms2Required
  Restore-FrameCompareLauncherEnvironmentValue -Name "FRAME_COMPARE_FFMPEG_EXECUTABLE" -Value $originalFfmpegExecutable
  Restore-FrameCompareLauncherEnvironmentValue -Name "FRAME_COMPARE_FFPROBE_EXECUTABLE" -Value $originalFfprobeExecutable
}
exit $exitCode
'@

  $cmd = @'
@echo off
setlocal
set SCRIPT_DIR=%~dp0
set "POWERSHELL_EXE="
where pwsh >nul 2>nul
if %ERRORLEVEL% EQU 0 (
  set "POWERSHELL_EXE=pwsh"
)
if not defined POWERSHELL_EXE if exist "%ProgramFiles%\PowerShell\7\pwsh.exe" set "POWERSHELL_EXE=%ProgramFiles%\PowerShell\7\pwsh.exe"
if not defined POWERSHELL_EXE if exist "%SystemRoot%\System32\WindowsPowerShell\v1.0\powershell.exe" set "POWERSHELL_EXE=%SystemRoot%\System32\WindowsPowerShell\v1.0\powershell.exe"
if not defined POWERSHELL_EXE (
  echo PowerShell was not found. Install PowerShell 7 or restore Windows PowerShell. 1>&2
  exit /b 9009
)
"%POWERSHELL_EXE%" -NoProfile -ExecutionPolicy Bypass -File "%SCRIPT_DIR%frame-compare.ps1" %*
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
set "POWERSHELL_EXE="
where pwsh >nul 2>nul
if %ERRORLEVEL% EQU 0 (
  set "POWERSHELL_EXE=pwsh"
)
if not defined POWERSHELL_EXE if exist "%ProgramFiles%\PowerShell\7\pwsh.exe" set "POWERSHELL_EXE=%ProgramFiles%\PowerShell\7\pwsh.exe"
if not defined POWERSHELL_EXE if exist "%SystemRoot%\System32\WindowsPowerShell\v1.0\powershell.exe" set "POWERSHELL_EXE=%SystemRoot%\System32\WindowsPowerShell\v1.0\powershell.exe"
if not defined POWERSHELL_EXE (
  echo PowerShell was not found. Install PowerShell 7 or restore Windows PowerShell. 1>&2
  exit /b 9009
)
"%POWERSHELL_EXE%" -NoProfile -ExecutionPolicy Bypass -File "%SCRIPT_DIR%frame-compare-update.ps1" %*
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

  $sourceStatus = @(
    & git -C $RepoRoot status --porcelain=v1 --untracked-files=all -- src/frame_compare
  )
  Assert-LastExitCode -CommandLabel "inspect Frame Compare source worktree"
  if ($sourceStatus.Count -gt 0) {
    $dirtySourceMessage = (
      "Uncommitted changes exist under src/frame_compare; the portable bundle " +
      "packages committed HEAD and will exclude them."
    )
    if ($RequireReleasePublicKey) {
      throw $dirtySourceMessage
    }
    Write-Warning $dirtySourceMessage
  }

  $archivePath = Join-Path $CacheDir (
    "frame_compare_source_$([System.Guid]::NewGuid().ToString('N')).tar"
  )
  try {
    & git -C $RepoRoot archive --format=tar --output=$archivePath HEAD src/frame_compare
    Assert-LastExitCode -CommandLabel "git archive Frame Compare source"
    if (!(Get-Command tar -ErrorAction SilentlyContinue)) {
      throw "tar is required on PATH to extract the committed Frame Compare source."
    }
    tar -xf $archivePath -C $appRoot
    Assert-LastExitCode -CommandLabel "extract committed Frame Compare source"
  } finally {
    Remove-Item -Force -LiteralPath $archivePath -ErrorAction SilentlyContinue
  }
  if (!(Test-Path -LiteralPath (Join-Path $srcRoot "frame_compare\\__init__.py"))) {
    throw "Committed Frame Compare source was not extracted into the bundle."
  }
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

  # R78 wheels carry the runtime DLL inside the vapoursynth package directory.
  # The launcher and validation PATH include this directory for Windows DLL lookup.
  $vsDllPackage = Join-Path $sitePackages "vapoursynth\\libvapoursynth.dll"
  if (!(Test-Path -LiteralPath $vsDllPackage)) {
    throw "libvapoursynth.dll not found after wheel install in expected R78 package layout: $vsDllPackage"
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
    $expectedBytes = [int64](Get-RequiredProperty -Object $artifact -Name "bytes" -Context "artifact '$artifactId'")
    Assert-FileSize -FilePath $wheelPath -ExpectedBytes $expectedBytes
    Assert-Sha256 -FilePath $wheelPath -ExpectedHex $sha256
    uv pip install --reinstall --strict --no-deps --target $sitePackages $wheelPath
    Assert-LastExitCode -CommandLabel "uv pip install $artifactId"
  }
}

function Set-BundleRuntimeEnvironment([string]$BundleRoot) {
  $bundleInfoPath = Join-Path $BundleRoot "bundle_info.json"
  if (!(Test-Path -LiteralPath $bundleInfoPath -PathType Leaf)) {
    throw "Bundle runtime identity not found: $bundleInfoPath"
  }
  $bundleInfo = Get-Content -LiteralPath $bundleInfoPath -Raw | ConvertFrom-Json
  $runtimeFingerprintProperty = $bundleInfo.PSObject.Properties["media_runtime_fingerprint"]
  if ($null -eq $runtimeFingerprintProperty -or [string]::IsNullOrWhiteSpace([string]$runtimeFingerprintProperty.Value)) {
    throw "Bundle runtime identity is missing media_runtime_fingerprint: $bundleInfoPath"
  }

  $env:PYTHONUTF8 = "1"
  $env:PYTHONDONTWRITEBYTECODE = "1"
  $env:PYTHONPATH = "$BundleRoot\app\src;$BundleRoot\app\site-packages"
  $env:VAPOURSYNTH_EXTRA_PLUGIN_PATH = "$BundleRoot\vs\extra-plugins"
  Remove-Item Env:VAPOURSYNTH_PLUGIN_PATH -ErrorAction SilentlyContinue
  $env:FRAME_COMPARE_MEDIA_RUNTIME_FINGERPRINT = [string]$runtimeFingerprintProperty.Value
  $env:FRAME_COMPARE_RUNTIME_KIND = "windows-portable"
  $env:FRAME_COMPARE_RUNTIME_FFMS2_REQUIRED = "0"
  $env:FRAME_COMPARE_FFMPEG_EXECUTABLE = "$BundleRoot\ffmpeg\bin\ffmpeg.exe"
  $env:FRAME_COMPARE_FFPROBE_EXECUTABLE = "$BundleRoot\ffmpeg\bin\ffprobe.exe"

  $sitePackages = Join-Path $BundleRoot "app\site-packages"
  $vsPackage = Join-Path $sitePackages "vapoursynth"
  $pathEntries = @(
    (Join-Path $BundleRoot "python"),
    $sitePackages,
    $vsPackage,
    (Join-Path $vsPackage "plugins"),
    (Join-Path $sitePackages "vapoursynth.libs"),
    (Join-Path $sitePackages "vs_placebo"),
    (Join-Path $sitePackages "vs_placebo.libs"),
    (Join-Path $BundleRoot "vs\extra-plugins\lsmas")
  )
  $existingEntries = @(
    $pathEntries |
      Where-Object { $_ -and (Test-Path -LiteralPath $_ -PathType Container) } |
      Select-Object -Unique
  )
  $env:PATH = (($existingEntries -join ";") + ";" + $env:PATH)
}

function Get-ProcessEnvironmentValue([string]$Name) {
  return [Environment]::GetEnvironmentVariable($Name, "Process")
}

function Restore-ProcessEnvironmentValue([string]$Name, [AllowNull()][string]$Value) {
  if ($null -eq $Value) {
    Remove-Item -Path "Env:$Name" -ErrorAction SilentlyContinue
    return
  }
  Set-Item -Path "Env:$Name" -Value $Value
}

function Write-BundleInfo([string]$BundleRoot, [string]$AppVersion) {
  $requirementsLockPath = Join-Path $BundleRoot "requirements.lock.txt"
  if (!(Test-Path -LiteralPath $requirementsLockPath)) {
    throw "requirements.lock.txt not found for bundle info: $requirementsLockPath"
  }

  $manifest = Get-Manifest
  $manifestVersion = [int](Get-RequiredProperty -Object $manifest -Name "manifest_version" -Context "manifest")
  if ($manifestVersion -ne 2) {
    throw "Unsupported portable manifest version '$manifestVersion' (expected 2)."
  }
  $bundleContract = Get-RequiredProperty -Object $manifest -Name "bundle" -Context "manifest"
  $manifestFingerprints = Get-RequiredProperty -Object $bundleContract -Name "runtime_fingerprints" -Context "manifest.bundle"
  $runtimeFingerprints = [ordered]@{}
  foreach ($scope in @("analysis", "probe", "alignment", "index", "full")) {
    $runtimeFingerprints[$scope] = Get-RequiredStringProperty -Object $manifestFingerprints -Name $scope -Context "manifest.bundle.runtime_fingerprints"
  }

  $requirementsLockSha256 = (Get-FileHash -Algorithm SHA256 -LiteralPath $requirementsLockPath).Hash.ToLowerInvariant()
  $bundleInfo = [ordered]@{
    schema_version = 2
    bundle_kind = "full"
    app_version = $AppVersion
    requirements_lock_sha256 = $requirementsLockSha256
    manifest_version = $manifestVersion
    platform = "windows-x64"
    media_runtime_fingerprint = $runtimeFingerprints["full"]
    media_runtime_fingerprints = $runtimeFingerprints
  }
  $bundleInfoPath = Join-Path $BundleRoot "bundle_info.json"
  $bundleInfoJson = $bundleInfo | ConvertTo-Json -Depth 4
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
  $python = Join-Path $BundleRoot "python\python.exe"
  if (!(Test-Path -LiteralPath $python)) {
    throw "Embedded python not found for runtime validation: $python"
  }

  $originalPath = Get-ProcessEnvironmentValue -Name "PATH"
  $originalPythonUtf8 = Get-ProcessEnvironmentValue -Name "PYTHONUTF8"
  $originalPythonDontWriteBytecode = Get-ProcessEnvironmentValue -Name "PYTHONDONTWRITEBYTECODE"
  $originalPythonPath = Get-ProcessEnvironmentValue -Name "PYTHONPATH"
  $originalVsExtraPluginPath = Get-ProcessEnvironmentValue -Name "VAPOURSYNTH_EXTRA_PLUGIN_PATH"
  $originalVsPluginPath = Get-ProcessEnvironmentValue -Name "VAPOURSYNTH_PLUGIN_PATH"
  $originalMediaRuntimeFingerprint = Get-ProcessEnvironmentValue -Name "FRAME_COMPARE_MEDIA_RUNTIME_FINGERPRINT"
  $originalRuntimeKind = Get-ProcessEnvironmentValue -Name "FRAME_COMPARE_RUNTIME_KIND"
  $originalRuntimeFfms2Required = Get-ProcessEnvironmentValue -Name "FRAME_COMPARE_RUNTIME_FFMS2_REQUIRED"
  $originalFfmpegExecutable = Get-ProcessEnvironmentValue -Name "FRAME_COMPARE_FFMPEG_EXECUTABLE"
  $originalFfprobeExecutable = Get-ProcessEnvironmentValue -Name "FRAME_COMPARE_FFPROBE_EXECUTABLE"

  $ffmpeg = Join-Path $BundleRoot "ffmpeg\bin\ffmpeg.exe"
  $mediaPath = Join-Path $BundleRoot "runtime-smoke.mp4"
  $legacyMediaIndexPath = "$mediaPath.lwi"
  $smokePath = Join-Path $BundleRoot "runtime-smoke.py"
  $locationPushed = $false
  try {
    Set-BundleRuntimeEnvironment -BundleRoot $BundleRoot
    Push-Location $BundleRoot
    $locationPushed = $true

    if (!(Test-Path -LiteralPath $ffmpeg -PathType Leaf)) {
      throw "Bundled FFmpeg executable not found: $ffmpeg"
    }
    & $ffmpeg -hide_banner -loglevel error -f lavfi -i "testsrc2=size=32x32:rate=1:duration=1" -frames:v 1 -pix_fmt yuv420p -y $mediaPath
    Assert-LastExitCode -CommandLabel "ffmpeg tiny media generation"

    $smokeScript = @'
from __future__ import annotations

import importlib.metadata
import os
import subprocess
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


def prove_runtime_contract() -> None:
    from frame_compare.utils.subproc import resolve_executable
    from frame_compare.vs.runtime_contract import (
        VS_PLACEBO_RELEASE,
        WINDOWS_FFMPEG_RELEASE,
        media_runtime_fingerprint,
        supported_media_runtime_report,
    )

    expected = media_runtime_fingerprint("full")
    observed = os.environ.get("FRAME_COMPARE_MEDIA_RUNTIME_FINGERPRINT", "")
    assert_true(observed == expected, f"runtime fingerprint mismatch: expected={expected} observed={observed}")
    assert_true(os.environ.get("FRAME_COMPARE_RUNTIME_KIND") == "windows-portable", "runtime kind mismatch")
    assert_true(os.environ.get("FRAME_COMPARE_RUNTIME_FFMS2_REQUIRED") == "0", "Windows FFMS2 policy mismatch")
    assert_true(importlib.metadata.version("vs-placebo") == VS_PLACEBO_RELEASE, "vs-placebo distribution mismatch")

    bundle_root = Path(sys.executable).resolve().parent.parent
    bundled_ffmpeg_bin = os.path.normcase(os.path.normpath(str(bundle_root / "ffmpeg" / "bin")))
    path_entries = {
        os.path.normcase(os.path.normpath(entry))
        for entry in os.environ.get("PATH", "").split(os.pathsep)
        if entry
    }
    assert_true(bundled_ffmpeg_bin not in path_entries, "standalone FFmpeg directory leaked onto PATH")

    ffmpeg = Path(resolve_executable("ffmpeg")).resolve()
    ffprobe = Path(resolve_executable("ffprobe")).resolve()
    assert_true(ffmpeg == (bundle_root / "ffmpeg" / "bin" / "ffmpeg.exe").resolve(), f"unexpected FFmpeg path: {ffmpeg}")
    assert_true(ffprobe == (bundle_root / "ffmpeg" / "bin" / "ffprobe.exe").resolve(), f"unexpected ffprobe path: {ffprobe}")
    version_line = subprocess.check_output([str(ffmpeg), "-version"], text=True, timeout=15).splitlines()[0]
    assert_true(WINDOWS_FFMPEG_RELEASE in version_line, f"unexpected FFmpeg version: {version_line}")
    report = supported_media_runtime_report()
    assert_true(report["fingerprints"]["full"] == expected, "runtime report fingerprint mismatch")
    proof(f"runtime_contract=ok fingerprint={expected} ffmpeg={version_line}")


def prove_vapoursynth_environment() -> None:
    import vapoursynth as vs

    core = vs.core
    version = getattr(vs, "__version__", None)
    api_version = getattr(vs, "__api_version__", None)
    version_major = getattr(version, "release_major", None)
    version_minor = getattr(version, "release_minor", None)
    api_major = getattr(api_version, "api_major", None)
    plugin_dir = Path(vs.get_plugin_dir())
    extra_plugin_path = os.environ.get("VAPOURSYNTH_EXTRA_PLUGIN_PATH", "")
    plugins = list(core.plugins())
    plugin_namespaces = sorted(plugin.namespace for plugin in plugins)

    assert_true(version_major == 78 and version_minor == 0, f"expected VapourSynth R78, got {version!r}")
    assert_true(api_major == 4, f"expected VapourSynth API 4, got {api_version!r}")
    assert_true(plugin_dir.is_dir(), f"vapoursynth.get_plugin_dir() is not a directory: {plugin_dir}")
    assert_true("vapoursynth" in str(plugin_dir).replace("\\", "/"), f"unexpected plugin dir: {plugin_dir}")
    assert_true(extra_plugin_path, "VAPOURSYNTH_EXTRA_PLUGIN_PATH is not set")
    assert_true("VAPOURSYNTH_PLUGIN_PATH" not in os.environ, "legacy VAPOURSYNTH_PLUGIN_PATH should not be set")
    assert_true("lsmas" in plugin_namespaces, f"lsmas plugin missing: {plugin_namespaces}")
    assert_true("placebo" in plugin_namespaces, f"placebo plugin missing: {plugin_namespaces}")
    assert_true("ffms2" not in plugin_namespaces, "FFMS2 must remain excluded from the Windows baseline")

    proof(f"vapoursynth_import=ok version=R{version_major} api={api_major}")
    proof(f"plugin_dir={plugin_dir}")
    proof(f"extra_plugin_path={extra_plugin_path}")
    proof(f"core_plugins={','.join(plugin_namespaces)}")


def prove_lwlibavsource(media_path: Path) -> None:
    import vapoursynth as vs

    from frame_compare.vs.env import candidate_lsmas_plugin_path_details, try_load_lsmas_plugin
    from frame_compare.vs.source import load_source, source_index_path

    core = vs.core
    lsmas_loaded_path = None
    if not (hasattr(core, "lsmas") and hasattr(core.lsmas, "LWLibavSource")):
        lsmas_loaded_path = try_load_lsmas_plugin(core)

    assert_true(hasattr(core, "lsmas"), "core.lsmas namespace missing")
    functions = {function.name for function in core.lsmas.functions()}
    assert_true("LWLibavSource" in functions, f"LWLibavSource missing: {sorted(functions)}")
    assert_true("LibavSMASHSource" in functions, f"LibavSMASHSource missing: {sorted(functions)}")

    if media_path.is_file():
        source = load_source(media_path, core=core)
        frame = source.clip.get_frame(0)
        assert_true(frame.width == 32 and frame.height == 32, "LWLibavSource frame render failed")
        assert_true(source.num_frames == 1, f"unexpected source frame count: {source.num_frames}")
        owned_index = source_index_path(media_path)
        assert_true(owned_index.is_file(), f"runtime-specific source index missing: {owned_index}")
        assert_true(not Path(f"{media_path}.lwi").exists(), "legacy unversioned source index was created")
    else:
        candidates = [{"source": candidate.source, "path": candidate.path} for candidate in candidate_lsmas_plugin_path_details()]
        raise AssertionError(f"tiny media proof missing: {media_path}; candidates={candidates}")

    proof(f"lwlibavsource=ok namespace=lsmas loaded_path={lsmas_loaded_path} functions={','.join(sorted(functions))}")


def build_placebo_clip():
    import vapoursynth as vs

    core = vs.core
    assert_true(hasattr(core, "placebo"), "core.placebo namespace missing")
    assert_true(hasattr(core.placebo, "Tonemap"), "core.placebo.Tonemap missing")

    tonemap_clip = core.std.BlankClip(width=16, height=16, format=vs.RGB48, length=1, color=[32768, 32768, 32768])
    tonemap_clip = tonemap_clip.std.SetFrameProps(_Matrix=0, _Range=1, _Transfer=16, _Primaries=9)
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
    functions = {function.name for function in core.placebo.functions()}
    assert_true("Tonemap" in functions, f"core.placebo.Tonemap missing: {sorted(functions)}")
    proof(f"placebo_tonemap_api=ok namespace=placebo functions={','.join(sorted(functions))}")


def prove_placebo_tonemap_frame() -> bool:
    from frame_compare.vs.tonemap_runtime import probe_libplacebo_runtime

    if not probe_libplacebo_runtime():
        proof("placebo_direct_frame=skipped reason=vulkan_runtime_unavailable")
        return False

    direct_out, _tonemap_clip = build_placebo_clip()
    direct_frame = direct_out.get_frame(0)
    assert_true(direct_frame.width == 16 and direct_frame.height == 16, "placebo direct frame render failed")
    assert_true(direct_frame.format.bits_per_sample >= 10, "placebo unexpectedly reduced output below 10-bit")
    proof(f"placebo_direct_frame=ok format={direct_frame.format.name} bits={direct_frame.format.bits_per_sample}")
    return True


def prove_apply_tonemap_frame() -> None:
    import vapoursynth as vs

    from frame_compare.vs.tonemap import _libplacebo_runtime_usable, apply_tonemap
    from frame_compare.vs.types import TonemapSettings

    core = vs.core
    tonemap_clip = core.std.BlankClip(width=16, height=16, format=vs.RGB48, length=1, color=[32768, 32768, 32768])
    tonemap_clip = tonemap_clip.std.SetFrameProps(_Matrix=0, _Range=1, _Transfer=16, _Primaries=9)

    libplacebo_runtime_usable = _libplacebo_runtime_usable()
    app_out = apply_tonemap(tonemap_clip, TonemapSettings(enabled=True))
    app_frame = app_out.get_frame(0)
    assert_true(app_frame.width == 16 and app_frame.height == 16, "apply_tonemap frame render failed")
    assert_true(app_frame.format.bits_per_sample >= 10, "apply_tonemap unexpectedly reduced output below 10-bit")

    proof(
        "apply_tonemap=ok "
        f"format={app_frame.format.name} bits={app_frame.format.bits_per_sample} "
        f"fallback_aware=true libplacebo_runtime_usable={str(libplacebo_runtime_usable).lower()}"
    )


def prove_qt_media_runtime(media_path: Path) -> None:
    from frame_compare.vspreview.launcher import preload_vapoursynth_runtime

    preload_vapoursynth_runtime()
    proof("qt_media_runtime_preload=ok")

    import PyQt6  # noqa: F401

    proof("pyqt6_import=ok")

    import vspreview  # noqa: F401

    proof("vspreview_pyqt6=ok")
    prove_runtime_contract()
    prove_vapoursynth_environment()
    prove_lwlibavsource(media_path)
    prove_placebo_tonemap_api()
    prove_apply_tonemap_frame()
    prove_placebo_tonemap_frame()
    proof("qt_media_runtime=ok")


phase = sys.argv[1]
media_path = Path(sys.argv[2])
if phase == "package_imports":
    prove_package_imports()
elif phase == "runtime_contract":
    prove_runtime_contract()
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
elif phase == "qt_media_runtime":
    prove_qt_media_runtime(media_path)
else:
    raise AssertionError(f"unknown runtime proof phase: {phase}")
'@
    Set-Content -LiteralPath $smokePath -Value $smokeScript -Encoding UTF8
    Invoke-BundleRuntimeProof -Python $python -SmokePath $smokePath -Phase "package_imports" -MediaPath $mediaPath -Required $true
    Invoke-BundleRuntimeProof -Python $python -SmokePath $smokePath -Phase "runtime_contract" -MediaPath $mediaPath -Required $true
    Invoke-BundleRuntimeProof -Python $python -SmokePath $smokePath -Phase "vapoursynth_environment" -MediaPath $mediaPath -Required $true
    Invoke-BundleRuntimeProof -Python $python -SmokePath $smokePath -Phase "lwlibavsource_frame" -MediaPath $mediaPath -Required $true
    Invoke-BundleRuntimeProof -Python $python -SmokePath $smokePath -Phase "placebo_tonemap_api" -MediaPath $mediaPath -Required $true
    Invoke-BundleRuntimeProof -Python $python -SmokePath $smokePath -Phase "apply_tonemap_frame" -MediaPath $mediaPath -Required $true
    Invoke-BundleRuntimeProof -Python $python -SmokePath $smokePath -Phase "placebo_tonemap_frame" -MediaPath $mediaPath -Required $true
    Invoke-BundleRuntimeProof -Python $python -SmokePath $smokePath -Phase "qt_media_runtime" -MediaPath $mediaPath -Required $true
  } finally {
    Remove-Item -Force -LiteralPath $smokePath -ErrorAction SilentlyContinue
    Remove-Item -Force -LiteralPath $mediaPath -ErrorAction SilentlyContinue
    Remove-Item -Force -LiteralPath $legacyMediaIndexPath -ErrorAction SilentlyContinue
    Get-ChildItem -LiteralPath $BundleRoot -Filter "runtime-smoke.mp4.frame-compare-*.lwi" -File -ErrorAction SilentlyContinue |
      Remove-Item -Force -ErrorAction SilentlyContinue
    if ($locationPushed) {
      Pop-Location
    }
    Restore-ProcessEnvironmentValue -Name "PATH" -Value $originalPath
    Restore-ProcessEnvironmentValue -Name "PYTHONUTF8" -Value $originalPythonUtf8
    Restore-ProcessEnvironmentValue -Name "PYTHONDONTWRITEBYTECODE" -Value $originalPythonDontWriteBytecode
    Restore-ProcessEnvironmentValue -Name "PYTHONPATH" -Value $originalPythonPath
    Restore-ProcessEnvironmentValue -Name "VAPOURSYNTH_EXTRA_PLUGIN_PATH" -Value $originalVsExtraPluginPath
    Restore-ProcessEnvironmentValue -Name "VAPOURSYNTH_PLUGIN_PATH" -Value $originalVsPluginPath
    Restore-ProcessEnvironmentValue -Name "FRAME_COMPARE_MEDIA_RUNTIME_FINGERPRINT" -Value $originalMediaRuntimeFingerprint
    Restore-ProcessEnvironmentValue -Name "FRAME_COMPARE_RUNTIME_KIND" -Value $originalRuntimeKind
    Restore-ProcessEnvironmentValue -Name "FRAME_COMPARE_RUNTIME_FFMS2_REQUIRED" -Value $originalRuntimeFfms2Required
    Restore-ProcessEnvironmentValue -Name "FRAME_COMPARE_FFMPEG_EXECUTABLE" -Value $originalFfmpegExecutable
    Restore-ProcessEnvironmentValue -Name "FRAME_COMPARE_FFPROBE_EXECUTABLE" -Value $originalFfprobeExecutable
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

function Remove-PythonBytecodeCaches([string]$BundleRoot) {
  $cacheDirs = @(
    Get-ChildItem -LiteralPath $BundleRoot -Recurse -Directory -Filter "__pycache__" |
      Sort-Object FullName -Descending
  )
  foreach ($cacheDir in $cacheDirs) {
    Remove-Item -LiteralPath $cacheDir.FullName -Recurse -Force
  }
  $bytecodeFiles = @(
    Get-ChildItem -LiteralPath $BundleRoot -Recurse -File |
      Where-Object { $_.Extension -in @(".pyc", ".pyo") }
  )
  foreach ($bytecodeFile in $bytecodeFiles) {
    Remove-Item -LiteralPath $bytecodeFile.FullName -Force
  }
}

function Copy-ManifestLicenseFiles(
  [string]$LicensesDir,
  [string]$ArtifactId,
  [string]$Spdx,
  [object[]]$LicenseFiles
) {
  $multipleFiles = $LicenseFiles.Count -gt 1

  foreach ($licenseFile in $LicenseFiles) {
    $relativePath = Get-RequiredStringProperty -Object $licenseFile -Name "path" -Context "artifact '$ArtifactId' license file"
    $expectedSha256 = Get-RequiredStringProperty -Object $licenseFile -Name "sha256" -Context "artifact '$ArtifactId' license file '$relativePath'"
    $resolvedPath = Resolve-ManifestRelativePath -RelativePath $relativePath
    Assert-Sha256 -FilePath $resolvedPath -ExpectedHex $expectedSha256

    $baseName = [System.IO.Path]::GetFileName($resolvedPath)
    $destName = if ($multipleFiles) {
      "{0}-{1}--{2}" -f $ArtifactId, $Spdx, $baseName
    } else {
      "{0}-{1}{2}" -f $ArtifactId, $Spdx, [System.IO.Path]::GetExtension($baseName)
    }

    Copy-Item -Force -LiteralPath $resolvedPath -Destination (Join-Path $LicensesDir $destName)
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

    $manifestLicenseFiles = Get-OptionalProperty -Object $license -Name "files"
    if ($null -ne $manifestLicenseFiles) {
      Copy-ManifestLicenseFiles -LicensesDir $licensesDir -ArtifactId $id -Spdx $spdx -LicenseFiles @($manifestLicenseFiles)
    }
  }
}

function Copy-RequiredQtLicenseDirectories([string]$BundleRoot) {
  $sitePackages = Join-Path $BundleRoot "app\\site-packages"
  $licensesDir = Join-Path $BundleRoot "licenses"
  $required = @(
    @{ Pattern = "pyqt6-*.dist-info"; Destination = "PyQt6" },
    @{ Pattern = "pyqt6_qt6-*.dist-info"; Destination = "Qt" },
    @{ Pattern = "pyqt6_sip-*.dist-info"; Destination = "PyQt6-sip" }
  )

  foreach ($entry in $required) {
    $licenseOwners = @(
      Get-ChildItem -LiteralPath $sitePackages -Directory -Filter $entry.Pattern
    )
    if ($licenseOwners.Count -ne 1) {
      throw "Expected exactly one $($entry.Pattern) license owner, found $($licenseOwners.Count)."
    }
    $licenseCandidates = @(
      @(
        (Join-Path $licenseOwners[0].FullName "LICENSE"),
        (Join-Path $licenseOwners[0].FullName "licenses\\LICENSE")
      ) | Where-Object { Test-Path -LiteralPath $_ -PathType Leaf }
    )
    if ($licenseCandidates.Count -ne 1) {
      throw "Expected exactly one license file for $($entry.Pattern), found $($licenseCandidates.Count)."
    }
    $destination = Join-Path $licensesDir $entry.Destination
    Ensure-Directory -Path $destination
    Copy-Item -Force -LiteralPath $licenseCandidates[0] -Destination (
      Join-Path $destination "LICENSE.txt"
    )
  }
}

function Write-BundleInventory([string]$BundleRoot) {
  $python = Join-Path $BundleRoot "python\\python.exe"
  $inventoryScript = Join-Path $RepoRoot "tools\\windows_portable\\write_bundle_inventory.py"
  if (!(Test-Path -LiteralPath $inventoryScript -PathType Leaf)) {
    throw "Bundle inventory owner not found: $inventoryScript"
  }

  $arguments = @(
    $inventoryScript,
    "--bundle-root", $BundleRoot,
    "--manifest", $ManifestPath,
    "--repo-root", $RepoRoot,
    "--output", (Join-Path $BundleRoot "bundle_inventory.json")
  )
  if ($RequireReleasePublicKey) {
    $arguments += "--require-clean-repo"
  }
  & $python -B @arguments
  Assert-LastExitCode -CommandLabel "Windows bundle inventory"
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
  Write-BundleInfo -BundleRoot $OutDir -AppVersion (Get-AppVersionFromSource -RepoRootPath (Join-Path $OutDir "app"))
  Configure-EmbeddedPython -BundleRoot $OutDir
  Assert-BundleRuntime -BundleRoot $OutDir
  Remove-PythonBytecodeCaches -BundleRoot $OutDir

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
  Copy-RequiredQtLicenseDirectories -BundleRoot $OutDir
  Write-BundleInventory -BundleRoot $OutDir

  Write-Host "OK: portable bundle assembled at $OutDir"
}

Main
