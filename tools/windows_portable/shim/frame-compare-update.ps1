$versionHelper = Join-Path $PSScriptRoot "frame-compare-version.ps1"
if (!(Test-Path -LiteralPath $versionHelper -PathType Leaf)) {
  throw "Updater version helper missing: $versionHelper. Reinstall the complete portable bundle."
}
. $versionHelper

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

function Get-RequiredStringProperty([object]$Object, [string]$Name, [string]$Context) {
  $value = Get-OptionalStringProperty -Object $Object -Name $Name
  if ([string]::IsNullOrWhiteSpace($value)) {
    throw "$Context is missing required property '$Name'"
  }
  return $value
}

function Assert-SafeRelativePath([string]$PathValue, [string]$Context) {
  if ([string]::IsNullOrWhiteSpace($PathValue)) {
    throw "$Context must not be empty"
  }
  $normalized = ($PathValue -replace "\\", "/")
  if ($normalized -match '^[A-Za-z]:') {
    throw "$Context must not contain a drive letter: $PathValue"
  }
  if ($normalized.StartsWith("/")) {
    throw "$Context must be relative: $PathValue"
  }
  if ($normalized -match '(^|/)\.\.(/|$)') {
    throw "$Context must not contain traversal: $PathValue"
  }
}

function Join-PathParts([string]$Root, [string[]]$Parts) {
  $result = $Root
  foreach ($part in $Parts) {
    $result = Join-Path $result $part
  }
  return $result
}

function Convert-RelativePathToNative([string]$RelativePath) {
  $separator = [string][System.IO.Path]::DirectorySeparatorChar
  $normalized = ($RelativePath -replace "\\", "/")
  return (($normalized -split "/") -join $separator)
}

function Get-SafeChildPath([string]$Root, [string]$RelativePath, [string]$Context) {
  Assert-SafeRelativePath -PathValue $RelativePath -Context $Context
  $candidate = Join-Path $Root (Convert-RelativePathToNative -RelativePath $RelativePath)
  $fullRoot = [System.IO.Path]::GetFullPath($Root)
  $fullCandidate = [System.IO.Path]::GetFullPath($candidate)
  $separator = [string][System.IO.Path]::DirectorySeparatorChar
  $fullRootPrefix = $fullRoot.TrimEnd([char[]]@([System.IO.Path]::DirectorySeparatorChar)) + $separator
  if (!$fullCandidate.StartsWith($fullRootPrefix, [System.StringComparison]::OrdinalIgnoreCase)) {
    throw "$Context resolved outside root: $RelativePath"
  }
  return $fullCandidate
}

Set-Variable -Name MaxUpdateArchiveBytes -Option Constant -Value ([int64](128 * 1024 * 1024))
Set-Variable -Name MaxUpdateEntryCount -Option Constant -Value 4096
Set-Variable -Name MaxManifestBytes -Option Constant -Value ([int64](4 * 1024 * 1024))
Set-Variable -Name MaxSignatureBytes -Option Constant -Value ([int64](16 * 1024))
Set-Variable -Name MaxPayloadEntryBytes -Option Constant -Value ([int64](16 * 1024 * 1024))
Set-Variable -Name MaxUpdateUncompressedBytes -Option Constant -Value ([int64](128 * 1024 * 1024))
Set-Variable -Name MaxCompressionRatio -Option Constant -Value 200.0

function Read-ZipEntryBytes(
  [System.IO.Compression.ZipArchiveEntry]$Entry,
  [int64]$MaxBytes,
  [string]$Context
) {
  if ($Entry.Length -lt 0 -or $Entry.Length -gt $MaxBytes) {
    throw "$Context exceeds the $MaxBytes-byte limit."
  }
  $stream = $Entry.Open()
  $buffer = New-Object byte[] (64 * 1024)
  $output = [System.IO.MemoryStream]::new()
  try {
    while ($true) {
      $read = $stream.Read($buffer, 0, $buffer.Length)
      if ($read -eq 0) {
        if ($output.Length -ne $Entry.Length) {
          throw "$Context length did not match its ZIP metadata."
        }
        return $output.ToArray()
      }
      if (($output.Length + $read) -gt $MaxBytes) {
        throw "$Context exceeds the $MaxBytes-byte limit while reading."
      }
      $output.Write($buffer, 0, $read)
    }
  } finally {
    $output.Dispose()
    $stream.Dispose()
  }
}

function Copy-ZipEntryToFile(
  [System.IO.Compression.ZipArchiveEntry]$Entry,
  [string]$DestinationPath,
  [int64]$ExpectedBytes
) {
  $stream = $null
  $out = $null
  $buffer = New-Object byte[] (64 * 1024)
  $written = [int64]0
  try {
    $stream = $Entry.Open()
    $out = [System.IO.File]::Open(
      $DestinationPath,
      [System.IO.FileMode]::Create,
      [System.IO.FileAccess]::Write,
      [System.IO.FileShare]::None
    )
    while ($true) {
      $read = $stream.Read($buffer, 0, $buffer.Length)
      if ($read -eq 0) {
        break
      }
      if ($written -gt ($ExpectedBytes - $read)) {
        throw "Extracted payload exceeded its signed byte count: $($Entry.FullName)"
      }
      $out.Write($buffer, 0, $read)
      $written += $read
    }
    if ($written -ne $ExpectedBytes) {
      throw "Extracted payload size did not match its signed byte count: $($Entry.FullName)"
    }
  } finally {
    if ($null -ne $out) {
      $out.Dispose()
    }
    if ($null -ne $stream) {
      $stream.Dispose()
    }
  }
}

function Assert-SafeUpdateArchive(
  [System.IO.Compression.ZipArchive]$Zip,
  [int64]$ArchiveBytes
) {
  if ($ArchiveBytes -le 0 -or $ArchiveBytes -gt $MaxUpdateArchiveBytes) {
    throw "Update archive size must be between 1 and $MaxUpdateArchiveBytes bytes."
  }
  if ($Zip.Entries.Count -le 0 -or $Zip.Entries.Count -gt $MaxUpdateEntryCount) {
    throw "Update archive entry count must be between 1 and $MaxUpdateEntryCount."
  }

  $names = New-Object System.Collections.Generic.HashSet[string] ([System.StringComparer]::OrdinalIgnoreCase)
  $totalUncompressedBytes = [int64]0
  foreach ($entry in $Zip.Entries) {
    if ([string]::IsNullOrWhiteSpace($entry.FullName)) {
      throw "Update archive contains an empty entry name."
    }
    Assert-SafeRelativePath -PathValue $entry.FullName -Context "zip entry"
    if (-not $names.Add($entry.FullName)) {
      throw "Update archive contains a duplicate entry name: $($entry.FullName)"
    }
    if ($entry.Length -lt 0 -or $entry.Length -gt $MaxPayloadEntryBytes) {
      throw "Update archive entry exceeds the $MaxPayloadEntryBytes-byte limit: $($entry.FullName)"
    }
    if ($entry.CompressedLength -lt 0) {
      throw "Update archive entry has an invalid compressed length: $($entry.FullName)"
    }
    if ($totalUncompressedBytes -gt ($MaxUpdateUncompressedBytes - $entry.Length)) {
      throw "Update archive exceeds the $MaxUpdateUncompressedBytes-byte uncompressed limit."
    }
    $totalUncompressedBytes += $entry.Length
    if ($entry.Length -gt 0) {
      if ($entry.CompressedLength -eq 0) {
        throw "Update archive entry has an invalid compression ratio: $($entry.FullName)"
      }
      $compressionRatio = [double]$entry.Length / [double]$entry.CompressedLength
      if ($compressionRatio -gt $MaxCompressionRatio) {
        throw "Update archive entry exceeds the maximum compression ratio: $($entry.FullName)"
      }
    }
  }
}

