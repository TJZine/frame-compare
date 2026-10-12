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
  try {
    $bundleInfo = Get-Content -LiteralPath $bundleInfoPath -Raw |
      ConvertFrom-Json -ErrorAction Stop
    if ($bundleInfo -isnot [PSCustomObject]) {
      throw "bundle_info.json must contain one JSON object"
    }
  } catch {
    throw (
      "The portable bundle is corrupt because bundle_info.json is invalid. " +
      "Rebuild or reinstall the complete portable bundle."
    )
  }
  $runtimeFingerprintProperty = $bundleInfo.PSObject.Properties["media_runtime_fingerprint"]
  if ($null -eq $runtimeFingerprintProperty -or [string]::IsNullOrWhiteSpace([string]$runtimeFingerprintProperty.Value)) {
    throw "Bundle runtime identity is missing media_runtime_fingerprint: $bundleInfoPath"
  }

  $env:PYTHONUTF8 = "1"
  $env:PYTHONDONTWRITEBYTECODE = "1"
  $env:PYTHONPATH = "$bundleRoot\app\src;$bundleRoot\app\site-packages"
  Remove-Item Env:VAPOURSYNTH_EXTRA_PLUGIN_PATH -ErrorAction SilentlyContinue
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
    (Join-Path $sitePackages "vs_placebo.libs")
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
    & git -C $RepoRoot status --porcelain=v1 --untracked-files=all -- src/frame_compare pyproject.toml
  )
  Assert-LastExitCode -CommandLabel "inspect Frame Compare source worktree"
  if ($sourceStatus.Count -gt 0) {
    $dirtySourceMessage = (
      "Uncommitted changes exist under src/frame_compare or pyproject.toml; the portable bundle " +
      "packages committed HEAD and builds wheel dist-info metadata from it, so it will exclude them."
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

function Install-ProjectDistributionMetadata([string]$BundleRoot) {
  # Install only the repository wheel's distribution metadata into the bundle.
  # The application code is copied from committed HEAD into app/src by
  # Copy-RepoApp. The wheel is used here only for the standard
  # importlib.metadata entry-point record; copying its frame_compare package
  # would create a second application-code owner.
  $appRoot = Join-Path $BundleRoot "app"
  $sitePackages = Join-Path $appRoot "site-packages"
  $sourcePackage = Join-Path $appRoot "src\frame_compare"
  $duplicatePackage = Join-Path $sitePackages "frame_compare"
  if (!(Test-Path -LiteralPath (Join-Path $sourcePackage "__init__.py") -PathType Leaf)) {
    throw "Committed Frame Compare source is missing before metadata installation: $sourcePackage"
  }
  if (Test-Path -LiteralPath $duplicatePackage) {
    throw "Refusing to install project metadata over a duplicate app/site-packages/frame_compare package."
  }

  $wheelBuildDir = Join-Path $CacheDir (
    "frame-compare-wheel-$([System.Guid]::NewGuid().ToString('N'))"
  )
  $wheelExtractDir = Join-Path $wheelBuildDir "extract"
  Ensure-Directory -Path $wheelBuildDir
  try {
    Push-Location $RepoRoot
    try {
      uv build --wheel --out-dir $wheelBuildDir
      Assert-LastExitCode -CommandLabel "uv build Frame Compare wheel"
    } finally {
      Pop-Location
    }

    $wheelCandidates = @(
      Get-ChildItem -LiteralPath $wheelBuildDir -File |
        Where-Object { $_.Extension -ieq ".whl" }
    )
    if (
      $wheelCandidates.Count -ne 1 -or
      $wheelCandidates[0].Name -notmatch "^frame_compare-[^\\/]+\.whl$"
    ) {
      throw "Expected exactly one Frame Compare project wheel in $wheelBuildDir, found $($wheelCandidates.Name -join ', ')"
    }
    Expand-ArchiveFile -ArchivePath $wheelCandidates[0].FullName -Destination $wheelExtractDir

    $distInfoDirectories = @(
      Get-ChildItem -LiteralPath $wheelExtractDir -Directory |
        Where-Object { $_.Name -cmatch "^frame_compare-[^\\/]+\.dist-info$" }
    )
    if ($distInfoDirectories.Count -ne 1) {
      throw "Expected exactly one top-level Frame Compare dist-info directory in $wheelExtractDir, found $($distInfoDirectories.Name -join ', ')"
    }
    $distInfoDirectory = $distInfoDirectories[0]
    $entryPointsPath = Join-Path $distInfoDirectory.FullName "entry_points.txt"
    if (!(Test-Path -LiteralPath $entryPointsPath -PathType Leaf)) {
      throw "Frame Compare wheel is missing entry_points.txt: $entryPointsPath"
    }
    $entryPointsText = Get-Content -LiteralPath $entryPointsPath -Raw -Encoding UTF8
    $expectedEntryPoint = "frame-compare-alignment-review = frame_compare.vsview.alignment_review_panel"
    $inVsViewSection = $false
    $entryPointMatches = 0
    foreach ($line in ($entryPointsText -split "`r?`n")) {
      $trimmedLine = $line.Trim()
      if ($trimmedLine.StartsWith("[") -and $trimmedLine.EndsWith("]")) {
        $inVsViewSection = $trimmedLine -ceq "[vsview]"
        continue
      }
      if ($inVsViewSection -and $trimmedLine -ceq $expectedEntryPoint) {
        $entryPointMatches++
      }
    }
    if ($entryPointMatches -ne 1) {
      throw "Frame Compare wheel entry_points.txt is missing the exact VSView registration: $expectedEntryPoint"
    }

    $destination = Join-Path $sitePackages $distInfoDirectory.Name
    if (Test-Path -LiteralPath $destination) {
      throw "Frame Compare dist-info destination already exists: $destination"
    }
    Copy-Item -Recurse -LiteralPath $distInfoDirectory.FullName -Destination $sitePackages
    if (!(Test-Path -LiteralPath $destination -PathType Container)) {
      throw "Frame Compare dist-info metadata was not copied to the bundle: $destination"
    }

    if (Test-Path -LiteralPath $duplicatePackage) {
      throw "Project wheel metadata installation created an unexpected app/site-packages/frame_compare package."
    }
    Write-Host "WINDOWS_BUNDLE_PROOF project_metadata=ok entry_point=frame-compare-alignment-review source=app/src"
  } finally {
    if (Test-Path -LiteralPath $wheelBuildDir) {
      Remove-Item -Recurse -Force -LiteralPath $wheelBuildDir
    }
  }
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
    uv export --frozen --no-dev --no-emit-project --no-emit-package vapoursynth-lsmas --extra vsview --format requirements.txt --output-file $reqFile | Out-Null
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

  # R81 wheels carry the runtime DLL inside the vapoursynth package directory.
  # The launcher and validation PATH include this directory for Windows DLL lookup.
  $vsDllPackage = Join-Path $sitePackages "vapoursynth\\libvapoursynth.dll"
  if (!(Test-Path -LiteralPath $vsDllPackage)) {
    throw "libvapoursynth.dll not found after wheel install in expected R81 package layout: $vsDllPackage"
  }

  Install-ProjectDistributionMetadata -BundleRoot $BundleRoot
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

function Remove-UnusedQtWebEngineRuntime([string]$BundleRoot) {
  $sitePackages = Join-Path $BundleRoot "app\site-packages"
  $pySideRoot = [System.IO.Path]::Combine($sitePackages, "PySide6")
  if (!(Test-Path -LiteralPath $pySideRoot -PathType Container)) {
    throw "PySide6 package directory not found: $pySideRoot"
  }

  $resolvedSitePackages = [System.IO.Path]::GetFullPath($sitePackages)
  $resolvedPySideRoot = (Resolve-Path -LiteralPath $pySideRoot).Path
  $sitePackagesPrefix = $resolvedSitePackages.TrimEnd(
    [System.IO.Path]::DirectorySeparatorChar,
    [System.IO.Path]::AltDirectorySeparatorChar
  ) + [System.IO.Path]::DirectorySeparatorChar
  if (!$resolvedPySideRoot.StartsWith($sitePackagesPrefix, [System.StringComparison]::OrdinalIgnoreCase)) {
    throw "Refusing to trim Qt runtime outside bundle site-packages: $resolvedPySideRoot"
  }

  $chromiumRuntimeNames = @(
    "icudtl.dat",
    "v8_context_snapshot.bin",
    "v8_context_snapshot.debug.bin"
  )
  $excludedFiles = @(
    Get-ChildItem -LiteralPath $resolvedPySideRoot -Recurse -File |
      Where-Object {
        $_.FullName.Substring($resolvedPySideRoot.Length + 1) -match "(?i)webengine" -or
        ($_.Directory.Name -eq "resources" -and $_.Name -in $chromiumRuntimeNames)
      }
  )
  $excludedBytes = [int64](($excludedFiles | Measure-Object -Property Length -Sum).Sum)
  if ($excludedFiles.Count -ne 123 -or $excludedBytes -ne 359205252) {
    throw "Unexpected Qt WebEngine deployment surface: files=$($excludedFiles.Count) bytes=$excludedBytes"
  }
  foreach ($file in $excludedFiles) {
    Remove-Item -Force -LiteralPath $file.FullName
  }

  $remainingFiles = @(
    Get-ChildItem -LiteralPath $resolvedPySideRoot -Recurse -File |
      Where-Object {
        $_.FullName.Substring($resolvedPySideRoot.Length + 1) -match "(?i)webengine" -or
        ($_.Directory.Name -eq "resources" -and $_.Name -in $chromiumRuntimeNames)
      }
  )
  if ($remainingFiles.Count -ne 0) {
    throw "Qt WebEngine deployment exclusion was incomplete: $($remainingFiles.FullName -join ', ')"
  }
  Write-Host "WINDOWS_BUNDLE_PROOF qt_webengine_deployment=excluded files=$($excludedFiles.Count) bytes=$excludedBytes"
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
  Remove-Item Env:VAPOURSYNTH_EXTRA_PLUGIN_PATH -ErrorAction SilentlyContinue
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
    (Join-Path $sitePackages "vs_placebo.libs")
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
    schema_version = 3
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

function Invoke-VSViewOffscreenLaunchProof(
  [string]$Python,
  [string]$SessionPath,
  [string]$BundleRoot
) {
  $stdoutPath = Join-Path $BundleRoot "runtime-smoke-vsview.stdout.log"
  $stderrPath = Join-Path $BundleRoot "runtime-smoke-vsview.stderr.log"
  $originalQtPlatform = Get-ProcessEnvironmentValue -Name "QT_QPA_PLATFORM"
  $originalNoColor = Get-ProcessEnvironmentValue -Name "NO_COLOR"
  $process = $null
  $timedOut = $false
  try {
    $env:QT_QPA_PLATFORM = "offscreen"
    $env:NO_COLOR = "1"
    $quotedSessionPath = '"' + $SessionPath + '"'
    $process = Start-Process -FilePath $Python -ArgumentList @(
      "-m",
      "frame_compare.vsview.launcher",
      "-vv",
      "--no-settings",
      $quotedSessionPath
    ) -NoNewWindow -PassThru -RedirectStandardOutput $stdoutPath -RedirectStandardError $stderrPath
    $timedOut = -not $process.WaitForExit(20000)
  } finally {
    if ($null -ne $process -and -not $process.HasExited) {
      Stop-Process -Id $process.Id -Force -ErrorAction SilentlyContinue
      if (-not $process.WaitForExit(10000)) {
        throw "VSView offscreen proof process did not terminate after forced cleanup."
      }
    }
    Restore-ProcessEnvironmentValue -Name "QT_QPA_PLATFORM" -Value $originalQtPlatform
    Restore-ProcessEnvironmentValue -Name "NO_COLOR" -Value $originalNoColor
  }

  $stdout = if (Test-Path -LiteralPath $stdoutPath) { Get-Content -LiteralPath $stdoutPath -Raw } else { "" }
  $stderr = if (Test-Path -LiteralPath $stderrPath) { Get-Content -LiteralPath $stderrPath -Raw } else { "" }
  $combined = "$stdout`n$stderr"
  $normalizedCombined = ($combined -replace "\s+", " ").Trim()
  Write-Host $combined

  if (-not $timedOut) {
    throw "VSView offscreen proof exited before the expected steady-state GUI timeout."
  }
  foreach ($marker in @(
    "VSView is open",
    "Script execution completed",
    "Switching to video output",
    "Frame 0 rendered"
  )) {
    if (-not $normalizedCombined.Contains($marker)) {
      throw "VSView offscreen proof marker missing: $marker"
    }
  }
  $errorLines = @($combined -split "`r?`n" | Where-Object { $_ -match "(?i)\bERROR\b" })
  if ($errorLines.Count -gt 0) {
    throw "VSView offscreen proof emitted ERROR output: $($errorLines -join ' | ')"
  }
  if ($null -ne $process -and -not $process.HasExited) {
    throw "VSView offscreen proof left its process running."
  }
  Write-Host "WINDOWS_BUNDLE_PROOF vsview_gui_launch=ok platform=offscreen timeout=expected cleanup=ok"
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
  $comparisonOneMediaPath = Join-Path $BundleRoot "runtime-smoke-comparison-1.mp4"
  $comparisonTwoMediaPath = Join-Path $BundleRoot "runtime-smoke-comparison-2.mp4"
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
    & $ffmpeg -hide_banner -loglevel error -f lavfi -i "testsrc2=size=64x64:rate=1:duration=3" -frames:v 3 -pix_fmt yuv420p -y $mediaPath
    Assert-LastExitCode -CommandLabel "ffmpeg tiny media generation"
    Copy-Item -LiteralPath $mediaPath -Destination $comparisonOneMediaPath
    Copy-Item -LiteralPath $mediaPath -Destination $comparisonTwoMediaPath

    $smokeSource = Join-Path $PSScriptRoot "runtime_smoke.py"
    Copy-Item -LiteralPath $smokeSource -Destination $smokePath -Force
    Invoke-BundleRuntimeProof -Python $python -SmokePath $smokePath -Phase "package_imports" -MediaPath $mediaPath -Required $true
    Invoke-BundleRuntimeProof -Python $python -SmokePath $smokePath -Phase "runtime_contract" -MediaPath $mediaPath -Required $true
    Invoke-BundleRuntimeProof -Python $python -SmokePath $smokePath -Phase "vapoursynth_environment" -MediaPath $mediaPath -Required $true
    Invoke-BundleRuntimeProof -Python $python -SmokePath $smokePath -Phase "lwlibavsource_frame" -MediaPath $mediaPath -Required $true
    Invoke-BundleRuntimeProof -Python $python -SmokePath $smokePath -Phase "placebo_tonemap_api" -MediaPath $mediaPath -Required $true
    Invoke-BundleRuntimeProof -Python $python -SmokePath $smokePath -Phase "apply_tonemap_frame" -MediaPath $mediaPath -Required $true
    Invoke-BundleRuntimeProof -Python $python -SmokePath $smokePath -Phase "placebo_tonemap_frame" -MediaPath $mediaPath -Required $true
    Invoke-BundleRuntimeProof -Python $python -SmokePath $smokePath -Phase "vsview_runtime" -MediaPath $mediaPath -Required $true
    $sessionPaths = @(
      Get-ChildItem -LiteralPath (Join-Path $BundleRoot "runtime-smoke-cache\vsview_sessions") -Filter "vsview_*.py" -File
    )
    if ($sessionPaths.Count -ne 1) {
      throw "Expected exactly one generated VSView smoke session, found $($sessionPaths.Count)."
    }
    Invoke-VSViewOffscreenLaunchProof -Python $python -SessionPath $sessionPaths[0].FullName -BundleRoot $BundleRoot
  } finally {
    Remove-Item -Force -LiteralPath $smokePath -ErrorAction SilentlyContinue
    Remove-Item -Force -LiteralPath $mediaPath -ErrorAction SilentlyContinue
    Remove-Item -Force -LiteralPath $comparisonOneMediaPath -ErrorAction SilentlyContinue
    Remove-Item -Force -LiteralPath $comparisonTwoMediaPath -ErrorAction SilentlyContinue
    Remove-Item -Force -LiteralPath (Join-Path $BundleRoot "runtime-smoke-vsview.stdout.log") -ErrorAction SilentlyContinue
    Remove-Item -Force -LiteralPath (Join-Path $BundleRoot "runtime-smoke-vsview.stderr.log") -ErrorAction SilentlyContinue
    Remove-Item -Force -LiteralPath $legacyMediaIndexPath -ErrorAction SilentlyContinue
    Get-ChildItem -LiteralPath $BundleRoot -Filter "runtime-smoke*.mp4.frame-compare-*.lwi" -File -ErrorAction SilentlyContinue |
      Remove-Item -Force -ErrorAction SilentlyContinue
    Remove-Item -Recurse -Force -LiteralPath (Join-Path $BundleRoot "runtime-smoke-cache") -ErrorAction SilentlyContinue
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

function Assert-RequiredPySideLicenseMetadata([string]$BundleRoot) {
  $sitePackages = Join-Path $BundleRoot "app\\site-packages"
  $licensesDir = Join-Path $BundleRoot "licenses"
  $requiredPatterns = @(
    "pyside6-*.dist-info",
    "pyside6_addons-*.dist-info",
    "pyside6_essentials-*.dist-info",
    "shiboken6-*.dist-info"
  )

  foreach ($pattern in $requiredPatterns) {
    $owners = @(Get-ChildItem -LiteralPath $sitePackages -Directory -Filter $pattern)
    if ($owners.Count -ne 1) {
      throw "Expected exactly one $pattern license owner, found $($owners.Count)."
    }
    $metadataPath = Join-Path $owners[0].FullName "METADATA"
    $metadata = Get-Content -LiteralPath $metadataPath -Raw
    if ($metadata -notmatch "License: LGPL-3.0-only OR GPL-2.0-only OR GPL-3.0-only") {
      throw "Unexpected open-source license metadata for $pattern."
    }
  }

  $lgplNotices = @(Get-ChildItem -LiteralPath $licensesDir -File -Filter "*LGPL-3.0*.txt")
  if ($lgplNotices.Count -lt 4) {
    throw "Expected manifest-verified LGPL-3.0 notices for every PySide6 wheel."
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
  Remove-UnusedQtWebEngineRuntime -BundleRoot $OutDir
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
  Assert-RequiredPySideLicenseMetadata -BundleRoot $OutDir
  Write-BundleInventory -BundleRoot $OutDir

  Write-Host "OK: portable bundle assembled at $OutDir"
}

Main
