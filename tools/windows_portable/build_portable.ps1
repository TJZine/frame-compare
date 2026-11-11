Param(
  [Parameter(Mandatory = $false)]
  [string]$ManifestPath = (Join-Path $PSScriptRoot "manifest.windows-x64.json"),

  [Parameter(Mandatory = $false)]
  [string]$OutDir = (Join-Path $PWD "dist\\frame-compare-portable-win-x64"),

  [Parameter(Mandatory = $false)]
  [string]$CacheDir = (Join-Path $PWD ".portable_cache"),

  [Parameter(Mandatory = $false)]
  [string]$RepoRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot "..\\..")).Path,

  [Parameter(Mandatory = $false)]
  [switch]$RequireReleasePublicKey,

  [string]$ExpectedCommitSha,

  [switch]$AssemblyOnly,
  [string]$RequirementsPath
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest
$PSNativeCommandUseErrorActionPreference = $true
$hasExpectedCommitSha = $PSBoundParameters.ContainsKey("ExpectedCommitSha")

. (Join-Path $PSScriptRoot "version_utils.ps1")
. (Join-Path $PSScriptRoot "path_safety.ps1")
. (Join-Path $PSScriptRoot "portable_launchers.ps1")

# Convert caller-supplied relative paths once, before they are embedded in
# runtime environment variables or passed across process working directories.
$currentLocation = $PWD.ProviderPath
$ManifestPath = [System.IO.Path]::GetFullPath($ManifestPath, $currentLocation)
$OutDir = [System.IO.Path]::GetFullPath($OutDir, $currentLocation)
$CacheDir = [System.IO.Path]::GetFullPath($CacheDir, $currentLocation)
$RepoRoot = [System.IO.Path]::GetFullPath($RepoRoot, $currentLocation)

$OutDir = [System.IO.Path]::TrimEndingDirectorySeparator($OutDir)
$CacheDir = [System.IO.Path]::TrimEndingDirectorySeparator($CacheDir)
$RepoRoot = [System.IO.Path]::TrimEndingDirectorySeparator($RepoRoot)
$currentLocation = [System.IO.Path]::TrimEndingDirectorySeparator($currentLocation)

function Assert-BuildPaths() {
  foreach ($path in @($OutDir, $CacheDir, $RepoRoot, $currentLocation, $PSScriptRoot, (Split-Path -Parent $ManifestPath))) {
    Assert-NoReparsePointAncestor -Path $path -Label "Build path"
  }
  if ($null -ne (Get-Item -LiteralPath $OutDir -Force -ErrorAction SilentlyContinue)) {
    throw "OutDir must not already exist: $OutDir (CacheDir: $CacheDir)"
  }
  if ($OutDir -eq [IO.Path]::GetPathRoot($OutDir)) { throw "Unsafe OutDir: $OutDir" }
  $manifestDir = [IO.Path]::TrimEndingDirectorySeparator((Split-Path -Parent $ManifestPath))
  foreach ($protected in @($currentLocation, $RepoRoot, $CacheDir, $PSScriptRoot, $manifestDir)) {
    if ($OutDir -eq $protected -or (Test-PathWithin $protected $OutDir)) {
      throw "Unsafe OutDir $OutDir contains protected path $protected"
    }
  }
  foreach ($protected in @($CacheDir, $PSScriptRoot, $manifestDir)) {
    if (Test-PathWithin $OutDir $protected) { throw "Unsafe OutDir $OutDir inside $protected" }
  }
  if ((Test-PathWithin $OutDir $RepoRoot) -and
      !(Test-PathWithin $OutDir (Join-Path $RepoRoot "dist"))) {
    throw "OutDir $OutDir inside RepoRoot $RepoRoot must be beneath dist."
  }
}