function Ensure-Directory([string]$Path) {
  if (!(Test-Path -LiteralPath $Path)) {
    New-Item -ItemType Directory -Path $Path | Out-Null
  }
}

function Get-Sha256HexForFile([string]$Path) {
  return (Get-FileHash -LiteralPath $Path -Algorithm SHA256).Hash.ToLowerInvariant()
}

function Get-Sha256HexForBytes([byte[]]$Bytes) {
  $sha = [System.Security.Cryptography.SHA256]::Create()
  try {
    $hash = $sha.ComputeHash($Bytes)
  } finally {
    $sha.Dispose()
  }
  return ([System.BitConverter]::ToString($hash).Replace("-", "").ToLowerInvariant())
}

function Get-RsaParameterBytes([xml]$KeyXml, [string]$Name, [bool]$Required) {
  $node = $KeyXml.DocumentElement.SelectSingleNode($Name)
  if ($null -eq $node -or [string]::IsNullOrWhiteSpace($node.InnerText)) {
    if ($Required) {
      throw "RSA key XML is missing required '$Name' value."
    }
    return $null
  }
  return [System.Convert]::FromBase64String($node.InnerText)
}

function New-RsaFromXml([string]$KeyXmlText) {
  $rsa = $null
  try {
    [xml]$keyXml = $KeyXmlText
    if ($null -eq $keyXml.RSAKeyValue) {
      throw "RSA key XML must have an RSAKeyValue root."
    }
    $parameters = New-Object System.Security.Cryptography.RSAParameters
    $parameters.Modulus = Get-RsaParameterBytes -KeyXml $keyXml -Name "Modulus" -Required $true
    $parameters.Exponent = Get-RsaParameterBytes -KeyXml $keyXml -Name "Exponent" -Required $true
    $parameters.P = Get-RsaParameterBytes -KeyXml $keyXml -Name "P" -Required $false
    $parameters.Q = Get-RsaParameterBytes -KeyXml $keyXml -Name "Q" -Required $false
    $parameters.DP = Get-RsaParameterBytes -KeyXml $keyXml -Name "DP" -Required $false
    $parameters.DQ = Get-RsaParameterBytes -KeyXml $keyXml -Name "DQ" -Required $false
    $parameters.InverseQ = Get-RsaParameterBytes -KeyXml $keyXml -Name "InverseQ" -Required $false
    $parameters.D = Get-RsaParameterBytes -KeyXml $keyXml -Name "D" -Required $false

    $rsa = [System.Security.Cryptography.RSA]::Create()
    $rsa.ImportParameters($parameters)
    return $rsa
  } catch {
    if ($null -ne $rsa) {
      $rsa.Dispose()
    }
    $rsa = New-Object System.Security.Cryptography.RSACryptoServiceProvider
    $rsa.PersistKeyInCsp = $false
    try {
      $rsa.FromXmlString(([xml]$KeyXmlText).DocumentElement.OuterXml)
      return $rsa
    } catch {
      $rsa.Clear()
      $rsa.Dispose()
      throw
    }
  }
}

function Test-ManifestSignature(
  [System.Security.Cryptography.RSA]$Rsa,
  [byte[]]$ManifestBytes,
  [byte[]]$SignatureBytes
) {
  try {
    return $Rsa.VerifyData(
      $ManifestBytes,
      $SignatureBytes,
      [System.Security.Cryptography.HashAlgorithmName]::SHA256,
      [System.Security.Cryptography.RSASignaturePadding]::Pkcs1
    )
  } catch [System.Management.Automation.MethodException] {
    return $Rsa.VerifyData($ManifestBytes, "SHA256", $SignatureBytes)
  } catch [System.MissingMethodException] {
    return $Rsa.VerifyData($ManifestBytes, "SHA256", $SignatureBytes)
  }
}

function Get-InstallConfig() {
  $shimDir = $PSScriptRoot
  if ([string]::IsNullOrWhiteSpace($shimDir)) {
    $shimDir = Split-Path -Parent $PSCommandPath
  }
  $installRoot = Split-Path -Parent $shimDir
  $stateDir = Join-Path $installRoot "state"
  $configPath = Join-Path $stateDir "config.json"

  if (!(Test-Path -LiteralPath $configPath)) {
    throw "Config not found: $configPath`nRun install.cmd from the portable bundle."
  }

  try {
    $config = Get-Content -LiteralPath $configPath -Raw -Encoding UTF8 | ConvertFrom-Json
  } catch {
    throw "Invalid config file: $configPath`nRun install.cmd from the portable bundle."
  }

  $schemaVersionRaw = Get-OptionalStringProperty -Object $config -Name "schema_version"
  $schemaVersion = 0
  if (-not [int]::TryParse($schemaVersionRaw, [ref]$schemaVersion)) {
    throw "Unsupported config schema version '$schemaVersionRaw' in $configPath"
  }
  if ($schemaVersion -ne 1) {
    throw "Unsupported config schema version '$schemaVersion' in $configPath"
  }
  $installType = Get-RequiredStringProperty -Object $config -Name "install_type" -Context "config"
  if ($installType -ne "portable_bundle") {
    throw "Unsupported install_type '$installType' in $configPath"
  }
  $bundlePath = Get-RequiredStringProperty -Object $config -Name "bundle_path" -Context "config"
  if (!(Test-Path -LiteralPath $bundlePath)) {
    throw "Portable bundle directory not found: $bundlePath`nRun install.cmd from the bundle's current location."
  }
  return [ordered]@{
    install_root = $installRoot
    state_dir = $stateDir
    config_path = $configPath
    bundle_path = $bundlePath
  }
}

function Invoke-WithRetry([scriptblock]$Action, [string]$Label) {
  $maxAttempts = 10
  for ($attempt = 1; $attempt -le $maxAttempts; $attempt++) {
    try {
      & $Action
      return
    } catch {
      if ($attempt -eq $maxAttempts) {
        throw "$Label failed after $maxAttempts attempts. Close any running frame-compare terminals, then retry. Details: $($_.Exception.Message)"
      }
      $sleepMs = [int][Math]::Min(2000, 200 * [Math]::Pow(2, $attempt - 1))
      Start-Sleep -Milliseconds $sleepMs
    }
  }
}

function Acquire-UpdateLock([string]$BundlePath) {
  $lockPath = Join-PathParts -Root $BundlePath -Parts @("app", ".update_lock")
  Ensure-Directory -Path (Split-Path -Parent $lockPath)
  # Ownership belongs to the exclusive handle, not the file's age or existence.
  # A terminated updater releases its handle so the next command can repair its
  # journal immediately. Keep the file: unlinking it after close can race a new
  # owner and let different handles lock different files at the same path.
  try {
    $stream = [System.IO.File]::Open($lockPath, [System.IO.FileMode]::OpenOrCreate, [System.IO.FileAccess]::ReadWrite, [System.IO.FileShare]::None)
    return [ordered]@{
      lock_path = $lockPath
      stream = $stream
    }
  } catch {
    throw "Another update appears to be running or its lock is inaccessible: $lockPath. $($_.Exception.Message)"
  }
}

