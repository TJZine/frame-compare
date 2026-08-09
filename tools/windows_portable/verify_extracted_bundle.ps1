Param(
  [Parameter(Mandatory = $true)]
  [string]$ZipPath,

  [Parameter(Mandatory = $true)]
  [string]$ExtractRoot,

  [Parameter(Mandatory = $true)]
  [string]$DoctorStdoutPath,

  [Parameter(Mandatory = $true)]
  [string]$DoctorStderrPath
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$currentLocation = $PWD.ProviderPath
$ZipPath = [System.IO.Path]::GetFullPath($ZipPath, $currentLocation)
$ExtractRoot = [System.IO.Path]::GetFullPath($ExtractRoot, $currentLocation)
$DoctorStdoutPath = [System.IO.Path]::GetFullPath($DoctorStdoutPath, $currentLocation)
$DoctorStderrPath = [System.IO.Path]::GetFullPath($DoctorStderrPath, $currentLocation)

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
if (Test-Path -LiteralPath $ExtractRoot) {
  throw "ExtractRoot must not already exist; choose a fresh verification directory: $ExtractRoot"
}

function Assert-CommandSucceeded([string]$Label, [int]$ExitCode) {
  Write-Host "WINDOWS_EXTRACTED_PROOF command=$Label exit_code=$ExitCode"
  if ($ExitCode -ne 0) {
    throw "$Label failed with exit code $ExitCode"
  }
}

Add-Type -AssemblyName System.IO.Compression.FileSystem
$archive = [System.IO.Compression.ZipFile]::OpenRead($ZipPath)
try {
  $entries = @($archive.Entries | ForEach-Object { $_.FullName })
} finally {
  $archive.Dispose()
}
$entryCollisions = @(
  $entries |
    Group-Object { $_.ToLowerInvariant() } |
    Where-Object { $_.Count -gt 1 }
)
if ($entryCollisions.Count -gt 0) {
  $collisionNames = @($entryCollisions | ForEach-Object { $_.Group -join ", " })
  throw "Duplicate or case-colliding ZIP entries: $($collisionNames -join '; ')"
}

foreach ($entry in $entries) {
  if (-not $entry.StartsWith("frame-compare-portable-win-x64/")) {
    throw "Non-folder-contained ZIP entry: $entry"
  }
  $pathSegments = @($entry.Split("/") | Where-Object { $_ -ne "" })
  if ($entry.Contains("\") -or $pathSegments -contains "." -or $pathSegments -contains "..") {
    throw "Unsafe ZIP entry path: $entry"
  }
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
  if ($entries -notcontains $requiredEntry) {
    throw "Missing ZIP entry: $requiredEntry"
  }
}
Write-Host "WINDOWS_EXTRACTED_PROOF zip_layout=ok zip=$ZipPath"

Expand-Archive -LiteralPath $ZipPath -DestinationPath $ExtractRoot -Force

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

$inventoryPath = Join-Path $bundle "bundle_inventory.json"
try {
  $inventory = Get-Content -LiteralPath $inventoryPath -Raw |
    ConvertFrom-Json -ErrorAction Stop
  if ($inventory -isnot [PSCustomObject]) {
    throw "bundle_inventory.json must contain one JSON object"
  }
} catch {
  throw "Extracted bundle inventory is not valid JSON: $inventoryPath"
}
$licensesProperty = $inventory.PSObject.Properties["licenses"]
if ($null -eq $licensesProperty -or @($licensesProperty.Value).Count -eq 0) {
  throw "Extracted bundle inventory does not record any license files: $inventoryPath"
}
$licensesRoot = (Resolve-Path -LiteralPath (Join-Path $bundle "licenses")).Path
foreach ($licenseRecord in @($licensesProperty.Value)) {
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
Write-Host "WINDOWS_EXTRACTED_PROOF license_inventory=ok count=$(@($licensesProperty.Value).Count)"

$candidateLauncher = Join-Path $bundle "frame-compare.ps1"
Get-Command -CommandType ExternalScript $candidateLauncher | Format-List Source,Path

& $candidateLauncher --help | Out-Host
Assert-CommandSucceeded -Label "candidate_launcher_--help" -ExitCode $LASTEXITCODE

$candidateVersionOutput = [string]::Join(
  [Environment]::NewLine,
  @(& $candidateLauncher version)
)
Assert-CommandSucceeded -Label "candidate_launcher_version" -ExitCode $LASTEXITCODE
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
