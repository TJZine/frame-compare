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

function Test-IsInteractiveSession() {
  if (-not [Environment]::UserInteractive) {
    return $false
  }
  try {
    if ([System.Console]::IsInputRedirected) {
      return $false
    }
  } catch {
    return $false
  }
  return $true
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

function Get-SafeChildPath([string]$Root, [string]$RelativePath, [string]$Context) {
  Assert-SafeRelativePath -PathValue $RelativePath -Context $Context
  $candidate = Join-Path $Root ($RelativePath -replace "/", "\\")
  $fullRoot = [System.IO.Path]::GetFullPath($Root)
  $fullCandidate = [System.IO.Path]::GetFullPath($candidate)
  $fullRootPrefix = $fullRoot.TrimEnd("\") + "\"
  if (!$fullCandidate.StartsWith($fullRootPrefix, [System.StringComparison]::OrdinalIgnoreCase)) {
    throw "$Context resolved outside root: $RelativePath"
  }
  return $fullCandidate
}

function Read-ZipEntryBytes([System.IO.Compression.ZipArchiveEntry]$Entry) {
  $stream = $Entry.Open()
  try {
    $buffer = New-Object byte[] $Entry.Length
    $offset = 0
    while ($offset -lt $buffer.Length) {
      $read = $stream.Read($buffer, $offset, $buffer.Length - $offset)
      if ($read -le 0) {
        break
      }
      $offset += $read
    }
    if ($offset -ne $buffer.Length) {
      throw "Failed to read complete entry bytes for $($Entry.FullName)"
    }
    return $buffer
  } finally {
    $stream.Dispose()
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
    $config = Get-Content -LiteralPath $configPath -Raw | ConvertFrom-Json
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
  $lockPath = Join-Path $BundlePath "app\\.update_lock"
  Ensure-Directory -Path (Split-Path -Parent $lockPath)
  try {
    $stream = [System.IO.File]::Open($lockPath, [System.IO.FileMode]::CreateNew, [System.IO.FileAccess]::Write, [System.IO.FileShare]::None)
    $bytes = [System.Text.Encoding]::ASCII.GetBytes(([DateTime]::UtcNow.ToString("o")))
    $stream.Write($bytes, 0, $bytes.Length)
    $stream.Flush()
    return [ordered]@{
      lock_path = $lockPath
      stream = $stream
    }
  } catch {
    throw "Another update appears to be running (lock exists): $lockPath"
  }
}

function Release-UpdateLock([object]$LockInfo) {
  if ($null -eq $LockInfo) {
    return
  }
  $stream = $LockInfo["stream"]
  $lockPath = [string]$LockInfo["lock_path"]
  if ($null -ne $stream) {
    $stream.Dispose()
  }
  if (Test-Path -LiteralPath $lockPath) {
    Remove-Item -LiteralPath $lockPath -Force
  }
}

function Get-InstalledRequirementsFingerprint([string]$BundlePath) {
  $bundleInfoPath = Join-Path $BundlePath "bundle_info.json"
  if (Test-Path -LiteralPath $bundleInfoPath) {
    $bundleInfo = Get-Content -LiteralPath $bundleInfoPath -Raw | ConvertFrom-Json
    $prop = $bundleInfo.PSObject.Properties["requirements_lock_sha256"]
    if ($null -ne $prop -and $null -ne $prop.Value) {
      return [string]$prop.Value
    }
  }
  $requirementsLock = Join-Path $BundlePath "requirements.lock.txt"
  if (!(Test-Path -LiteralPath $requirementsLock)) {
    throw "Installed requirements.lock.txt not found: $requirementsLock"
  }
  return Get-Sha256HexForFile -Path $requirementsLock
}

function Get-BackupRoot([string]$BundlePath) {
  return Join-Path $BundlePath "app\\.update_backups"
}

function Get-PayloadVersionFromManifest([object]$Manifest) {
  return Get-RequiredStringProperty -Object $Manifest -Name "to_app_version" -Context "manifest"
}

function Invoke-SmokeCheck([string]$BundlePath, [string]$ExpectedVersion) {
  $bundleLauncher = Join-Path $BundlePath "frame-compare.ps1"
  if (!(Test-Path -LiteralPath $bundleLauncher)) {
    throw "Bundle launcher not found: $bundleLauncher"
  }

  $versionOutput = & $bundleLauncher version 2>&1
  $exitCode = $LASTEXITCODE
  if ($exitCode -ne 0) {
    throw "Smoke check failed: frame-compare version exited with code $exitCode"
  }
  $joined = ($versionOutput -join "`n")
  if ($joined -match [regex]::Escape($ExpectedVersion)) {
    return
  }

  $pythonExe = Join-Path $BundlePath "python\\python.exe"
  if (!(Test-Path -LiteralPath $pythonExe)) {
    throw "Smoke check failed: expected version '$ExpectedVersion' not found in output."
  }
  $pyOut = & $pythonExe -c "import frame_compare; print(frame_compare.__version__)" 2>&1
  if ($LASTEXITCODE -ne 0) {
    throw "Smoke check failed: python import check exited with code $LASTEXITCODE"
  }
  $pyVersion = ($pyOut -join "").Trim()
  if ($pyVersion -ne $ExpectedVersion) {
    throw "Smoke check failed: expected version '$ExpectedVersion', got '$pyVersion'"
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
  if ($dirs.Count -le $Keep) {
    Write-Host "Backup retention already satisfied (count=$($dirs.Count), keep=$Keep)."
    return 0
  }
  for ($i = $Keep; $i -lt $dirs.Count; $i++) {
    Remove-Item -LiteralPath $dirs[$i].FullName -Recurse -Force
  }
  Write-Host "Purged $($dirs.Count - $Keep) old backup(s); kept $Keep."
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
  foreach ($dir in $dirs) {
    Write-Host $dir.Name
  }
  return 0
}

function Read-Choice([string]$Prompt) {
  return (Read-Host $Prompt).Trim()
}

function Confirm-Token([string]$Token, [string]$Prompt) {
  $value = Read-Choice -Prompt $Prompt
  return $value -ceq $Token
}

function Verify-ManifestSignature(
  [byte[]]$ManifestBytes,
  [string]$SignaturePath,
  [string]$PublicKeyPath
) {
  if (!(Test-Path -LiteralPath $SignaturePath)) {
    return $false
  }
  if (!(Test-Path -LiteralPath $PublicKeyPath)) {
    return $false
  }
  $signatureText = (Get-Content -LiteralPath $SignaturePath -Raw).Trim()
  if ([string]::IsNullOrWhiteSpace($signatureText)) {
    return $false
  }
  try {
    $signatureBytes = [Convert]::FromBase64String($signatureText)
  } catch {
    return $false
  }
  try {
    $keyXml = Get-Content -LiteralPath $PublicKeyPath -Raw
    $rsa = New-Object System.Security.Cryptography.RSACryptoServiceProvider
    $rsa.PersistKeyInCsp = $false
    $rsa.FromXmlString($keyXml)
    $isValid = $rsa.VerifyData($ManifestBytes, "SHA256", $signatureBytes)
    $rsa.Clear()
    return $isValid
  } catch {
    return $false
  }
}

function Test-StringInRange([string]$Value, [string]$Min, [string]$Max) {
  if ($Value -lt $Min) {
    return $false
  }
  if (![string]::IsNullOrWhiteSpace($Max) -and $Value -gt $Max) {
    return $false
  }
  return $true
}

function Get-BundleAppVersion([string]$BundlePath) {
  $pythonExe = Join-Path $BundlePath "python\\python.exe"
  if (!(Test-Path -LiteralPath $pythonExe)) {
    return ""
  }
  $result = & $pythonExe -c "import frame_compare; print(frame_compare.__version__)" 2>&1
  if ($LASTEXITCODE -ne 0) {
    return ""
  }
  return (($result -join "").Trim())
}

function Copy-DirectoryContents([string]$SourceDir, [string]$DestinationDir) {
  Ensure-Directory -Path $DestinationDir
  foreach ($item in (Get-ChildItem -LiteralPath $SourceDir -Force)) {
    Copy-Item -LiteralPath $item.FullName -Destination $DestinationDir -Force -Recurse
  }
}

function Restore-FromBackup([string]$BackupDir, [string]$TargetDir) {
  if (Test-Path -LiteralPath $TargetDir) {
    Invoke-WithRetry -Label "Remove failed target dir" -Action { Remove-Item -LiteralPath $TargetDir -Recurse -Force }
  }
  Copy-Item -LiteralPath $BackupDir -Destination $TargetDir -Recurse -Force
}

function Invoke-Rollback([string]$BundlePath, [string]$BackupId) {
  $lockInfo = $null
  try {
    $lockInfo = Acquire-UpdateLock -BundlePath $BundlePath
    $backupRoot = Get-BackupRoot -BundlePath $BundlePath
    $backupDir = Join-Path (Join-Path $backupRoot $BackupId) "frame_compare"
    if (!(Test-Path -LiteralPath $backupDir)) {
      throw "Backup id not found: $BackupId"
    }
    $targetDir = Join-Path $BundlePath "app\\src\\frame_compare"
    Restore-FromBackup -BackupDir $backupDir -TargetDir $targetDir
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
  $interactive = Test-IsInteractiveSession
  $lockInfo = $null
  $zip = $null
  $tempRoot = Join-Path ([System.IO.Path]::GetTempPath()) ("FrameCompareUpdate\\" + [guid]::NewGuid().ToString("N"))
  $backupId = ""
  $backupDir = ""
  $targetDir = Join-Path $BundlePath "app\\src\\frame_compare"
  $oldDir = "$targetDir.old"
  $newDir = "$targetDir.new"

  try {
    $lockInfo = Acquire-UpdateLock -BundlePath $BundlePath
    Ensure-Directory -Path $tempRoot

    $zip = [System.IO.Compression.ZipFile]::OpenRead($resolvedZip)
    $entries = @($zip.Entries)
    foreach ($entry in $entries) {
      if ([string]::IsNullOrWhiteSpace($entry.FullName)) {
        continue
      }
      Assert-SafeRelativePath -PathValue $entry.FullName -Context "zip entry"
    }

    $manifestEntry = $zip.GetEntry("update-manifest.json")
    if ($null -eq $manifestEntry) {
      throw "update-manifest.json not found in update zip."
    }
    $manifestBytes = Read-ZipEntryBytes -Entry $manifestEntry
    $manifestText = [System.Text.Encoding]::UTF8.GetString($manifestBytes)
    $manifest = $manifestText | ConvertFrom-Json

    $schemaVersion = [int](Get-RequiredStringProperty -Object $manifest -Name "schema_version" -Context "manifest")
    if ($schemaVersion -ne 1) {
      throw "Unsupported manifest schema_version '$schemaVersion'"
    }
    $platform = Get-RequiredStringProperty -Object $manifest -Name "target_platform" -Context "manifest"
    if ($platform -ne "windows-x64") {
      throw "Unsupported update target_platform '$platform'"
    }
    $payloadRoot = Get-RequiredStringProperty -Object $manifest -Name "payload_root" -Context "manifest"
    Assert-SafeRelativePath -PathValue $payloadRoot -Context "payload_root"
    if ($payloadRoot -ne "payload") {
      throw "Unsupported payload_root '$payloadRoot' (expected 'payload')"
    }
    $signatureFile = Get-RequiredStringProperty -Object $manifest -Name "signature_file" -Context "manifest"
    Assert-SafeRelativePath -PathValue $signatureFile -Context "signature_file"

    $fromVersionMin = Get-RequiredStringProperty -Object $manifest -Name "from_app_version_min" -Context "manifest"
    $fromVersionMax = Get-OptionalStringProperty -Object $manifest -Name "from_app_version_max"
    $installedVersion = Get-BundleAppVersion -BundlePath $BundlePath
    if (![string]::IsNullOrWhiteSpace($installedVersion)) {
      if (!(Test-StringInRange -Value $installedVersion -Min $fromVersionMin -Max $fromVersionMax)) {
        throw "Installed app version '$installedVersion' is outside supported range [$fromVersionMin, $fromVersionMax]."
      }
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
      [void]$expectedZipEntries.Add($zipPayloadPath)
      if (!$zipEntryMap.ContainsKey($zipPayloadPath)) {
        throw "Payload file missing from zip: $zipPayloadPath"
      }
    }

    foreach ($entryName in $expectedZipEntries) {
      if (!$zipEntryMap.ContainsKey($entryName)) {
        continue
      }
      $entry = $zipEntryMap[$entryName]
      $outPath = Get-SafeChildPath -Root $tempRoot -RelativePath $entryName -Context "zip extraction path"
      Ensure-Directory -Path (Split-Path -Parent $outPath)
      $stream = $entry.Open()
      $out = [System.IO.File]::Open($outPath, [System.IO.FileMode]::Create, [System.IO.FileAccess]::Write, [System.IO.FileShare]::None)
      try {
        $stream.CopyTo($out)
      } finally {
        $out.Dispose()
        $stream.Dispose()
      }
    }

    $signaturePath = Join-Path $tempRoot ($signatureFile -replace "/", "\\")
    $publicKeyPath = Join-Path $PSScriptRoot "update_public_key.xml"
    $signatureValid = Verify-ManifestSignature -ManifestBytes $manifestBytes -SignaturePath $signaturePath -PublicKeyPath $publicKeyPath
    $unsignedAllowed = $false
    if (-not $signatureValid) {
      if (-not $interactive) {
        throw "Signature missing or invalid; refusing to apply update in non-interactive mode."
      }
      Write-Host "WARNING: Update signature is missing or invalid."
      if (!(Confirm-Token -Token "UNSIGNED" -Prompt "Type UNSIGNED to apply anyway (Unsafe), or press Enter to cancel")) {
        throw "Canceled: unsigned update."
      }
      $unsignedAllowed = $true
    }

    foreach ($file in $manifestFiles) {
      $manifestPath = Get-RequiredStringProperty -Object $file -Name "path" -Context "manifest.files[]"
      $expectedHash = Get-RequiredStringProperty -Object $file -Name "sha256" -Context "manifest.files[]"
      $payloadPath = Join-Path $tempRoot (($payloadRoot + "/" + ($manifestPath -replace "\\", "/")) -replace "/", "\\")
      if (!(Test-Path -LiteralPath $payloadPath -PathType Leaf)) {
        throw "Extracted payload file missing: $manifestPath"
      }
      $actualHash = Get-Sha256HexForFile -Path $payloadPath
      if ($actualHash -ne $expectedHash.ToLowerInvariant()) {
        throw "Payload hash mismatch for $manifestPath"
      }
    }

    $expectedFingerprint = Get-RequiredStringProperty -Object $manifest -Name "expected_requirements_lock_sha256" -Context "manifest"
    $installedFingerprint = Get-InstalledRequirementsFingerprint -BundlePath $BundlePath
    if ($installedFingerprint -ne $expectedFingerprint.ToLowerInvariant()) {
      $promptRequiresUnsigned = -not $signatureValid
      if (-not $interactive) {
        throw "Dependency fingerprint mismatch and non-interactive mode; refusing update."
      }
      Write-Host "Dependency fingerprint mismatch detected."
      Write-Host "Installed: $installedFingerprint"
      Write-Host "Expected:  $expectedFingerprint"
      Write-Host "C = Cancel (recommended)"
      Write-Host "O = Open releases page"
      Write-Host "U = Unsafe apply anyway (requires typing APPLY)"
      if ($promptRequiresUnsigned) {
        Write-Host "X = Apply unsigned (Unsafe; requires typing UNSIGNED)"
      }
      $choice = (Read-Choice -Prompt "Choose [C/O/U/X], default C").ToUpperInvariant()
      if ([string]::IsNullOrWhiteSpace($choice) -or $choice -eq "C") {
        throw "Canceled due to dependency mismatch."
      }
      if ($choice -eq "O") {
        try {
          Start-Process "https://github.com/TJZine/frame-compare/releases/latest" | Out-Null
        } catch {
          Write-Host "Unable to open browser automatically."
        }
        throw "Canceled due to dependency mismatch."
      }
      if ($choice -eq "U") {
        if (!(Confirm-Token -Token "APPLY" -Prompt "Type APPLY to continue unsafely")) {
          throw "Canceled due to dependency mismatch."
        }
      } elseif ($choice -eq "X" -and $promptRequiresUnsigned) {
        if (!(Confirm-Token -Token "UNSIGNED" -Prompt "Type UNSIGNED to continue with unsigned update")) {
          throw "Canceled due to dependency mismatch."
        }
        $unsignedAllowed = $true
      } else {
        throw "Canceled due to dependency mismatch."
      }
    }

    $payloadDir = Join-Path $tempRoot "payload\\app\\src\\frame_compare"
    if (!(Test-Path -LiteralPath $payloadDir -PathType Container)) {
      throw "Extracted payload root missing: $payloadDir"
    }
    if (!(Test-Path -LiteralPath $targetDir -PathType Container)) {
      throw "Installed target path not found: $targetDir"
    }

    if (Test-Path -LiteralPath $newDir) {
      Invoke-WithRetry -Label "Cleanup existing .new directory" -Action { Remove-Item -LiteralPath $newDir -Recurse -Force }
    }
    if (Test-Path -LiteralPath $oldDir) {
      Invoke-WithRetry -Label "Cleanup existing .old directory" -Action { Remove-Item -LiteralPath $oldDir -Recurse -Force }
    }

    $backupRoot = Get-BackupRoot -BundlePath $BundlePath
    Ensure-Directory -Path $backupRoot
    $backupId = (Get-Date).ToString("yyyyMMddHHmmss")
    $backupDir = Join-Path (Join-Path $backupRoot $backupId) "frame_compare"
    Ensure-Directory -Path (Split-Path -Parent $backupDir)
    Copy-Item -LiteralPath $targetDir -Destination $backupDir -Recurse -Force

    Copy-DirectoryContents -SourceDir $payloadDir -DestinationDir $newDir
    Invoke-WithRetry -Label "Rename current frame_compare to .old" -Action { Move-Item -LiteralPath $targetDir -Destination $oldDir -Force }
    Invoke-WithRetry -Label "Rename .new into place" -Action { Move-Item -LiteralPath $newDir -Destination $targetDir -Force }

    try {
      $targetVersion = Get-PayloadVersionFromManifest -Manifest $manifest
      Invoke-SmokeCheck -BundlePath $BundlePath -ExpectedVersion $targetVersion
    } catch {
      Write-Host "Smoke check failed; rolling back update."
      if (Test-Path -LiteralPath $targetDir) {
        Invoke-WithRetry -Label "Remove failed target after smoke check failure" -Action { Remove-Item -LiteralPath $targetDir -Recurse -Force }
      }
      if (Test-Path -LiteralPath $oldDir) {
        Invoke-WithRetry -Label "Restore .old after smoke check failure" -Action { Move-Item -LiteralPath $oldDir -Destination $targetDir -Force }
      } elseif (![string]::IsNullOrWhiteSpace($backupDir) -and (Test-Path -LiteralPath $backupDir)) {
        Restore-FromBackup -BackupDir $backupDir -TargetDir $targetDir
      }
      throw
    }

    if (Test-Path -LiteralPath $oldDir) {
      Invoke-WithRetry -Label "Remove .old after successful update" -Action { Remove-Item -LiteralPath $oldDir -Recurse -Force }
    }
    if (Test-Path -LiteralPath $newDir) {
      Invoke-WithRetry -Label "Remove .new after successful update" -Action { Remove-Item -LiteralPath $newDir -Recurse -Force }
    }

    Invoke-PurgeBackups -BundlePath $BundlePath -Keep 5 | Out-Null
    Write-Host "Update applied successfully."
    if ($unsignedAllowed) {
      Write-Host "WARNING: Update was applied using an unsafe unsigned path."
    }
    return 0
  } finally {
    if ($null -ne $zip) {
      $zip.Dispose()
    }
    if (Test-Path -LiteralPath $tempRoot) {
      Remove-Item -LiteralPath $tempRoot -Recurse -Force
    }
    Release-UpdateLock -LockInfo $lockInfo
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
    return Invoke-PurgeBackups -BundlePath $bundlePath -Keep $keep
  }

  throw "Unknown command: $command. Run frame-compare-update --help"
}

if ($MyInvocation.InvocationName -ne ".") {
  try {
    exit (Invoke-FrameCompareUpdate -ArgsValues $args)
  } catch {
    Write-Error -ErrorAction Continue $_.Exception.Message
    exit 1
  }
}