function Release-UpdateLock([object]$LockInfo) {
  if ($null -eq $LockInfo) {
    return
  }
  $stream = $LockInfo["stream"]
  if ($null -ne $stream) {
    $stream.Dispose()
  }
}

function Get-InstalledBundleCompatibilityContract([string]$BundlePath) {
  $bundleInfoPath = Join-Path $BundlePath "bundle_info.json"
  if (!(Test-Path -LiteralPath $bundleInfoPath -PathType Leaf)) {
    throw "Installed media runtime identity is unavailable. Install the complete portable bundle before using code-only updates."
  }

  try {
    $bundleInfo = Get-Content -LiteralPath $bundleInfoPath -Raw | ConvertFrom-Json
  } catch {
    throw "Installed bundle_info.json is invalid. Reinstall the complete portable bundle before using code-only updates."
  }

  $schemaVersionRaw = Get-OptionalStringProperty -Object $bundleInfo -Name "schema_version"
  $schemaVersion = 0
  if (-not [int]::TryParse($schemaVersionRaw, [ref]$schemaVersion) -or $schemaVersion -ne 3) {
    throw "Installed bundle lacks the native VSView alignment-panel capability (bundle_info schema_version 3 required). A complete portable reinstall is required; code-only update refused."
  }

  $bundleKind = Get-RequiredStringProperty -Object $bundleInfo -Name "bundle_kind" -Context "bundle_info"
  $platform = Get-RequiredStringProperty -Object $bundleInfo -Name "platform" -Context "bundle_info"
  if ($bundleKind -ne "full" -or $platform -ne "windows-x64") {
    throw "Installed bundle identity is not a supported full windows-x64 bundle. A complete portable reinstall is required."
  }

  $requirementsFingerprint = Get-RequiredStringProperty -Object $bundleInfo -Name "requirements_lock_sha256" -Context "bundle_info"
  $runtimeFingerprint = Get-RequiredStringProperty -Object $bundleInfo -Name "media_runtime_fingerprint" -Context "bundle_info"
  if ($requirementsFingerprint -cnotmatch '^[a-f0-9]{64}$') {
    throw "Installed requirements fingerprint is invalid in bundle_info.json."
  }
  if ($runtimeFingerprint -cnotmatch '^[a-f0-9]{64}$') {
    throw "Installed media-runtime fingerprint is invalid. A complete portable reinstall is required."
  }

  return [ordered]@{
    requirements_lock_sha256 = $requirementsFingerprint.ToLowerInvariant()
    media_runtime_fingerprint = $runtimeFingerprint.ToLowerInvariant()
  }
}

function Get-BackupRoot([string]$BundlePath) {
  return Join-PathParts -Root $BundlePath -Parts @("app", ".update_backups")
}

function Get-BackupCompatibilityError([string]$BackupParent, [object]$InstalledCompatibility) {
  $identityPath = Join-Path $BackupParent "compatibility.json"
  if (!(Test-Path -LiteralPath $identityPath -PathType Leaf)) {
    return "backup runtime/requirements identity is missing (legacy backups cannot be restored)"
  }
  try {
    $identity = Get-Content -LiteralPath $identityPath -Raw -Encoding UTF8 | ConvertFrom-Json
    $requirements = Get-RequiredStringProperty -Object $identity -Name "requirements_lock_sha256" -Context "backup identity"
    $runtime = Get-RequiredStringProperty -Object $identity -Name "media_runtime_fingerprint" -Context "backup identity"
    if ($requirements -cnotmatch '^[a-f0-9]{64}$' -or $runtime -cnotmatch '^[a-f0-9]{64}$') {
      return "backup runtime/requirements identity is invalid"
    }
  } catch {
    return "backup runtime/requirements identity is invalid"
  }
  if (
    $requirements -cne [string]$InstalledCompatibility["requirements_lock_sha256"] -or
    $runtime -cne [string]$InstalledCompatibility["media_runtime_fingerprint"]
  ) {
    return "backup runtime/requirements identity differs from the current bundle"
  }
  return ""
}

function Get-PayloadVersionFromManifest([object]$Manifest) {
  return Get-RequiredStringProperty -Object $Manifest -Name "to_app_version" -Context "manifest"
}

function Invoke-SmokeCheck([string]$BundlePath, [string]$ExpectedVersion) {
  $launcher = Join-Path $BundlePath "frame-compare.ps1"
  if (!(Test-Path -LiteralPath $launcher -PathType Leaf)) { throw "Bundle launcher not found: $launcher" }
  $output = & $launcher version 2>&1
  if ($LASTEXITCODE -ne 0) { throw "Smoke check failed: frame-compare version exited with code $LASTEXITCODE" }
  $reported = Get-VersionFromCommandOutput -OutputLines $output
  if ($reported -eq "") { $reported = Get-PythonAppVersion $BundlePath }
  if ([string]::IsNullOrEmpty($reported) -or
      (Compare-FrameCompareVersion $reported $ExpectedVersion) -ne 0) {
    throw "Smoke check failed: expected version '$ExpectedVersion', got '$reported'"
  }
}

function Invoke-PurgeBackups([string]$BundlePath, [int]$Keep = 5) {
  if ($Keep -lt 0) {
    throw "--keep must be >= 0"
  }
  $backupRoot = Get-BackupRoot -BundlePath $BundlePath
  if (!(Test-Path -LiteralPath $backupRoot)) {
    Write-Host "No backups to purge."
    return 0
  }
  $dirs = @(Get-ChildItem -LiteralPath $backupRoot -Directory | Sort-Object Name -Descending)
  $installedCompatibility = Get-InstalledBundleCompatibilityContract $BundlePath
  $complete = @($dirs | Where-Object {
    (Get-BackupCompatibilityError $_.FullName $installedCompatibility) -eq "" -and
    (Get-BackupCompletenessError $_.FullName) -eq ""
  })
  $retained = @($complete | Select-Object -First $Keep | ForEach-Object { $_.FullName })
  $removed = 0
  foreach ($dir in $dirs) {
    if ($dir.FullName -notin $retained) { Remove-Item -LiteralPath $dir.FullName -Recurse -Force; $removed++ }
  }
  Write-Host "Purged $removed backup(s); kept $($retained.Count) complete backups."
  return 0
}

function Invoke-ListBackups([string]$BundlePath) {
  $backupRoot = Get-BackupRoot -BundlePath $BundlePath
  if (!(Test-Path -LiteralPath $backupRoot)) {
    Write-Host "No backups found."
    return 0
  }
  $dirs = @(Get-ChildItem -LiteralPath $backupRoot -Directory | Sort-Object Name -Descending)
  if ($dirs.Count -eq 0) {
    Write-Host "No backups found."
    return 0
  }
  $installedCompatibility = Get-InstalledBundleCompatibilityContract -BundlePath $BundlePath
  foreach ($dir in $dirs) {
    $compatibilityError = Get-BackupCompatibilityError -BackupParent $dir.FullName -InstalledCompatibility $installedCompatibility
    if ($compatibilityError -eq "") { $compatibilityError = Get-BackupCompletenessError $dir.FullName }
    if ([string]::IsNullOrWhiteSpace($compatibilityError)) {
      Write-Host $dir.Name
    } else {
      Write-Host "$($dir.Name) (unavailable: $compatibilityError)"
    }
  }
  return 0
}

