Param(
  [Parameter(Mandatory = $true)]
  [string]$BundleDir,

  [Parameter(Mandatory = $false)]
  [string]$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\\..")).Path,

  [Parameter(Mandatory = $true)]
  [string]$OutFile
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest
$PSNativeCommandUseErrorActionPreference = $true

Add-Type -AssemblyName System.IO.Compression
Add-Type -AssemblyName System.IO.Compression.FileSystem

. (Join-Path $PSScriptRoot "version_utils.ps1")

function Ensure-Directory([string]$Path) {
  if (!(Test-Path -LiteralPath $Path)) {
    New-Item -ItemType Directory -Path $Path | Out-Null
  }
}

function Write-Utf8NoBomFile([string]$Path, [string]$Content) {
  $utf8NoBom = New-Object System.Text.UTF8Encoding($false)
  [System.IO.File]::WriteAllText($Path, $Content, $utf8NoBom)
}

function ConvertTo-PortablePath([string]$PathValue) {
  return ($PathValue -replace "\\", "/")
}

function Get-FromVersionMin([string]$VersionText) {
  $match = [regex]::Match($VersionText, '^(\d+)\.(\d+)')
  if (!$match.Success) {
    throw "Unparseable app version '$VersionText' (expected at least 'MAJOR.MINOR'). Refusing to write from_app_version_min because Test-StringInRange uses [System.Version]::Parse."
  }
  return "{0}.{1}.0" -f $match.Groups[1].Value, $match.Groups[2].Value
}

function Get-ExpectedRequirementsFingerprint([string]$ResolvedBundleDir) {
  $bundleInfoPath = Join-Path $ResolvedBundleDir "bundle_info.json"
  if (Test-Path -LiteralPath $bundleInfoPath) {
    $bundleInfo = Get-Content -LiteralPath $bundleInfoPath -Raw | ConvertFrom-Json
    $fingerprintProp = $bundleInfo.PSObject.Properties["requirements_lock_sha256"]
    if ($null -ne $fingerprintProp -and $null -ne $fingerprintProp.Value) {
      return [string]$fingerprintProp.Value
    }
  }

  $requirementsLock = Join-Path $ResolvedBundleDir "requirements.lock.txt"
  if (!(Test-Path -LiteralPath $requirementsLock)) {
    throw "Could not find requirements fingerprint source under bundle: $ResolvedBundleDir"
  }
  return (Get-FileHash -LiteralPath $requirementsLock -Algorithm SHA256).Hash.ToLowerInvariant()
}

function New-ManifestFiles([string]$SourceRoot, [string]$PayloadRoot) {
  $entries = New-Object 'System.Collections.Generic.List[object]'
  foreach ($sourceFile in (Get-ChildItem -LiteralPath $SourceRoot -Recurse -File | Sort-Object FullName)) {
    $relative = [System.IO.Path]::GetRelativePath($SourceRoot, $sourceFile.FullName)
    if (
      [System.IO.Path]::IsPathRooted($relative) -or
      $relative -eq ".." -or
      $relative.StartsWith("..\\") -or
      $relative.StartsWith("../")
    ) {
      throw "Source file escaped src/frame_compare: $($sourceFile.FullName)"
    }
    $relativePortable = ConvertTo-PortablePath -PathValue $relative
    if (
      $relativePortable -match '(^|/)__pycache__(/|$)' -or
      $relativePortable.EndsWith(".pyc") -or
      $relativePortable.EndsWith(".pyo")
    ) {
      continue
    }
    $payloadRelative = ConvertTo-PortablePath -PathValue $relative
    $manifestPath = "app/src/frame_compare/$payloadRelative"
    $destFile = Join-Path $PayloadRoot $relative
    Ensure-Directory -Path (Split-Path -Parent $destFile)
    Copy-Item -LiteralPath $sourceFile.FullName -Destination $destFile -Force
    $destInfo = Get-Item -LiteralPath $destFile
    $destHash = (Get-FileHash -LiteralPath $destFile -Algorithm SHA256).Hash.ToLowerInvariant()
    $entryRecord = [ordered]@{
      path = $manifestPath
      sha256 = $destHash
      bytes = [int64]$destInfo.Length
    }
    [void]$entries.Add($entryRecord)
  }
  return @($entries.ToArray() | Sort-Object { $_["path"] })
}

function Add-FileToZip(
  [System.IO.Compression.ZipArchive]$Zip,
  [string]$SourceFile,
  [string]$EntryName
) {
  $entry = $Zip.CreateEntry($EntryName, [System.IO.Compression.CompressionLevel]::Optimal)
  $entryStream = $null
  $sourceStream = $null
  try {
    $entryStream = $entry.Open()
    $sourceStream = [System.IO.File]::OpenRead($SourceFile)
    $sourceStream.CopyTo($entryStream)
  } finally {
    if ($null -ne $entryStream) {
      $entryStream.Dispose()
    }
    if ($null -ne $sourceStream) {
      $sourceStream.Dispose()
    }
  }
}

$resolvedBundleDir = (Resolve-Path -LiteralPath $BundleDir).Path
$resolvedRepoRoot = (Resolve-Path -LiteralPath $RepoRoot).Path
$outFilePath = [System.IO.Path]::GetFullPath($OutFile)
$outDir = Split-Path -Parent $outFilePath
if (![string]::IsNullOrWhiteSpace($outDir)) {
  Ensure-Directory -Path $outDir
}

$sourceRoot = Join-Path $resolvedRepoRoot "src\\frame_compare"
if (!(Test-Path -LiteralPath $sourceRoot)) {
  throw "Source package directory not found: $sourceRoot"
}

$stagingRoot = Join-Path ([System.IO.Path]::GetTempPath()) ("FrameCompareUpdateBuild_" + [guid]::NewGuid().ToString("N"))
$zip = $null
try {
  Ensure-Directory -Path $stagingRoot
  $payloadRoot = Join-Path $stagingRoot "payload\\app\\src\\frame_compare"
  Ensure-Directory -Path $payloadRoot

  $manifestFiles = New-ManifestFiles -SourceRoot $sourceRoot -PayloadRoot $payloadRoot
  if ($manifestFiles.Count -eq 0) {
    throw "No files found under src/frame_compare; refusing to create empty update."
  }

  $toAppVersion = Get-AppVersionFromSource -RepoRootPath $resolvedRepoRoot
  $fromAppVersionMin = Get-FromVersionMin -VersionText $toAppVersion
  $requirementsFingerprint = Get-ExpectedRequirementsFingerprint -ResolvedBundleDir $resolvedBundleDir

  $manifest = [ordered]@{
    schema_version = 1
    target_platform = "windows-x64"
    to_app_version = $toAppVersion
    from_app_version_min = $fromAppVersionMin
    from_app_version_max = $null
    expected_requirements_lock_sha256 = $requirementsFingerprint
    signature_algorithm = "rsa-sha256-pkcs1"
    signature_file = "update-manifest.sig"
    payload_root = "payload"
    files = $manifestFiles
  }
  $manifestPath = Join-Path $stagingRoot "update-manifest.json"
  Write-Utf8NoBomFile -Path $manifestPath -Content (($manifest | ConvertTo-Json -Depth 6) + "`n")

  if (Test-Path -LiteralPath $outFilePath) {
    Remove-Item -LiteralPath $outFilePath -Force
  }
  $zip = [System.IO.Compression.ZipFile]::Open($outFilePath, [System.IO.Compression.ZipArchiveMode]::Create)
  foreach ($file in (Get-ChildItem -LiteralPath $stagingRoot -Recurse -File | Sort-Object FullName)) {
    $relative = $file.FullName.Substring($stagingRoot.Length + 1)
    $entryName = ConvertTo-PortablePath -PathValue $relative
    Add-FileToZip -Zip $zip -SourceFile $file.FullName -EntryName $entryName
  }
  Write-Host "Created update package: $outFilePath"
} finally {
  if ($null -ne $zip) {
    $zip.Dispose()
  }
  if (Test-Path -LiteralPath $stagingRoot) {
    Remove-Item -LiteralPath $stagingRoot -Recurse -Force
  }
}
