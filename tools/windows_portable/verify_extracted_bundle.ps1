Param(
  [Parameter(Mandatory = $true)]
  [string]$ZipPath,

  [Parameter(Mandatory = $true)]
  [string]$ExtractRoot,

  [Parameter(Mandatory = $true)]
  [string]$DoctorStdoutPath,

  [Parameter(Mandatory = $true)]
  [string]$DoctorStderrPath,

  [Parameter(Mandatory = $true)]
  [string]$ExpectedCommitSha
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$currentLocation = $PWD.ProviderPath
$ZipPath = [System.IO.Path]::GetFullPath($ZipPath, $currentLocation)
$ExtractRoot = [System.IO.Path]::GetFullPath($ExtractRoot, $currentLocation)
$DoctorStdoutPath = [System.IO.Path]::GetFullPath($DoctorStdoutPath, $currentLocation)
$DoctorStderrPath = [System.IO.Path]::GetFullPath($DoctorStderrPath, $currentLocation)

if ($ExpectedCommitSha -cnotmatch "^[a-f0-9]{40}$") {
  throw "ExpectedCommitSha must be a complete lowercase 40-character commit SHA."
}

if (!(Test-Path -LiteralPath $ZipPath -PathType Leaf)) {
  throw "Portable bundle ZIP not found: $ZipPath"
}

function Test-PathWithin([string]$Path, [string]$Parent) {
  $parentPrefix = $Parent.TrimEnd(
    [System.IO.Path]::DirectorySeparatorChar,
    [System.IO.Path]::AltDirectorySeparatorChar
  ) + [System.IO.Path]::DirectorySeparatorChar
  return $Path.StartsWith($parentPrefix, [System.StringComparison]::OrdinalIgnoreCase)
}

$extractPathRoot = [System.IO.Path]::GetPathRoot($ExtractRoot)
if (
  [string]::IsNullOrWhiteSpace($ExtractRoot) -or
  $ExtractRoot -eq $extractPathRoot -or
  $ExtractRoot -eq $currentLocation -or
  (Test-PathWithin -Path $currentLocation -Parent $ExtractRoot) -or
  (Test-PathWithin -Path $ZipPath -Parent $ExtractRoot)
) {
  throw "ExtractRoot must name a dedicated verification directory: $ExtractRoot"
}
if ($DoctorStdoutPath -eq $DoctorStderrPath) {
  throw "DoctorStdoutPath and DoctorStderrPath must be different files."
}
foreach ($doctorPath in @($DoctorStdoutPath, $DoctorStderrPath)) {
  if ($doctorPath -eq $ZipPath) {
    throw "Doctor output must not overwrite the portable bundle ZIP: $doctorPath"
  }
}
function Assert-CommandSucceeded([string]$Label, [int]$ExitCode) {
  Write-Host "WINDOWS_EXTRACTED_PROOF command=$Label exit_code=$ExitCode"
  if ($ExitCode -ne 0) {
    throw "$Label failed with exit code $ExitCode"
  }
}

Add-Type -AssemblyName System.IO.Compression.FileSystem
Add-Type @"
using System;
using System.Runtime.InteropServices;

public static class FrameCompareNativeDirectory {
    [DllImport("kernel32.dll", CharSet = CharSet.Unicode, SetLastError = true)]
    [return: MarshalAs(UnmanagedType.Bool)]
    public static extern bool CreateDirectory(string path, IntPtr securityAttributes);
}
"@

function New-AtomicallyReservedDirectory([string]$Path) {
  [System.IO.Directory]::CreateDirectory((Split-Path -Parent $Path)) | Out-Null
  if ([FrameCompareNativeDirectory]::CreateDirectory($Path, [IntPtr]::Zero)) {
    return
  }
  $errorCode = [Runtime.InteropServices.Marshal]::GetLastWin32Error()
  if ($errorCode -eq 183) {
    throw "ExtractRoot must not already exist; choose a fresh verification directory: $Path"
  }
  throw [System.ComponentModel.Win32Exception]::new(
    $errorCode,
    "Could not atomically reserve ExtractRoot: $Path"
  )
}

function Assert-SafeWindowsSegment([string]$Segment, [string]$EntryName) {
  if (
    [string]::IsNullOrEmpty($Segment) -or
    $Segment -in @(".", "..") -or
    $Segment.IndexOfAny([System.IO.Path]::GetInvalidFileNameChars()) -ge 0 -or
    $Segment.EndsWith(" ", [System.StringComparison]::Ordinal) -or
    $Segment.EndsWith(".", [System.StringComparison]::Ordinal) -or
    $Segment -match "^(?i:CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])(?:\..*)?$"
  ) {
    throw "Unsafe ZIP entry path: $EntryName"
  }
}

$archive = [System.IO.Compression.ZipFile]::OpenRead($ZipPath)
try {
  $entries = @($archive.Entries | ForEach-Object { $_.FullName })
  $entryCollisions = @(
    $entries |
      Group-Object { $_.ToLowerInvariant() } |
      Where-Object { $_.Count -gt 1 }
  )
  if ($entryCollisions.Count -gt 0) {
    $collisionNames = @($entryCollisions | ForEach-Object { $_.Group -join ", " })
    throw "Duplicate or case-colliding ZIP entries: $($collisionNames -join '; ')"
  }

  $validatedEntries = [Collections.Generic.List[PSCustomObject]]::new()
  $pathKinds = [Collections.Generic.Dictionary[string, string]]::new(
    [System.StringComparer]::OrdinalIgnoreCase
  )
  $pathSpellings = [Collections.Generic.Dictionary[string, string]]::new(
    [System.StringComparer]::OrdinalIgnoreCase
  )
  foreach ($zipEntry in $archive.Entries) {
    $entryName = $zipEntry.FullName
    if (
      -not $entryName.StartsWith(
        "frame-compare-portable-win-x64/",
        [System.StringComparison]::Ordinal
      ) -or
      $entryName.Contains("\") -or
      $entryName.Contains("//")
    ) {
      throw "Unsafe ZIP entry path: $entryName"
    }
    $isDirectory = $entryName.EndsWith("/", [System.StringComparison]::Ordinal)
    if ($isDirectory -and ($zipEntry.Name -ne "" -or $zipEntry.Length -ne 0)) {
      throw "Malformed ZIP directory entry: $entryName"
    }
    $trimmedName = $entryName.TrimEnd("/")
    $pathSegments = @($trimmedName.Split("/"))
    foreach ($segment in $pathSegments) {
      Assert-SafeWindowsSegment -Segment $segment -EntryName $entryName
    }
    for ($index = 0; $index -lt $pathSegments.Count; $index++) {
      $logicalPath = [string]::Join("/", $pathSegments[0..$index])
      $kind = if ($index -eq ($pathSegments.Count - 1) -and -not $isDirectory) {
        "file"
      } else {
        "directory"
      }
      if ($pathKinds.ContainsKey($logicalPath)) {
        if ($pathSpellings[$logicalPath] -cne $logicalPath) {
          throw "Duplicate or case-colliding ZIP paths: $($pathSpellings[$logicalPath]), $logicalPath"
        }
        if ($pathKinds[$logicalPath] -ne $kind) {
          throw "Conflicting ZIP file and directory path: $logicalPath"
        }
      } else {
        $pathKinds.Add($logicalPath, $kind)
        $pathSpellings.Add($logicalPath, $logicalPath)
      }
    }
    $validatedEntries.Add([PSCustomObject]@{
      Entry = $zipEntry
      IsDirectory = $isDirectory
      RelativePath = $trimmedName
    })
  }

  $requiredEntries = @(
    "frame-compare-portable-win-x64/install.cmd",
    "frame-compare-portable-win-x64/install.ps1",
    "frame-compare-portable-win-x64/frame-compare.ps1",
    "frame-compare-portable-win-x64/frame-compare-update.cmd",
    "frame-compare-portable-win-x64/frame-compare-update.ps1",
    "frame-compare-portable-win-x64/bundle_info.json",
    "frame-compare-portable-win-x64/bundle_inventory.json",
    "frame-compare-portable-win-x64/manifest.json",
    "frame-compare-portable-win-x64/licenses/SOURCE_URLS.txt",
    "frame-compare-portable-win-x64/licenses/THIRD_PARTY_NOTICES.txt",
    "frame-compare-portable-win-x64/shim/frame-compare.cmd",
    "frame-compare-portable-win-x64/shim/frame-compare-update.cmd",
    "frame-compare-portable-win-x64/shim/frame-compare-update.ps1"
  )
  foreach ($requiredEntry in $requiredEntries) {
    if ($entries -cnotcontains $requiredEntry) {
      throw "Missing ZIP entry: $requiredEntry"
    }
  }
  Write-Host "WINDOWS_EXTRACTED_PROOF zip_layout=ok zip=$ZipPath"

  New-AtomicallyReservedDirectory -Path $ExtractRoot
  Write-Host "WINDOWS_EXTRACTED_PROOF extraction_root_reserved=ok root=$ExtractRoot"
  foreach ($validatedEntry in $validatedEntries) {
    $destinationPath = [System.IO.Path]::GetFullPath(
      (Join-Path $ExtractRoot ($validatedEntry.RelativePath -replace "/", "\"))
    )
    if (-not (Test-PathWithin -Path $destinationPath -Parent $ExtractRoot)) {
      throw "Unsafe ZIP extraction destination: $($validatedEntry.Entry.FullName)"
    }
    if ($validatedEntry.IsDirectory) {
      [System.IO.Directory]::CreateDirectory($destinationPath) | Out-Null
      continue
    }
    [System.IO.Directory]::CreateDirectory((Split-Path -Parent $destinationPath)) | Out-Null
    $entryStream = $validatedEntry.Entry.Open()
    try {
      $outputStream = [System.IO.FileStream]::new(
        $destinationPath,
        [System.IO.FileMode]::CreateNew,
        [System.IO.FileAccess]::Write,
        [System.IO.FileShare]::None
      )
      try {
        $entryStream.CopyTo($outputStream)
      } finally {
        $outputStream.Dispose()
      }
    } finally {
      $entryStream.Dispose()
    }
  }
} finally {
  $archive.Dispose()
}
Write-Host "WINDOWS_EXTRACTED_PROOF extraction=ok root=$ExtractRoot"

$bundle = (Resolve-Path -LiteralPath (
    Join-Path $ExtractRoot "frame-compare-portable-win-x64"
  )).Path
foreach ($doctorPath in @($DoctorStdoutPath, $DoctorStderrPath)) {
  if ($doctorPath -eq $bundle -or (Test-PathWithin -Path $doctorPath -Parent $bundle)) {
    throw "Doctor output must not overwrite the extracted candidate bundle: $doctorPath"
  }
}
foreach ($directory in @("config", "comparison_videos")) {
  $path = Join-Path $bundle $directory
  if (!(Test-Path -LiteralPath $path -PathType Container)) {
    throw "Missing default workspace directory in extracted ZIP: $path"
  }
}
Write-Host "WINDOWS_EXTRACTED_PROOF workspace_directories=ok bundle=$bundle"

function Read-JsonObject([string]$Path, [string]$Label) {
  try {
    $value = Get-Content -LiteralPath $Path -Raw |
      ConvertFrom-Json -NoEnumerate -ErrorAction Stop
  } catch {
    throw "$Label is not valid JSON: $Path"
  }
  if ($value -isnot [PSCustomObject]) {
    throw "$Label must contain one JSON object: $Path"
  }
  return $value
}

function Get-RequiredProperty([PSCustomObject]$Object, [string]$Name, [string]$Context) {
  $property = $Object.PSObject.Properties[$Name]
  if ($null -eq $property -or $null -eq $property.Value) {
    throw "$Context is missing required property '$Name'."
  }
  return $property.Value
}

function Assert-PropertyPresent([PSCustomObject]$Object, [string]$Name, [string]$Context) {
  if ($null -eq $Object.PSObject.Properties[$Name]) {
    throw "$Context is missing required property '$Name'."
  }
}

function Get-RequiredString([PSCustomObject]$Object, [string]$Name, [string]$Context) {
  $value = Get-RequiredProperty -Object $Object -Name $Name -Context $Context
  if ($value -isnot [string] -or [string]::IsNullOrWhiteSpace($value)) {
    throw "$Context.$Name must be a non-empty string."
  }
  return $value
}

function Get-RequiredObject([PSCustomObject]$Object, [string]$Name, [string]$Context) {
  $value = Get-RequiredProperty -Object $Object -Name $Name -Context $Context
  if ($value -isnot [PSCustomObject]) {
    throw "$Context.$Name must be an object."
  }
  return $value
}

function Get-RequiredArray([PSCustomObject]$Object, [string]$Name, [string]$Context) {
  $value = Get-RequiredProperty -Object $Object -Name $Name -Context $Context
  if ($value -isnot [System.Array]) {
    throw "$Context.$Name must be an array."
  }
  return @($value)
}

function Assert-ExactProperties(
  [PSCustomObject]$Object,
  [string[]]$Expected,
  [string]$Context
) {
  $actual = @($Object.PSObject.Properties.Name)
  $difference = @(Compare-Object -ReferenceObject $Expected -DifferenceObject $actual)
  if ($difference.Count -ne 0) {
    throw "$Context properties do not match schema: expected=$($Expected -join ',') actual=$($actual -join ',')"
  }
}

function Get-RuntimeFingerprints([PSCustomObject]$Object, [string]$Context) {
  $scopes = @("analysis", "probe", "alignment", "index", "full")
  Assert-ExactProperties -Object $Object -Expected $scopes -Context $Context
  $result = @{}
  foreach ($scope in $scopes) {
    $value = Get-RequiredString -Object $Object -Name $scope -Context $Context
    if ($value -cnotmatch "^[a-f0-9]{64}$") {
      throw "$Context.$scope must be a lowercase SHA-256 digest."
    }
    $result[$scope] = $value
  }
  return $result
}

function Assert-MatchingProperty(
  [PSCustomObject]$Left,
  [string]$LeftName,
  [PSCustomObject]$Right,
  [string]$RightName,
  [string]$Context
) {
  if ((Get-RequiredProperty $Left $LeftName $Context) -cne
    (Get-RequiredProperty $Right $RightName $Context)) {
    throw "$Context provenance mismatch: $LeftName"
  }
}

function Assert-OptionalMatchingProperty(
  [PSCustomObject]$Left,
  [PSCustomObject]$Right,
  [string]$Name,
  [string]$Context
) {
  $leftProperty = $Left.PSObject.Properties[$Name]
  $rightProperty = $Right.PSObject.Properties[$Name]
  $rightHasValue = $null -ne $rightProperty -and $null -ne $rightProperty.Value
  if ($rightHasValue -and $rightProperty.Value -is [string]) {
    $rightHasValue = -not [string]::IsNullOrWhiteSpace($rightProperty.Value)
  }
  if ($rightHasValue) {
    if ($null -eq $leftProperty -or $leftProperty.Value -cne $rightProperty.Value) {
      throw "$Context provenance mismatch: $Name"
    }
  } elseif ($null -ne $leftProperty) {
    throw "$Context contains unexpected provenance: $Name"
  }
}

$inventoryPath = Join-Path $bundle "bundle_inventory.json"
$inventory = Read-JsonObject -Path $inventoryPath -Label "Extracted bundle inventory"
Assert-ExactProperties -Object $inventory -Expected @(
  "bundle",
  "corresponding_sources",
  "licenses",
  "manifest_artifacts",
  "python_distributions",
  "schema_version",
  "source_build_install_scripts"
) -Context "bundle_inventory"
if ((Get-RequiredProperty $inventory "schema_version" "bundle_inventory") -ne 2) {
  throw "bundle_inventory.schema_version must be 2."
}

$inventoryBundle = Get-RequiredObject $inventory "bundle" "bundle_inventory"
Assert-ExactProperties -Object $inventoryBundle -Expected @(
  "commit_sha",
  "frame_compare_license",
  "media_runtime_fingerprint",
  "media_runtime_fingerprints",
  "name",
  "platform",
  "requirements_lock_sha256",
  "source_archive_url",
  "version"
) -Context "bundle_inventory.bundle"
$inventoryCommit = Get-RequiredString $inventoryBundle "commit_sha" "bundle_inventory.bundle"
if ($inventoryCommit -cne $ExpectedCommitSha) {
  throw "Bundle inventory commit does not match expected checkout: expected=$ExpectedCommitSha actual=$inventoryCommit"
}
$appVersion = Get-RequiredString $inventoryBundle "version" "bundle_inventory.bundle"
if (
  (Get-RequiredString $inventoryBundle "name" "bundle_inventory.bundle") -cne "Frame Compare" -or
  (Get-RequiredString $inventoryBundle "platform" "bundle_inventory.bundle") -cne "windows-x64" -or
  (Get-RequiredString $inventoryBundle "frame_compare_license" "bundle_inventory.bundle") -cne "GPL-3.0-only" -or
  (Get-RequiredString $inventoryBundle "source_archive_url" "bundle_inventory.bundle") -cne
    "https://github.com/TJZine/frame-compare/archive/$ExpectedCommitSha.tar.gz"
) {
  throw "Bundle inventory application identity or source provenance is invalid."
}
$requirementsSha = Get-RequiredString $inventoryBundle "requirements_lock_sha256" "bundle_inventory.bundle"
$inventoryPrimaryFingerprint = Get-RequiredString $inventoryBundle "media_runtime_fingerprint" "bundle_inventory.bundle"
foreach ($digest in @($requirementsSha, $inventoryPrimaryFingerprint)) {
  if ($digest -cnotmatch "^[a-f0-9]{64}$") {
    throw "Bundle inventory contains a malformed SHA-256 digest."
  }
}
$inventoryFingerprints = Get-RuntimeFingerprints (
  Get-RequiredObject $inventoryBundle "media_runtime_fingerprints" "bundle_inventory.bundle"
) "bundle_inventory.bundle.media_runtime_fingerprints"
if ($inventoryFingerprints["full"] -cne $inventoryPrimaryFingerprint) {
  throw "Bundle inventory primary runtime fingerprint does not match its full scope."
}

$bundleInfo = Read-JsonObject -Path (Join-Path $bundle "bundle_info.json") -Label "bundle_info.json"
Assert-ExactProperties -Object $bundleInfo -Expected @(
  "schema_version",
  "bundle_kind",
  "app_version",
  "requirements_lock_sha256",
  "manifest_version",
  "platform",
  "media_runtime_fingerprint",
  "media_runtime_fingerprints"
) -Context "bundle_info"
if (
  (Get-RequiredProperty $bundleInfo "schema_version" "bundle_info") -ne 2 -or
  (Get-RequiredProperty $bundleInfo "manifest_version" "bundle_info") -ne 2 -or
  (Get-RequiredString $bundleInfo "bundle_kind" "bundle_info") -cne "full" -or
  (Get-RequiredString $bundleInfo "platform" "bundle_info") -cne "windows-x64" -or
  (Get-RequiredString $bundleInfo "app_version" "bundle_info") -cne $appVersion -or
  (Get-RequiredString $bundleInfo "requirements_lock_sha256" "bundle_info") -cne $requirementsSha -or
  (Get-RequiredString $bundleInfo "media_runtime_fingerprint" "bundle_info") -cne $inventoryPrimaryFingerprint
) {
  throw "bundle_info.json does not match the bundle inventory identity."
}
$bundleInfoFingerprints = Get-RuntimeFingerprints (
  Get-RequiredObject $bundleInfo "media_runtime_fingerprints" "bundle_info"
) "bundle_info.media_runtime_fingerprints"

$manifest = Read-JsonObject -Path (Join-Path $bundle "manifest.json") -Label "manifest.json"
if ((Get-RequiredProperty $manifest "manifest_version" "manifest") -ne 2) {
  throw "manifest.manifest_version must be 2."
}
$manifestBundle = Get-RequiredObject $manifest "bundle" "manifest"
if (
  (Get-RequiredString $manifestBundle "platform" "manifest.bundle") -cne "windows" -or
  (Get-RequiredString $manifestBundle "arch" "manifest.bundle") -cne "x64"
) {
  throw "manifest bundle identity does not match windows-x64."
}
$manifestFingerprints = Get-RuntimeFingerprints (
  Get-RequiredObject $manifestBundle "runtime_fingerprints" "manifest.bundle"
) "manifest.bundle.runtime_fingerprints"
foreach ($scope in @("analysis", "probe", "alignment", "index", "full")) {
  if (
    $inventoryFingerprints[$scope] -cne $bundleInfoFingerprints[$scope] -or
    $inventoryFingerprints[$scope] -cne $manifestFingerprints[$scope]
  ) {
    throw "Media-runtime fingerprint mismatch for scope: $scope"
  }
}

$manifestArtifacts = Get-RequiredArray $manifest "artifacts" "manifest"
$inventoryArtifacts = Get-RequiredArray $inventory "manifest_artifacts" "bundle_inventory"
if ($manifestArtifacts.Count -eq 0 -or $inventoryArtifacts.Count -ne $manifestArtifacts.Count) {
  throw "Bundle inventory must cover every manifest artifact exactly once."
}
$manifestArtifactById = [Collections.Generic.Dictionary[string, PSCustomObject]]::new(
  [System.StringComparer]::OrdinalIgnoreCase
)
foreach ($artifact in $manifestArtifacts) {
  if ($artifact -isnot [PSCustomObject]) { throw "manifest artifact must be an object." }
  $artifactId = Get-RequiredString $artifact "id" "manifest artifact"
  if ($manifestArtifactById.ContainsKey($artifactId)) {
    throw "Duplicate or case-colliding manifest artifact id: $artifactId"
  }
  $manifestArtifactById.Add($artifactId, $artifact)
}
$inventoryArtifactIds = [Collections.Generic.HashSet[string]]::new(
  [System.StringComparer]::OrdinalIgnoreCase
)
foreach ($artifact in $inventoryArtifacts) {
  if ($artifact -isnot [PSCustomObject]) { throw "inventory manifest artifact must be an object." }
  foreach ($field in @(
    "binary_bytes", "binary_sha256", "binary_url", "id", "license_spdx",
    "license_url", "name", "source_url", "version"
  )) {
    Get-RequiredProperty $artifact $field "inventory manifest artifact" | Out-Null
  }
  $artifactId = Get-RequiredString $artifact "id" "inventory manifest artifact"
  if (-not $inventoryArtifactIds.Add($artifactId) -or -not $manifestArtifactById.ContainsKey($artifactId)) {
    throw "Duplicate, case-colliding, or unknown inventory manifest artifact id: $artifactId"
  }
  $sourceArtifact = $manifestArtifactById[$artifactId]
  $sourceLicense = Get-RequiredObject $sourceArtifact "license" "manifest artifact $artifactId"
  foreach ($field in @("name", "source_url", "version")) {
    Assert-MatchingProperty $artifact $field $sourceArtifact $field "inventory artifact $artifactId"
  }
  Assert-MatchingProperty $artifact "binary_bytes" $sourceArtifact "bytes" "inventory artifact $artifactId"
  Assert-MatchingProperty $artifact "binary_sha256" $sourceArtifact "sha256" "inventory artifact $artifactId"
  Assert-MatchingProperty $artifact "binary_url" $sourceArtifact "url" "inventory artifact $artifactId"
  Assert-MatchingProperty $artifact "license_spdx" $sourceLicense "spdx" "inventory artifact $artifactId"
  Assert-MatchingProperty $artifact "license_url" $sourceLicense "url" "inventory artifact $artifactId"
  foreach ($field in @(
    "release_date", "source_kind", "source_ref", "source_commit", "source_sha256",
    "source_bytes", "build_source_url", "build_source_commit", "build_source_sha256",
    "build_source_bytes"
  )) {
    Assert-OptionalMatchingProperty $artifact $sourceArtifact $field "inventory artifact $artifactId"
  }
  if (
    (Get-RequiredString $artifact "binary_sha256" "inventory artifact $artifactId") -cnotmatch
      "^[a-f0-9]{64}$" -or
    (
      (Get-RequiredProperty $artifact "binary_bytes" "inventory artifact $artifactId") -isnot [int] -and
      (Get-RequiredProperty $artifact "binary_bytes" "inventory artifact $artifactId") -isnot [long]
    ) -or
    (Get-RequiredProperty $artifact "binary_bytes" "inventory artifact $artifactId") -lt 0
  ) {
    throw "Inventory artifact integrity is malformed: $artifactId"
  }
}

foreach ($collectionName in @("corresponding_sources", "python_distributions")) {
  $records = Get-RequiredArray $inventory $collectionName "bundle_inventory"
  if ($records.Count -eq 0) {
    throw "bundle_inventory.$collectionName must not be empty."
  }
  foreach ($record in $records) {
    if ($record -isnot [PSCustomObject]) {
      throw "bundle_inventory.$collectionName records must be objects."
    }
    foreach ($field in @("name", "source_url", "version")) {
      Get-RequiredString $record $field "bundle_inventory.$collectionName record" | Out-Null
    }
    if ($collectionName -eq "corresponding_sources") {
      foreach ($field in @("license", "sha256")) {
        Get-RequiredString $record $field "bundle_inventory.corresponding_sources record" | Out-Null
      }
      $sourceSha = Get-RequiredString $record "sha256" "bundle_inventory.corresponding_sources record"
      $sourceBytes = Get-RequiredProperty $record "bytes" "bundle_inventory.corresponding_sources record"
      if (
        $sourceSha -cnotmatch "^[a-f0-9]{64}$" -or
        ($sourceBytes -isnot [int] -and $sourceBytes -isnot [long]) -or
        $sourceBytes -lt 0
      ) {
        throw "Bundle inventory corresponding-source integrity is malformed."
      }
    } else {
      Assert-PropertyPresent $record "declared_license" "bundle_inventory.python_distributions record"
      foreach ($field in @("license_classifiers", "license_expression", "project_urls")) {
        Get-RequiredArray $record $field "bundle_inventory.python_distributions record" | Out-Null
      }
      foreach ($projectUrl in (Get-RequiredArray $record "project_urls" "python distribution")) {
        if ($projectUrl -isnot [PSCustomObject]) {
          throw "bundle_inventory python distribution project URL must be an object."
        }
        Get-RequiredString $projectUrl "label" "python distribution project URL" | Out-Null
        Get-RequiredString $projectUrl "url" "python distribution project URL" | Out-Null
      }
    }
  }
}

$manifestSources = Get-RequiredArray $manifest "corresponding_sources" "manifest"
$inventorySources = Get-RequiredArray $inventory "corresponding_sources" "bundle_inventory"
if ($manifestSources.Count -ne $inventorySources.Count) {
  throw "Bundle inventory must cover every corresponding source exactly once."
}
$manifestSourceByIdentity = [Collections.Generic.Dictionary[string, PSCustomObject]]::new(
  [System.StringComparer]::OrdinalIgnoreCase
)
foreach ($source in $manifestSources) {
  if ($source -isnot [PSCustomObject]) { throw "manifest corresponding source must be an object." }
  $sourceIdentity = "$(Get-RequiredString $source 'name' 'manifest source')`n$(Get-RequiredString $source 'version' 'manifest source')"
  if ($manifestSourceByIdentity.ContainsKey($sourceIdentity)) {
    throw "Duplicate or case-colliding manifest corresponding source: $sourceIdentity"
  }
  $manifestSourceByIdentity.Add($sourceIdentity, $source)
}
$inventorySourceIdentities = [Collections.Generic.HashSet[string]]::new(
  [System.StringComparer]::OrdinalIgnoreCase
)
foreach ($source in $inventorySources) {
  $sourceIdentity = "$(Get-RequiredString $source 'name' 'inventory source')`n$(Get-RequiredString $source 'version' 'inventory source')"
  if (-not $inventorySourceIdentities.Add($sourceIdentity) -or
    -not $manifestSourceByIdentity.ContainsKey($sourceIdentity)) {
    throw "Duplicate, case-colliding, or unknown inventory corresponding source: $sourceIdentity"
  }
  $manifestSource = $manifestSourceByIdentity[$sourceIdentity]
  foreach ($field in @("license", "source_url", "sha256", "bytes")) {
    if ((Get-RequiredProperty $source $field "inventory source") -cne
      (Get-RequiredProperty $manifestSource $field "manifest source")) {
      throw "Inventory corresponding-source provenance mismatch: $sourceIdentity.$field"
    }
  }
  foreach ($field in @("selection_kind", "source_ref", "source_commit", "release_date", "notes")) {
    Assert-OptionalMatchingProperty $source $manifestSource $field "inventory source $sourceIdentity"
  }
}

$requiredSourceScripts = @(
  ".github/workflows/windows-portable-build.yml",
  "tools/windows_portable/build_portable.ps1",
  "tools/windows_portable/bundle_info.schema.json",
  "tools/windows_portable/manifest.windows-x64.json",
  "tools/windows_portable/manifest.schema.json",
  "tools/windows_portable/write_bundle_inventory.py"
)
$sourceScripts = Get-RequiredArray $inventory "source_build_install_scripts" "bundle_inventory"
if ($sourceScripts.Count -eq 0) {
  throw "Bundle inventory source/build/install script provenance must not be empty."
}
$sourceScriptPaths = [Collections.Generic.HashSet[string]]::new(
  [System.StringComparer]::OrdinalIgnoreCase
)
foreach ($sourceScript in $sourceScripts) {
  if ($sourceScript -isnot [string] -or [string]::IsNullOrWhiteSpace($sourceScript)) {
    throw "Bundle inventory source/build/install script path must be a non-empty string."
  }
  $sourceSegments = @($sourceScript.Split("/"))
  if (
    $sourceScript.Contains("\") -or
    $sourceSegments -contains "" -or
    $sourceSegments -contains "." -or
    $sourceSegments -contains ".." -or
    (
      -not $sourceScript.StartsWith(".github/workflows/", [System.StringComparison]::Ordinal) -and
      -not $sourceScript.StartsWith("tools/windows_portable/", [System.StringComparison]::Ordinal)
    )
  ) {
    throw "Unsafe bundle inventory source/build/install script path: $sourceScript"
  }
  if (-not $sourceScriptPaths.Add($sourceScript)) {
    throw "Duplicate or case-colliding source/build/install script path: $sourceScript"
  }
}
foreach ($requiredSourceScript in $requiredSourceScripts) {
  if (-not $sourceScriptPaths.Contains($requiredSourceScript)) {
    throw "Bundle inventory is missing required provenance entry: $requiredSourceScript"
  }
}

$licenseRecords = Get-RequiredArray $inventory "licenses" "bundle_inventory"
if ($licenseRecords.Count -eq 0) {
  throw "Extracted bundle inventory does not record any license files: $inventoryPath"
}
$licensesRoot = (Resolve-Path -LiteralPath (Join-Path $bundle "licenses")).Path
$inventoryLicenses = [Collections.Generic.Dictionary[string, string]]::new(
  [System.StringComparer]::OrdinalIgnoreCase
)
foreach ($licenseRecord in $licenseRecords) {
  if ($licenseRecord -isnot [PSCustomObject]) {
    throw "Extracted bundle inventory contains a malformed license record: $inventoryPath"
  }
  $pathProperty = $licenseRecord.PSObject.Properties["path"]
  $shaProperty = $licenseRecord.PSObject.Properties["sha256"]
  if ($null -eq $pathProperty -or $null -eq $shaProperty) {
    throw "Extracted bundle inventory contains a malformed license record: $inventoryPath"
  }
  $relativeLicensePath = [string]$pathProperty.Value
  $expectedLicenseSha256 = [string]$shaProperty.Value
  $licenseSegments = @($relativeLicensePath.Split("/") | Where-Object { $_ -ne "" })
  if (
    -not $relativeLicensePath.StartsWith("licenses/", [System.StringComparison]::Ordinal) -or
    $relativeLicensePath.Contains("\") -or
    $licenseSegments -contains "." -or
    $licenseSegments -contains ".."
  ) {
    throw "Unsafe inventoried license path: $relativeLicensePath"
  }
  if ($expectedLicenseSha256 -cnotmatch "^[a-f0-9]{64}$") {
    throw "Invalid inventoried license SHA-256 for ${relativeLicensePath}: $expectedLicenseSha256"
  }
  if ($inventoryLicenses.ContainsKey($relativeLicensePath)) {
    throw "Duplicate or case-colliding inventoried license path: $relativeLicensePath"
  }
  $inventoryLicenses.Add($relativeLicensePath, $expectedLicenseSha256)
  $licensePath = [System.IO.Path]::GetFullPath(
    (Join-Path $bundle ($relativeLicensePath -replace "/", "\"))
  )
  if (
    -not (Test-PathWithin -Path $licensePath -Parent $licensesRoot) -or
    -not (Test-Path -LiteralPath $licensePath -PathType Leaf)
  ) {
    throw "Inventoried license file is missing from the extracted bundle: $relativeLicensePath"
  }
  $actualLicenseSha256 = (Get-FileHash -Algorithm SHA256 -LiteralPath $licensePath).Hash.ToLowerInvariant()
  if ($actualLicenseSha256 -ne $expectedLicenseSha256) {
    throw "Inventoried license SHA-256 mismatch: $relativeLicensePath"
  }
}
$actualLicensePaths = @(
  Get-ChildItem -LiteralPath $licensesRoot -Recurse -File | ForEach-Object {
    "licenses/" + ([System.IO.Path]::GetRelativePath($licensesRoot, $_.FullName) -replace "\", "/")
  }
)
if ($actualLicensePaths.Count -ne $inventoryLicenses.Count) {
  throw "Bundle inventory must cover every extracted license file exactly once."
}
foreach ($relativeLicensePath in $actualLicensePaths) {
  if (-not $inventoryLicenses.ContainsKey($relativeLicensePath)) {
    throw "Extracted license file is absent from bundle inventory: $relativeLicensePath"
  }
}
Write-Host "WINDOWS_EXTRACTED_PROOF metadata_provenance=ok commit=$inventoryCommit version=$appVersion"
Write-Host "WINDOWS_EXTRACTED_PROOF license_inventory=ok count=$($licenseRecords.Count)"

$candidateLauncher = Join-Path $bundle "frame-compare.ps1"
Get-Command -CommandType ExternalScript $candidateLauncher | Format-List Source,Path

& $candidateLauncher --help | Out-Host
Assert-CommandSucceeded -Label "candidate_launcher_--help" -ExitCode $LASTEXITCODE

$candidateVersionOutput = [string]::Join(
  [Environment]::NewLine,
  @(& $candidateLauncher version)
)
Assert-CommandSucceeded -Label "candidate_launcher_version" -ExitCode $LASTEXITCODE
if ($candidateVersionOutput -cne "frame-compare $appVersion") {
  throw "Candidate launcher version does not match bundle inventory: expected=$appVersion actual=$candidateVersionOutput"
}
Write-Host $candidateVersionOutput

$doctorOutputDirectory = Split-Path -Parent $DoctorStdoutPath
$doctorErrorDirectory = Split-Path -Parent $DoctorStderrPath
New-Item -ItemType Directory -Path $doctorOutputDirectory -Force | Out-Null
New-Item -ItemType Directory -Path $doctorErrorDirectory -Force | Out-Null

& $candidateLauncher doctor --json 1> $DoctorStdoutPath 2> $DoctorStderrPath
$doctorExitCode = $LASTEXITCODE
foreach ($line in Get-Content -LiteralPath $DoctorStderrPath) {
  Write-Warning $line
}
Assert-CommandSucceeded -Label "candidate_launcher_doctor_--json" -ExitCode $doctorExitCode

$doctorJson = Get-Content -LiteralPath $DoctorStdoutPath -Raw
try {
  $doctorPayload = $doctorJson | ConvertFrom-Json -NoEnumerate -ErrorAction Stop
} catch {
  throw "Extracted candidate doctor stdout is not exactly one valid JSON document: $($_.Exception.Message)"
}
if ($doctorPayload -isnot [PSCustomObject] -or $doctorPayload.success -ne $true) {
  throw "Extracted candidate doctor JSON is not a successful object"
}
Write-Host $doctorJson

$installer = Join-Path $bundle "install.cmd"
& $installer
Assert-CommandSucceeded -Label "candidate_install" -ExitCode $LASTEXITCODE

$installedShim = Join-Path $env:LOCALAPPDATA "Programs/FrameCompare/bin/frame-compare.cmd"
if (!(Test-Path -LiteralPath $installedShim -PathType Leaf)) {
  throw "Installed shim not found: $installedShim"
}
$installStatePath = Join-Path $env:LOCALAPPDATA "Programs/FrameCompare/state/config.json"
try {
  $installState = Get-Content -LiteralPath $installStatePath -Raw |
    ConvertFrom-Json -ErrorAction Stop
} catch {
  throw "Installed state is missing or invalid: $installStatePath"
}
$bundlePathProperty = $installState.PSObject.Properties["bundle_path"]
if ($null -eq $bundlePathProperty -or [string]::IsNullOrWhiteSpace([string]$bundlePathProperty.Value)) {
  throw "Installed state does not record bundle_path: $installStatePath"
}
$installedBundlePath = [System.IO.Path]::GetFullPath([string]$bundlePathProperty.Value)
if (-not $installedBundlePath.Equals($bundle, [System.StringComparison]::OrdinalIgnoreCase)) {
  throw "Installed state points to the wrong bundle: expected=$bundle actual=$installedBundlePath"
}

$versionOutput = [string]::Join([Environment]::NewLine, @(& $installedShim version))
Assert-CommandSucceeded -Label "installed_shim_version" -ExitCode $LASTEXITCODE
if ($versionOutput -notmatch "^frame-compare \d+\.\d+\.\d+") {
  throw "Unexpected version output from installed shim: $versionOutput"
}
if ($versionOutput -ne $candidateVersionOutput) {
  throw "Installed shim version output does not match the candidate launcher."
}
Write-Host $versionOutput

& $installedShim --help | Out-Host
Assert-CommandSucceeded -Label "installed_shim_--help" -ExitCode $LASTEXITCODE

Write-Host "WINDOWS_EXTRACTED_PROOF result=ok"
Write-Host "WINDOWS_EXTRACTED_PROOF candidate_launcher=$candidateLauncher"
Write-Host "WINDOWS_EXTRACTED_PROOF installed_shim=$installedShim"
Write-Host "WINDOWS_EXTRACTED_PROOF doctor_stdout=$DoctorStdoutPath"
Write-Host "WINDOWS_EXTRACTED_PROOF doctor_stderr=$DoctorStderrPath"
