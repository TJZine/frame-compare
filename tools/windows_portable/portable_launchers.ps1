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

  Push-Location -LiteralPath $bundleRoot
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
set "SCRIPT_DIR=%~dp0"
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
set "SCRIPT_DIR=%~dp0"
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

  # Use the same CRLF bytes when assembling or independently verifying the bundle.
  foreach ($launcher in @{
    $ps1Path = $ps1
    $cmdPath = $cmd
    $updatePs1Path = $updatePs1
    $updateCmdPath = $updateCmd
  }.GetEnumerator()) {
    $text = ($launcher.Value -replace "\r?\n", "`r`n") + "`r`n"
    [IO.File]::WriteAllText($launcher.Key, $text, [Text.UTF8Encoding]::new($false))
  }
}