function Verify-ManifestSignature(
  [byte[]]$ManifestBytes,
  [byte[]]$SignatureFileBytes,
  [string]$PublicKeyPath
) {
  if (!(Test-Path -LiteralPath $PublicKeyPath)) {
    return $false
  }
  $signatureText = ([System.Text.Encoding]::UTF8.GetString($SignatureFileBytes)).Trim()
  if ([string]::IsNullOrWhiteSpace($signatureText)) {
    return $false
  }
  try {
    $signatureBytes = [Convert]::FromBase64String($signatureText)
  } catch {
    return $false
  }
  $rsa = $null
  try {
    $keyXml = Get-Content -LiteralPath $PublicKeyPath -Raw
    $rsa = New-RsaFromXml -KeyXmlText $keyXml
    return Test-ManifestSignature -Rsa $rsa -ManifestBytes $ManifestBytes -SignatureBytes $signatureBytes
  } catch {
    return $false
  } finally {
    if ($null -ne $rsa) {
      try { $rsa.Clear() } catch { }
      try { $rsa.Dispose() } catch { }
    }
  }
}

function Get-VersionFromCommandOutput([object[]]$OutputLines) {
  foreach ($line in $OutputLines) {
    $text = [string]$line
    if ([string]::IsNullOrWhiteSpace($text)) {
      continue
    }
    $candidate = $text.Trim() -creplace '^frame-compare[ \t]+', ''
    if ($null -ne (ConvertTo-FrameCompareVersion $candidate)) { return $candidate }
  }
  return ""
}

function Get-BundleAppVersion([string]$BundlePath) {
  $bundleLauncher = Join-Path $BundlePath "frame-compare.ps1"
  if (Test-Path -LiteralPath $bundleLauncher) {
    $launcherResult = & $bundleLauncher version 2>&1
    if ($LASTEXITCODE -eq 0) {
      $launcherVersion = Get-VersionFromCommandOutput -OutputLines $launcherResult
      if (-not [string]::IsNullOrWhiteSpace($launcherVersion)) {
        return $launcherVersion
      }
    }
  }

  return Get-PythonAppVersion $BundlePath
}

function Get-PythonAppVersion([string]$BundlePath) {
  $pythonExe = Join-PathParts -Root $BundlePath -Parts @("python", "python.exe")
  if (!(Test-Path -LiteralPath $pythonExe)) {
    return ""
  }
  $result = & $pythonExe -c "import frame_compare; print(frame_compare.__version__)" 2>&1
  if ($LASTEXITCODE -ne 0) {
    return ""
  }
  return (Get-VersionFromCommandOutput -OutputLines $result)
}

function Copy-DirectoryContents([string]$SourceDir, [string]$DestinationDir) {
  Ensure-Directory -Path $DestinationDir
  foreach ($item in (Get-ChildItem -LiteralPath $SourceDir -Force)) {
    Copy-Item -LiteralPath $item.FullName -Destination $DestinationDir -Force -Recurse
  }
}