function Assert-BuildManifest([object]$Manifest) {
  $manifestVersion = Get-RequiredProperty $Manifest "manifest_version" "manifest"
  if (($manifestVersion -isnot [int] -and $manifestVersion -isnot [long]) -or $manifestVersion -ne 2) {
    throw "Unsupported portable manifest version (expected 2)."
  }
  $bundle = Get-RequiredProperty $Manifest "bundle" "manifest"
  $fingerprints = Get-RequiredProperty $bundle "runtime_fingerprints" "manifest.bundle"
  foreach ($scope in @("analysis", "probe", "alignment", "index", "full")) {
    $value = Get-RequiredStringProperty $fingerprints $scope "manifest.bundle.runtime_fingerprints"
    if ($value -cnotmatch '^[a-f0-9]{64}$') { throw "Invalid runtime fingerprint: $scope" }
  }
  $artifacts = @(Get-RequiredProperty $Manifest "artifacts" "manifest")
  if ($artifacts.Count -eq 0) { throw "Manifest artifacts must not be empty." }
  $ids = [Collections.Generic.HashSet[string]]::new([StringComparer]::OrdinalIgnoreCase)
  foreach ($artifact in $artifacts) {
    foreach ($field in @("id", "url", "sha256")) {
      $null = Get-RequiredStringProperty $artifact $field "artifact"
    }
    if ($artifact.id -cnotmatch '^[a-z0-9][a-z0-9._-]*$' -or !$ids.Add($artifact.id)) {
      throw "Invalid or duplicate artifact id: $($artifact.id)"
    }
    $bytes = Get-RequiredProperty $artifact "bytes" "artifact"
    if ($artifact.sha256 -notmatch '^[a-fA-F0-9]{64}$' -or
        ($bytes -isnot [int] -and $bytes -isnot [long]) -or $bytes -le 0) {
      throw "Invalid artifact hash or byte size: $($artifact.id)"
    }
    $uri = $null
    if (![Uri]::TryCreate($artifact.url, [UriKind]::Absolute, [ref]$uri) -or
        $uri.Scheme -notin @("https", "http")) {
      throw "Invalid artifact URL: $($artifact.url)"
    }
    $license = Get-RequiredProperty $artifact "license" "artifact"
    $null = Get-RequiredStringProperty $license "spdx" "artifact.license"
    $null = Get-RequiredStringProperty $license "url" "artifact.license"
    $install = Get-RequiredProperty $artifact "install" "artifact"
    $type = Get-RequiredStringProperty $install "type" "artifact.install"
    if ($type -notin @("extract", "python_wheel")) { throw "Unknown install.type: $type" }
    $destination = Get-OptionalStringProperty $install "destination"
    if ($type -eq "extract" -or $destination -ne "") {
      if ([string]::IsNullOrWhiteSpace($destination) -or
          [IO.Path]::IsPathRooted($destination) -or $destination.Contains(":")) {
        throw "Unsafe artifact destination: $destination"
      }
      $resolved = [IO.Path]::GetFullPath((Join-Path $OutDir $destination))
      if (!(Test-PathWithin $resolved $OutDir)) { throw "Unsafe artifact destination: $destination" }
      foreach ($segment in ($destination -split '[\\/]')) {
        if ($segment -in @("", ".", "..") -or $segment.EndsWith(".") -or
            $segment.EndsWith(" ") -or $segment -match '^(?i:CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])(?:\..*)?$' -or
            $segment.IndexOfAny([IO.Path]::GetInvalidFileNameChars()) -ge 0) {
          throw "Unsafe artifact destination: $destination"
        }
      }
    }
  }
}

function Ensure-Directory([string]$Path) {
  if (!(Test-Path -LiteralPath $Path)) {
    New-Item -ItemType Directory -Path $Path | Out-Null
  }
}

function Get-Manifest([string]$Path) {
  if (!(Test-Path -LiteralPath $Path)) {
    throw "Manifest not found: $Path"
  }
  return (Get-Content -LiteralPath $Path -Raw | ConvertFrom-Json)
}

function Resolve-ManifestRelativePath([string]$ManifestDir, [string]$RelativePath) {
  if ($RelativePath -cnotmatch '\Alicenses/(?:[A-Za-z0-9._-]+/)*[A-Za-z0-9._-]+\z' -or
      $RelativePath -match '(^|/)\.{1,2}(/|$)') {
    throw "Unsafe vendored license path: $RelativePath"
  }
  $candidate = Join-Path $manifestDir $RelativePath
  Assert-NoReparsePointAncestor -Path $candidate -Label "Vendored license path"
  if (!(Test-Path -LiteralPath $candidate -PathType Leaf)) {
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

function Copy-RepoApp([string]$BundleRoot, [string]$CommitSha) {
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
      "packages commit $CommitSha and builds wheel dist-info metadata from it, so it will exclude them."
    )
    if ($RequireReleasePublicKey) {
      throw $dirtySourceMessage
    }
    Write-Warning $dirtySourceMessage
  }

  & $HostPython -B -I -S (Join-Path $PSScriptRoot "portable_bundle.py") install-project `
    --repo $RepoRoot --root $BundleRoot --commit-sha $CommitSha
  Assert-LastExitCode -CommandLabel "project source and metadata projection"
  Write-Host "WINDOWS_BUNDLE_PROOF project_metadata=ok entry_point=frame-compare-alignment-review source=app/src"
}

function Initialize-PortableRuntime([string]$BundleRoot, [string]$CommitSha, [string]$SelectedManifestPath) {
  $arguments = @(
    "assemble", "--repo", $RepoRoot, "--cache", $CacheDir, "--output", $BundleRoot,
    "--commit-sha", $CommitSha, "--manifest", $SelectedManifestPath
  )
  if ($RequirementsPath) {
    $arguments += @("--requirements", $RequirementsPath)
  }
  & $HostPython -B -I -S (Join-Path $PSScriptRoot "portable_runtime.py") @arguments
  Assert-LastExitCode -CommandLabel "portable runtime projection"
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

function Write-BundleInfo([string]$BundleRoot, [string]$AppVersion, [object]$Manifest) {
  $requirementsLockPath = Join-Path $BundleRoot "requirements.lock.txt"
  if (!(Test-Path -LiteralPath $requirementsLockPath)) {
    throw "requirements.lock.txt not found for bundle info: $requirementsLockPath"
  }

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
  $smokePath = Join-Path $BundleRoot "runtime-smoke.py"
  $locationPushed = $false
  try {
    Set-BundleRuntimeEnvironment -BundleRoot $BundleRoot
    Push-Location -LiteralPath $BundleRoot
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
  [string]$ManifestDir,
  [object[]]$LicenseFiles
) {
  $multipleFiles = $LicenseFiles.Count -gt 1

  foreach ($licenseFile in $LicenseFiles) {
    $relativePath = Get-RequiredStringProperty -Object $licenseFile -Name "path" -Context "artifact '$ArtifactId' license file"
    $expectedSha256 = Get-RequiredStringProperty -Object $licenseFile -Name "sha256" -Context "artifact '$ArtifactId' license file '$relativePath'"
    $resolvedPath = Resolve-ManifestRelativePath -ManifestDir $ManifestDir -RelativePath $relativePath
    Assert-Sha256 -FilePath $resolvedPath -ExpectedHex $expectedSha256

    $baseName = [System.IO.Path]::GetFileName($resolvedPath)
    $destName = if ($multipleFiles) {
      "{0}-{1}--{2}" -f $ArtifactId, $Spdx, $baseName
    } else {
      "{0}-{1}{2}" -f $ArtifactId, $Spdx, [System.IO.Path]::GetExtension($baseName)
    }

    if ($destName -cnotmatch '\A[A-Za-z0-9._+() -]+\z' -or $destName -match '[. ]$') {
      throw "Unsafe bundle license filename: $destName"
    }
    $destination = Join-Path $LicensesDir $destName
    if (Test-Path -LiteralPath $destination) { throw "Duplicate bundle license filename: $destName" }
    Copy-Item -LiteralPath $resolvedPath -Destination $destination
  }
}

function Copy-Licenses([string]$BundleRoot, [string]$ManifestDir, [pscustomobject[]]$Artifacts) {
  $licensesDir = Join-Path $BundleRoot "licenses"
  Ensure-Directory -Path $licensesDir
  foreach ($artifact in $Artifacts) {
    $id = Get-RequiredStringProperty -Object $artifact -Name "id" -Context "artifact"
    $license = Get-RequiredProperty -Object $artifact -Name "license" -Context "artifact '$id'"
    $spdx = Get-RequiredStringProperty -Object $license -Name "spdx" -Context "artifact '$id' license"

    $manifestLicenseFiles = Get-OptionalProperty -Object $license -Name "files"
    if ($null -ne $manifestLicenseFiles) {
      Copy-ManifestLicenseFiles -LicensesDir $licensesDir -ArtifactId $id -Spdx $spdx -ManifestDir $ManifestDir -LicenseFiles @($manifestLicenseFiles)
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
    "pyside6_pdf-*.dist-info",
    "pyside6_webengine-*.dist-info",
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
  if ($lgplNotices.Count -lt 6) {
    throw "Expected manifest-verified LGPL-3.0 notices for every PySide6 wheel."
  }
}

function Write-BundleInventory([string]$BundleRoot, [string]$CommitSha) {
  $inventoryScript = Join-Path $RepoRoot "tools\\windows_portable\\write_bundle_inventory.py"
  if (!(Test-Path -LiteralPath $inventoryScript -PathType Leaf)) {
    throw "Bundle inventory owner not found: $inventoryScript"
  }

  $arguments = @(
    $inventoryScript,
    "--bundle-root", $BundleRoot,
    "--manifest", (Join-Path $BundleRoot "manifest.json"),
    "--repo-root", $RepoRoot,
    "--commit-sha", $CommitSha,
    "--output", (Join-Path $BundleRoot "bundle_inventory.json")
  )
  if ($RequireReleasePublicKey) {
    $arguments += "--require-clean-repo"
  }
  & $HostPython -B -I -S @arguments
  Assert-LastExitCode -CommandLabel "Windows bundle inventory"
}

function Main() {
  if ($RequireReleasePublicKey) {
    Assert-ReleasePublicKey
  }

  Assert-BuildPaths
  $useCommittedManifest = $ManifestPath -eq (Join-Path $PSScriptRoot "manifest.windows-x64.json")
  $selectedManifestPath = $ManifestPath
  if (!$useCommittedManifest) {
    $manifest = Get-Manifest -Path $selectedManifestPath
    Assert-BuildManifest -Manifest $manifest
  }
  $commitSha = $ExpectedCommitSha
  if (!$hasExpectedCommitSha -or $RequireReleasePublicKey) {
    $headSha = & git -C $RepoRoot rev-parse HEAD
    Assert-LastExitCode -CommandLabel "resolve portable source commit"
    if (!$hasExpectedCommitSha) {
      $commitSha = $headSha
    }
  }
  if ($commitSha -cnotmatch '\A[a-f0-9]{40}\z') {
    throw "Expected a complete lowercase 40-character source commit SHA."
  }
  if ($RequireReleasePublicKey) {
    if ($commitSha -cne $headSha) {
      throw "Portable release source commit must match the live checkout: expected=$commitSha actual=$headSha"
    }
    if (@(git -C $RepoRoot status --porcelain=v1 --untracked-files=all).Count -gt 0) {
      throw "Portable release builds require a clean, exact source checkout."
    }
  }
  $manifestSnapshot = $null
  $reservedOutput = $null
  try {
    $HostPython = (& uv python find --system --no-project --no-python-downloads 3.13).Trim()
    Assert-LastExitCode -CommandLabel "find the host Python 3.13 interpreter"
    if ($useCommittedManifest) {
      $snapshotPath = Join-Path ([IO.Path]::GetTempPath()) ("frame-compare-manifest-" + [guid]::NewGuid())
      $manifestSnapshot = New-AtomicallyReservedDirectory -Path $snapshotPath -Label "Manifest snapshot"
      & $HostPython -B -I -S (Join-Path $PSScriptRoot "portable_runtime.py") snapshot-manifest `
        --repo $RepoRoot --commit-sha $commitSha --output $manifestSnapshot
      Assert-LastExitCode -CommandLabel "project portable manifest and notices"
      $selectedManifestPath = Join-Path $manifestSnapshot "manifest.windows-x64.json"
      $manifest = Get-Manifest -Path $selectedManifestPath
      Assert-BuildManifest -Manifest $manifest
    }

    $reservedOutput = New-AtomicallyReservedDirectory -Path $OutDir -Label "OutDir"
    Ensure-Directory -Path $CacheDir
    Initialize-PortableRuntime -BundleRoot $OutDir -CommitSha $commitSha -SelectedManifestPath $selectedManifestPath
    Copy-RepoApp -BundleRoot $OutDir -CommitSha $commitSha
    Write-BundleInfo -BundleRoot $OutDir -Manifest $manifest -AppVersion (Get-AppVersionFromSource -RepoRootPath (Join-Path $OutDir "app"))

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
    $artifacts = @(Get-RequiredProperty -Object $manifest -Name "artifacts" -Context "manifest")
    Copy-Licenses -BundleRoot $OutDir -ManifestDir (Split-Path -Parent $selectedManifestPath) -Artifacts $artifacts
    Assert-RequiredPySideLicenseMetadata -BundleRoot $OutDir
    Write-BundleInventory -BundleRoot $OutDir -CommitSha $commitSha

    if (!$AssemblyOnly) {
      Assert-BundleRuntime -BundleRoot $OutDir
      Remove-PythonBytecodeCaches -BundleRoot $OutDir
    }

    Write-Host "OK: portable bundle assembled at $OutDir"
  } catch {
    if ($null -ne $reservedOutput) {
      Remove-Item -Recurse -Force -LiteralPath $reservedOutput
    }
    throw
  } finally {
    if ($null -ne $manifestSnapshot) {
      Remove-Item -Recurse -Force -LiteralPath $manifestSnapshot
    }
  }
}

Main