function Get-TreeInventory([string]$Root) {
  if (!(Test-Path -LiteralPath $Root -PathType Container)) { throw "Source tree missing: $Root" }
  $rootItem = Get-Item -LiteralPath $Root -Force
  if (($rootItem.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0) { throw "Reparse source tree refused: $Root" }
  $prefix = [IO.Path]::GetFullPath($Root).TrimEnd([IO.Path]::DirectorySeparatorChar, [IO.Path]::AltDirectorySeparatorChar) + [IO.Path]::DirectorySeparatorChar
  $items = @(Get-ChildItem -LiteralPath $Root -Recurse -Force -ErrorAction Stop | Sort-Object FullName)
  foreach ($item in $items) {
    if (($item.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0) { throw "Reparse source entry refused: $($item.FullName)" }
    if (!$item.PSIsContainer) {
      [pscustomobject]@{
        path = $item.FullName.Substring($prefix.Length).Replace('\', '/')
        sha256 = Get-Sha256HexForFile $item.FullName
        bytes = [int64]$item.Length
      }
    }
  }
}

function Assert-TreeInventory([string]$Root, [object[]]$ExpectedInventory) {
  if ($ExpectedInventory.Count -eq 0) { throw "Empty source inventory: $Root" }
  $expected = New-Object 'Collections.Generic.Dictionary[string,object]' ([StringComparer]::Ordinal)
  $caseNames = New-Object 'Collections.Generic.HashSet[string]' ([StringComparer]::OrdinalIgnoreCase)
  foreach ($entry in $ExpectedInventory) {
    $path = Get-RequiredStringProperty $entry "path" "source inventory"
    Assert-SafeRelativePath $path "source inventory"
    if ($path.Contains('\') -or !$caseNames.Add($path)) { throw "Duplicate or noncanonical inventory path: $path" }
    $hash = Get-RequiredStringProperty $entry "sha256" "source inventory"
    $bytes = [int64]0
    if ($hash -cnotmatch '^[a-f0-9]{64}$' -or
        ![int64]::TryParse((Get-RequiredStringProperty $entry "bytes" "source inventory"), [ref]$bytes) -or $bytes -lt 0) {
      throw "Invalid inventory hash/size: $path"
    }
    $expected.Add($path, $entry)
  }
  $actual = @(Get-TreeInventory $Root)
  if ($actual.Count -ne $expected.Count) { throw "Source inventory path-set mismatch: $Root" }
  foreach ($file in $actual) {
    if (!$expected.ContainsKey($file.path)) { throw "Unexpected source inventory path: $($file.path)" }
    $entry = $expected[$file.path]
    if ($file.sha256 -cne $entry.sha256 -or $file.bytes -ne [int64]$entry.bytes) {
      throw "Source inventory hash/size mismatch: $($file.path)"
    }
  }
}

function Write-AtomicJson([string]$Path, [object]$Value) {
  $temporary = $Path + ".tmp"
  [IO.File]::WriteAllText($temporary, (($Value | ConvertTo-Json -Depth 8) + "`n"), [Text.UTF8Encoding]::new($false))
  # Ordinary PowerShell null becomes an empty backup path in this .NET call.
  if ([IO.File]::Exists($Path)) { [IO.File]::Replace($temporary, $Path, [NullString]::Value) }
  else { [IO.File]::Move($temporary, $Path) }
}

function Read-CompleteBackup([string]$BackupParent) {
  $recordPath = Join-Path $BackupParent "backup.json"
  if (!(Test-Path -LiteralPath $recordPath -PathType Leaf)) { throw "backup completeness record missing: $recordPath" }
  $recordText = Get-Content -LiteralPath $recordPath -Raw -Encoding UTF8 -ErrorAction Stop
  if (!$recordText.TrimStart().StartsWith("{")) { throw "Invalid backup completeness record: $recordPath" }
  $record = $recordText | ConvertFrom-Json
  if (($record.schema_version -isnot [int] -and $record.schema_version -isnot [long]) -or
      $record.schema_version -ne 1 -or $null -eq (ConvertTo-FrameCompareVersion $record.app_version)) {
    throw "Invalid backup completeness record: $recordPath"
  }
  $files = @($record.files)
  Assert-TreeInventory -Root (Join-Path $BackupParent "frame_compare") -ExpectedInventory $files
  return $record
}

function Get-BackupCompletenessError([string]$BackupParent) {
  try { $null = Read-CompleteBackup $BackupParent; return "" }
  catch { return "backup completeness unavailable: $($_.Exception.Message)" }
}

function New-CompleteBackup([string]$BundlePath, [string]$TargetDir, [object]$Compatibility, [string]$Version, [string]$BackupId) {
  if ($null -eq (ConvertTo-FrameCompareVersion $Version)) { throw "Malformed backup app version '$Version'" }
  $inventory = @(Get-TreeInventory $TargetDir)
  $backupRoot = Get-BackupRoot $BundlePath
  Ensure-Directory $backupRoot
  $parent = Get-SafeChildPath $backupRoot $BackupId "backup id"
  if (Test-Path -LiteralPath $parent) { throw "Backup id already exists; refusing to merge: $parent" }
  $created = $false
  try {
    New-Item -ItemType Directory -Path $parent -ErrorAction Stop | Out-Null
    $created = $true
    $copy = Join-Path $parent "frame_compare"
    Copy-Item -LiteralPath $TargetDir -Destination $copy -Recurse -Force -ErrorAction Stop
    Assert-TreeInventory -Root $copy -ExpectedInventory $inventory
    Write-AtomicJson -Path (Join-Path $parent "compatibility.json") -Value $Compatibility
    # Last write is the completeness marker; neither record lives inside the copy.
    Write-AtomicJson -Path (Join-Path $parent "backup.json") -Value ([ordered]@{
      schema_version = 1; app_version = $Version; files = $inventory
    })
    return $parent
  } catch {
    if ($created) { Remove-Item -LiteralPath $parent -Recurse -Force -ErrorAction Stop }
    throw
  }
}

function Get-ReplacementPaths([string]$BundlePath) {
  $target = Join-PathParts $BundlePath @("app", "src", "frame_compare")
  return @{ Target = $target; New = "$target.new"; Old = "$target.old";
    Journal = (Join-PathParts $BundlePath @("app", ".frame_compare_replacement.json")) }
}

function Repair-InterruptedReplacement([string]$BundlePath) {
  $paths = Get-ReplacementPaths $BundlePath
  $temporary = $paths.Journal + ".tmp"
  try {
    foreach ($path in @($paths.Target, $paths.New, $paths.Old)) {
      if (Test-Path -LiteralPath $path) {
        $item = Get-Item -LiteralPath $path -Force
        if (!$item.PSIsContainer -or ($item.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0) { throw "Unsafe transaction tree: $path" }
      }
    }
    if (Test-Path -LiteralPath $paths.Journal) {
      $journalItem = Get-Item -LiteralPath $paths.Journal -Force
      if ($journalItem.PSIsContainer -or ($journalItem.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0) { throw "Unsafe replacement journal: $($paths.Journal)" }
    }
    if (!(Test-Path -LiteralPath $paths.Journal -PathType Leaf)) {
      if ((Test-Path -LiteralPath $paths.New) -or (Test-Path -LiteralPath $paths.Old)) {
        throw "Unknown replacement state: .old/.new exists without a journal."
      }
    } else {
      $journalText = Get-Content -LiteralPath $paths.Journal -Raw -Encoding UTF8
      if (!$journalText.TrimStart().StartsWith("{")) { throw "Invalid replacement journal." }
      $journal = $journalText | ConvertFrom-Json
      if (($journal.schema_version -isnot [int] -and $journal.schema_version -isnot [long]) -or
          $journal.schema_version -ne 1 -or $journal.operation -cnotin @("apply", "rollback") -or
          $journal.state -cnotin @("staging", "promoting", "committed") -or
          [string]::IsNullOrWhiteSpace([string]$journal.started_at)) { throw "Invalid replacement journal." }
      $started = [DateTime]::MinValue
      if ($journal.started_at -isnot [DateTime] -and
          ![DateTime]::TryParse([string]$journal.started_at, [Globalization.CultureInfo]::InvariantCulture, [Globalization.DateTimeStyles]::RoundtripKind, [ref]$started)) {
        throw "Invalid replacement journal timestamp."
      }
      $targetExists = Test-Path -LiteralPath $paths.Target
      $oldExists = Test-Path -LiteralPath $paths.Old
      if ($journal.state -ceq "staging") {
        if (!$targetExists -or $oldExists) { throw "Staging journal does not describe an untouched target." }
      } elseif ($journal.state -ceq "promoting") {
        if ($oldExists) {
          if ($targetExists) {
            $failed = $paths.Target + ".failed-" + [DateTime]::UtcNow.ToString("yyyyMMddHHmmssfffffff") + "-" + [guid]::NewGuid().ToString("N")
            Invoke-WithRetry -Label "Retain uncommitted target" -Action { Move-Item -LiteralPath $paths.Target -Destination $failed -ErrorAction Stop }
          }
          Invoke-WithRetry -Label "Restore previous source tree" -Action { Move-Item -LiteralPath $paths.Old -Destination $paths.Target -ErrorAction Stop }
        } elseif (!$targetExists) { throw "Promoting journal has neither target nor .old." }
      } else {
        if (!$targetExists -or (Test-Path -LiteralPath $paths.New)) { throw "Committed journal has missing target or unexpected .new." }
        if ($oldExists) { Invoke-WithRetry -Label "Remove committed previous tree" -Action { Remove-Item -LiteralPath $paths.Old -Recurse -Force -ErrorAction Stop } }
      }
      if (Test-Path -LiteralPath $paths.New) { Remove-Item -LiteralPath $paths.New -Recurse -Force -ErrorAction Stop }
      Remove-Item -LiteralPath $paths.Journal -Force -ErrorAction Stop
    }
    # An interrupted atomic write is never authoritative and cannot block retry.
    if (Test-Path -LiteralPath $temporary) { Remove-Item -LiteralPath $temporary -Force -ErrorAction Stop }
  } catch {
    throw "Replacement recovery refused/failed: $($_.Exception.Message). Retained paths: target=$($paths.Target); old=$($paths.Old); new=$($paths.New); journal=$($paths.Journal); failed=$($paths.Target).failed-*. Restore the previous .old by rename after moving any target aside; retain the journal until the trees are reconciled."
  }
}

function Invoke-SourceTreeReplacement([string]$BundlePath, [string]$TargetDir, [string]$CandidateDir, [object[]]$ExpectedInventory, [string]$ExpectedVersion, [string]$Operation) {
  if ($null -eq (ConvertTo-FrameCompareVersion $ExpectedVersion)) { throw "Malformed target app version '$ExpectedVersion'" }
  if ($Operation -cnotin @("apply", "rollback")) { throw "Invalid replacement operation: $Operation" }
  $paths = Get-ReplacementPaths $BundlePath
  if ($TargetDir -cne $paths.Target -or !(Test-Path -LiteralPath $TargetDir -PathType Container)) { throw "Invalid replacement target: $TargetDir" }
  if ((Test-Path -LiteralPath $paths.Old) -or (Test-Path -LiteralPath $paths.New) -or (Test-Path -LiteralPath $paths.Journal)) { throw "Replacement requires repaired transaction paths." }
  $journal = [ordered]@{ schema_version = 1; operation = $Operation; state = "staging"; started_at = [DateTime]::UtcNow.ToString("o") }
  $committed = $false
  try {
    Write-AtomicJson $paths.Journal $journal
    Copy-DirectoryContents -SourceDir $CandidateDir -DestinationDir $paths.New
    Assert-TreeInventory -Root $paths.New -ExpectedInventory $ExpectedInventory
    $journal.state = "promoting"
    Write-AtomicJson $paths.Journal $journal
    Invoke-WithRetry -Label "Rename current frame_compare to .old" -Action { Move-Item -LiteralPath $TargetDir -Destination $paths.Old -ErrorAction Stop }
    Invoke-WithRetry -Label "Rename .new into place" -Action { Move-Item -LiteralPath $paths.New -Destination $TargetDir -ErrorAction Stop }
    Invoke-SmokeCheck -BundlePath $BundlePath -ExpectedVersion $ExpectedVersion
    $journal.state = "committed"
    Write-AtomicJson $paths.Journal $journal
    $committed = $true
    Repair-InterruptedReplacement $BundlePath
    $failed = @(Get-ChildItem -LiteralPath (Split-Path -Parent $TargetDir) -Directory -Filter "frame_compare.failed-*" | Sort-Object Name -Descending)
    $failed | Select-Object -Skip 1 | Remove-Item -Recurse -Force -ErrorAction Stop
  } catch {
    $failure = $_
    if (!$committed) {
      try { Repair-InterruptedReplacement $BundlePath }
      catch { throw "Replacement failed: $($failure.Exception.Message). $($_.Exception.Message)" }
    }
    throw $failure
  }
}

function Invoke-Rollback([string]$BundlePath, [string]$BackupId) {
  $backupRoot = Get-BackupRoot -BundlePath $BundlePath
  if ($BackupId -notmatch '^\d{14}$') {
    throw "Invalid backup id format: $BackupId (expected yyyyMMddHHmmss)"
  }
  $backupParent = Get-SafeChildPath -Root $backupRoot -RelativePath $BackupId -Context "backup id"
  $backupDir = Join-Path $backupParent "frame_compare"
  if (!(Test-Path -LiteralPath $backupDir -PathType Container)) {
    throw "Backup id not found: $BackupId"
  }
  $installedCompatibility = Get-InstalledBundleCompatibilityContract -BundlePath $BundlePath
  $compatibilityError = Get-BackupCompatibilityError -BackupParent $backupParent -InstalledCompatibility $installedCompatibility
  if (![string]::IsNullOrWhiteSpace($compatibilityError)) {
    throw "Rollback refused: $compatibilityError."
  }
  $completenessError = Get-BackupCompletenessError $backupParent
  if ($completenessError -ne "") { throw "Rollback refused: $completenessError" }

  $lockInfo = $null
  try {
    $lockInfo = Acquire-UpdateLock -BundlePath $BundlePath
    Repair-InterruptedReplacement -BundlePath $BundlePath
    # Another update may have pruned this backup after the unlocked preflight.
    if (!(Test-Path -LiteralPath $backupDir -PathType Container)) {
      throw "Backup id not found: $BackupId"
    }
    $installedCompatibility = Get-InstalledBundleCompatibilityContract -BundlePath $BundlePath
    $compatibilityError = Get-BackupCompatibilityError -BackupParent $backupParent -InstalledCompatibility $installedCompatibility
    if (![string]::IsNullOrWhiteSpace($compatibilityError)) {
      throw "Rollback refused: $compatibilityError."
    }

    $targetDir = Join-PathParts -Root $BundlePath -Parts @("app", "src", "frame_compare")
    $record = Read-CompleteBackup $backupParent
    Invoke-SourceTreeReplacement -BundlePath $BundlePath -TargetDir $targetDir -CandidateDir $backupDir -ExpectedInventory @($record.files) -ExpectedVersion $record.app_version -Operation "rollback"
    Write-Host "Rollback applied from backup: $BackupId"
    return 0
  } finally {
    Release-UpdateLock -LockInfo $lockInfo
  }
}

function Invoke-ApplyUpdate([string]$BundlePath, [string]$UpdateZipPath) {
  Add-Type -AssemblyName System.IO.Compression
  Add-Type -AssemblyName System.IO.Compression.FileSystem

  $resolvedZip = (Resolve-Path -LiteralPath $UpdateZipPath).Path
  $lockInfo = $null
  $zipStream = $null
  $zip = $null
  $tempRoot = Join-PathParts -Root ([System.IO.Path]::GetTempPath()) -Parts @(
    "FrameCompareUpdate",
    [guid]::NewGuid().ToString("N")
  )
  $targetDir = Join-PathParts -Root $BundlePath -Parts @("app", "src", "frame_compare")

  try {
    $lockInfo = Acquire-UpdateLock -BundlePath $BundlePath
    Repair-InterruptedReplacement -BundlePath $BundlePath

    $zipStream = [System.IO.File]::Open(
      $resolvedZip,
      [System.IO.FileMode]::Open,
      [System.IO.FileAccess]::Read,
      [System.IO.FileShare]::Read
    )
    $archiveBytes = $zipStream.Length
    if ($archiveBytes -le 0 -or $archiveBytes -gt $MaxUpdateArchiveBytes) {
      throw "Update archive size must be between 1 and $MaxUpdateArchiveBytes bytes."
    }

    $zip = [System.IO.Compression.ZipArchive]::new(
      $zipStream,
      [System.IO.Compression.ZipArchiveMode]::Read,
      $true
    )
    if ($zip.Entries.Count -le 0 -or $zip.Entries.Count -gt $MaxUpdateEntryCount) {
      throw "Update archive entry count must be between 1 and $MaxUpdateEntryCount."
    }

    $manifestEntry = $null
    $signatureEntry = $null
    foreach ($entry in $zip.Entries) {
      if ($entry.FullName.Equals("update-manifest.json", [System.StringComparison]::OrdinalIgnoreCase)) {
        if ($null -ne $manifestEntry) {
          throw "Update archive contains duplicate update-manifest.json entries."
        }
        $manifestEntry = $entry
      }
      if ($entry.FullName.Equals("update-manifest.sig", [System.StringComparison]::OrdinalIgnoreCase)) {
        if ($null -ne $signatureEntry) {
          throw "Update archive contains duplicate update-manifest.sig entries."
        }
        $signatureEntry = $entry
      }
    }
    if ($null -eq $manifestEntry -or $manifestEntry.FullName -cne "update-manifest.json") {
      throw "Canonical update-manifest.json not found in update zip."
    }
    if ($null -eq $signatureEntry -or $signatureEntry.FullName -cne "update-manifest.sig") {
      throw "Canonical update-manifest.sig not found in update zip."
    }

    $manifestBytes = Read-ZipEntryBytes -Entry $manifestEntry -MaxBytes $MaxManifestBytes -Context "update-manifest.json"
    $signatureFileBytes = Read-ZipEntryBytes -Entry $signatureEntry -MaxBytes $MaxSignatureBytes -Context "update-manifest.sig"
    $publicKeyPath = Join-Path $PSScriptRoot "update_public_key.xml"
    if (-not (Verify-ManifestSignature -ManifestBytes $manifestBytes -SignatureFileBytes $signatureFileBytes -PublicKeyPath $publicKeyPath)) {
      throw "Signature missing or invalid; refusing to apply update."
    }

    Assert-SafeUpdateArchive -Zip $zip -ArchiveBytes $archiveBytes
    $entries = @($zip.Entries)
    $manifestText = [System.Text.Encoding]::UTF8.GetString($manifestBytes)
    $manifest = $manifestText | ConvertFrom-Json

    $schemaVersion = [int](Get-RequiredStringProperty -Object $manifest -Name "schema_version" -Context "manifest")
    if ($schemaVersion -ne 2) {
      throw "Unsupported manifest schema_version '$schemaVersion'"
    }
    $platform = Get-RequiredStringProperty -Object $manifest -Name "target_platform" -Context "manifest"
    if ($platform -ne "windows-x64") {
      throw "Unsupported update target_platform '$platform'"
    }
    $signatureAlgorithm = Get-RequiredStringProperty -Object $manifest -Name "signature_algorithm" -Context "manifest"
    if ($signatureAlgorithm -cne "rsa-sha256-pkcs1") {
      throw "Unsupported signature_algorithm '$signatureAlgorithm'"
    }

    $expectedRuntimeFingerprint = Get-RequiredStringProperty -Object $manifest -Name "expected_media_runtime_fingerprint" -Context "manifest"
    if ($expectedRuntimeFingerprint -cnotmatch '^[a-f0-9]{64}$') {
      throw "Manifest expected_media_runtime_fingerprint is invalid."
    }
    $installedCompatibility = Get-InstalledBundleCompatibilityContract -BundlePath $BundlePath
    $installedRuntimeFingerprint = [string]$installedCompatibility["media_runtime_fingerprint"]
    if ($installedRuntimeFingerprint -ne $expectedRuntimeFingerprint.ToLowerInvariant()) {
      throw (
        "Media runtime fingerprint mismatch. Installed=$installedRuntimeFingerprint " +
        "Expected=$expectedRuntimeFingerprint. This code-only update does not replace VapourSynth, " +
        "native source plugins, vs-placebo, or FFmpeg. Install the complete portable bundle for this release."
      )
    }
    $payloadRoot = Get-RequiredStringProperty -Object $manifest -Name "payload_root" -Context "manifest"
    Assert-SafeRelativePath -PathValue $payloadRoot -Context "payload_root"
    if ($payloadRoot -ne "payload") {
      throw "Unsupported payload_root '$payloadRoot' (expected 'payload')"
    }
    $signatureFile = Get-RequiredStringProperty -Object $manifest -Name "signature_file" -Context "manifest"
    Assert-SafeRelativePath -PathValue $signatureFile -Context "signature_file"
    if ($signatureFile -cne "update-manifest.sig") {
      throw "Unsupported signature_file '$signatureFile' (expected 'update-manifest.sig')"
    }

    foreach ($field in @("from_app_version_min", "to_app_version")) {
      $property = $manifest.PSObject.Properties[$field]
      if ($null -eq $property -or $property.Value -isnot [string]) { throw "Malformed app version field '$field' in update manifest." }
    }
    $fromVersionMin = Get-RequiredStringProperty -Object $manifest -Name "from_app_version_min" -Context "manifest"
    $fromVersionMax = Get-OptionalStringProperty -Object $manifest -Name "from_app_version_max"
    $targetVersion = Get-PayloadVersionFromManifest -Manifest $manifest
    foreach ($versionText in @($fromVersionMin, $targetVersion)) {
      if ($null -eq (ConvertTo-FrameCompareVersion $versionText)) { throw "Malformed app version '$versionText' in update manifest." }
    }
    $maximumProperty = $manifest.PSObject.Properties["from_app_version_max"]
    if ($null -ne $maximumProperty -and $null -ne $maximumProperty.Value -and
        ($maximumProperty.Value -isnot [string] -or $null -eq (ConvertTo-FrameCompareVersion $fromVersionMax))) {
      throw "Malformed maximum app version '$fromVersionMax'."
    }
    $targetLine = ConvertTo-FrameCompareVersion $targetVersion
    $minimumLine = ConvertTo-FrameCompareVersion $fromVersionMin
    if ($targetLine.Major -ne $minimumLine.Major -or $targetLine.Minor -ne $minimumLine.Minor) {
      throw "Target version must stay within the signed minimum's major.minor line."
    }
    $installedVersion = Get-BundleAppVersion -BundlePath $BundlePath
    if ([string]::IsNullOrWhiteSpace($installedVersion)) {
      throw "Installed app version could not be determined; refusing code-only update. Reinstall the complete portable bundle."
    }
    if (!(Test-FrameCompareVersionInRange -Value $installedVersion -Min $fromVersionMin -Max $fromVersionMax)) {
      throw "Installed app version '$installedVersion' is outside supported range [$fromVersionMin, $fromVersionMax]."
    }

    $filesProp = $manifest.PSObject.Properties["files"]
    if ($null -eq $filesProp -or $null -eq $filesProp.Value) {
      throw "Manifest is missing files."
    }
    $manifestFiles = @($filesProp.Value)
    if ($manifestFiles.Count -eq 0) {
      throw "Manifest files list is empty."
    }

    $zipEntryMap = @{}
    foreach ($entry in $entries) {
      $zipEntryMap[$entry.FullName] = $entry
    }

    $expectedZipEntries = New-Object System.Collections.Generic.HashSet[string] ([System.StringComparer]::OrdinalIgnoreCase)
    [void]$expectedZipEntries.Add("update-manifest.json")
    [void]$expectedZipEntries.Add($signatureFile)

    foreach ($file in $manifestFiles) {
      $path = Get-RequiredStringProperty -Object $file -Name "path" -Context "manifest.files[]"
      Assert-SafeRelativePath -PathValue $path -Context "manifest.files[].path"
      $normalizedPath = ($path -replace "\\", "/")
      if (!$normalizedPath.StartsWith("app/src/frame_compare/")) {
        throw "Invalid manifest file path (must stay under app/src/frame_compare): $path"
      }
      $zipPayloadPath = "$payloadRoot/$normalizedPath"
      if (-not $expectedZipEntries.Add($zipPayloadPath)) {
        throw "Manifest contains a duplicate file path: $path"
      }
      if (!$zipEntryMap.ContainsKey($zipPayloadPath)) {
        throw "Payload file missing from zip: $zipPayloadPath"
      }
    }

    foreach ($entry in $entries) {
      if (-not $expectedZipEntries.Contains($entry.FullName)) {
        throw "Unexpected file in update archive: $($entry.FullName)"
      }
    }

    foreach ($file in $manifestFiles) {
      $manifestPath = Get-RequiredStringProperty -Object $file -Name "path" -Context "manifest.files[]"
      $expectedHash = Get-RequiredStringProperty -Object $file -Name "sha256" -Context "manifest.files[]"
      if ($expectedHash -cnotmatch '^[a-f0-9]{64}$') {
        throw "Manifest sha256 is invalid for $manifestPath"
      }
      $expectedBytesRaw = Get-RequiredStringProperty -Object $file -Name "bytes" -Context "manifest.files[]"
      $expectedBytes = [int64]0
      if (-not [int64]::TryParse($expectedBytesRaw, [ref]$expectedBytes) -or $expectedBytes -lt 0) {
        throw "Manifest bytes is invalid for $manifestPath"
      }
      $zipPayloadPath = "$payloadRoot/$($manifestPath -replace '\\', '/')"
      $entry = $zipEntryMap[$zipPayloadPath]
      if ($entry.Length -ne $expectedBytes) {
        throw "Payload size mismatch for $manifestPath"
      }
      $outPath = Get-SafeChildPath -Root $tempRoot -RelativePath $zipPayloadPath -Context "zip extraction path"
      Ensure-Directory -Path (Split-Path -Parent $outPath)
      Copy-ZipEntryToFile -Entry $entry -DestinationPath $outPath -ExpectedBytes $expectedBytes
    }

    foreach ($file in $manifestFiles) {
      $manifestPath = Get-RequiredStringProperty -Object $file -Name "path" -Context "manifest.files[]"
      $expectedHash = Get-RequiredStringProperty -Object $file -Name "sha256" -Context "manifest.files[]"
      $payloadPath = Join-Path $tempRoot (
        Convert-RelativePathToNative -RelativePath (
          $payloadRoot + "/" + ($manifestPath -replace "\\", "/")
        )
      )
      if (!(Test-Path -LiteralPath $payloadPath -PathType Leaf)) {
        throw "Extracted payload file missing: $manifestPath"
      }
      $actualHash = Get-Sha256HexForFile -Path $payloadPath
      if ($actualHash -ne $expectedHash.ToLowerInvariant()) {
        throw "Payload hash mismatch for $manifestPath"
      }
    }

    $expectedFingerprint = Get-RequiredStringProperty -Object $manifest -Name "expected_requirements_lock_sha256" -Context "manifest"
    $installedFingerprint = [string]$installedCompatibility["requirements_lock_sha256"]
    if ($installedFingerprint -ne $expectedFingerprint.ToLowerInvariant()) {
      throw (
        "Dependency fingerprint mismatch; code-only update refused. " +
        "Install the complete Windows portable bundle from the releases page."
      )
    }

    $payloadDir = Join-PathParts -Root $tempRoot -Parts @("payload", "app", "src", "frame_compare")
    if (!(Test-Path -LiteralPath $payloadDir -PathType Container)) {
      throw "Extracted payload root missing: $payloadDir"
    }
    if (!(Test-Path -LiteralPath $targetDir -PathType Container)) {
      throw "Installed target path not found: $targetDir"
    }

    $backupId = [DateTime]::UtcNow.ToString("yyyyMMddHHmmss")
    $null = New-CompleteBackup -BundlePath $BundlePath -TargetDir $targetDir -Compatibility $installedCompatibility -Version $installedVersion -BackupId $backupId
    $relativeInventory = @($manifestFiles | ForEach-Object {
      [pscustomobject]@{ path = $_.path.Substring("app/src/frame_compare/".Length); sha256 = $_.sha256; bytes = $_.bytes }
    })
    Invoke-SourceTreeReplacement -BundlePath $BundlePath -TargetDir $targetDir -CandidateDir $payloadDir -ExpectedInventory $relativeInventory -ExpectedVersion $targetVersion -Operation "apply"

    Invoke-PurgeBackups -BundlePath $BundlePath -Keep 5 | Out-Null
    Write-Host "Update applied successfully."
    return 0
  } finally {
    if ($null -ne $zip) {
      $zip.Dispose()
    }
    if ($null -ne $zipStream) {
      $zipStream.Dispose()
    }
    if (Test-Path -LiteralPath $tempRoot) {
      try {
        Remove-Item -LiteralPath $tempRoot -Recurse -Force
      } catch {
        Write-Warning "Failed to remove temporary update directory: $tempRoot ($($_.Exception.Message))"
      }
    }
    try {
      Release-UpdateLock -LockInfo $lockInfo
    } catch {
      Write-Warning "Failed to release update lock: $($_.Exception.Message)"
    }
  }
}

function Show-Help() {
  Write-Host "Frame Compare updater"
  Write-Host ""
  Write-Host "Usage:"
  Write-Host "  frame-compare-update apply <update-zip>"
  Write-Host "  frame-compare-update rollback <backup-id>"
  Write-Host "  frame-compare-update list-backups"
  Write-Host "  frame-compare-update purge-backups --keep <N>"
  Write-Host "  frame-compare-update --help"
  Write-Host ""
  Write-Host "Commands:"
  Write-Host "  apply          Verify a signed code-only update, back up current code, and apply it."
  Write-Host "  rollback       Restore application code from one exact backup ID."
  Write-Host "  list-backups   List available backup IDs newest first."
  Write-Host "  purge-backups  Retain only the newest N backups (default: 5)."
}

function Invoke-FrameCompareUpdate([object[]]$ArgsValues) {
  $ErrorActionPreference = "Stop"
  Set-StrictMode -Version Latest
  $argsList = @()
  if ($null -ne $ArgsValues) {
    $argsList = @($ArgsValues | ForEach-Object { [string]$_ })
  }

  if ($argsList.Count -eq 0 -or $argsList[0] -eq "--help" -or $argsList[0] -eq "-h" -or $argsList[0] -eq "help") {
    Show-Help
    return 0
  }

  $config = Get-InstallConfig
  $bundlePath = [string]$config["bundle_path"]
  $command = $argsList[0].ToLowerInvariant()

  if ($command -eq "apply") {
    if ($argsList.Count -lt 2) {
      throw "Missing update zip path. Usage: frame-compare-update apply <update-zip>"
    }
    return Invoke-ApplyUpdate -BundlePath $bundlePath -UpdateZipPath $argsList[1]
  }

  if ($command -eq "rollback") {
    if ($argsList.Count -lt 2) {
      throw "Missing backup id. Usage: frame-compare-update rollback <backup-id>"
    }
    return Invoke-Rollback -BundlePath $bundlePath -BackupId $argsList[1]
  }

  if ($command -eq "list-backups") {
    return Invoke-ListBackups -BundlePath $bundlePath
  }

  if ($command -eq "purge-backups") {
    $keep = 5
    for ($i = 1; $i -lt $argsList.Count; $i++) {
      if ($argsList[$i] -eq "--keep") {
        if (($i + 1) -ge $argsList.Count) {
          throw "--keep requires an integer value"
        }
        if (-not [int]::TryParse($argsList[$i + 1], [ref]$keep)) {
          throw "--keep requires an integer value"
        }
        $i += 1
      } else {
        throw "Unknown argument for purge-backups: $($argsList[$i])"
      }
    }
    if ($keep -lt 0) {
      throw "--keep must be >= 0"
    }
    $lockInfo = $null
    try {
      $lockInfo = Acquire-UpdateLock -BundlePath $bundlePath
      return Invoke-PurgeBackups -BundlePath $bundlePath -Keep $keep
    } finally {
      Release-UpdateLock -LockInfo $lockInfo
    }
  }

  throw "Unknown command: $command. Run frame-compare-update --help"
}

if ($MyInvocation.InvocationName -ne ".") {
  try {
    exit (Invoke-FrameCompareUpdate -ArgsValues $args)
  } catch {
    [Console]::Error.WriteLine($_.Exception.Message)
    exit 1
  }
}
