Param(
  [Parameter(Mandatory = $true)]
  [string]$UpdateZip
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest
$PSNativeCommandUseErrorActionPreference = $true

Add-Type -AssemblyName System.IO.Compression
Add-Type -AssemblyName System.IO.Compression.FileSystem

function Assert-SafeRelativePath([string]$PathValue, [string]$FieldName) {
  if ([string]::IsNullOrWhiteSpace($PathValue)) {
    throw "$FieldName must not be empty."
  }
  if ($PathValue -match '^[A-Za-z]:') {
    throw "$FieldName must not include a drive letter: $PathValue"
  }
  if ($PathValue.StartsWith("/") -or $PathValue.StartsWith('\')) {
    throw "$FieldName must be relative: $PathValue"
  }
  $normalized = ($PathValue -replace "\\", "/")
  if ($normalized -match '(^|/)\.\.(/|$)') {
    throw "$FieldName must not contain traversal segments: $PathValue"
  }
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
      throw "Failed to read complete zip entry bytes for $($Entry.FullName)"
    }
    return $buffer
  } finally {
    $stream.Dispose()
  }
}

function Write-StringEntry(
  [System.IO.Compression.ZipArchive]$Zip,
  [string]$EntryPath,
  [string]$Content
) {
  $existing = $Zip.GetEntry($EntryPath)
  if ($null -ne $existing) {
    $existing.Delete()
  }
  $entry = $Zip.CreateEntry($EntryPath, [System.IO.Compression.CompressionLevel]::Optimal)
  $stream = $entry.Open()
  try {
    $writer = New-Object System.IO.StreamWriter($stream, (New-Object System.Text.UTF8Encoding($false)))
    try {
      $writer.Write($Content)
    } finally {
      $writer.Dispose()
    }
  } finally {
    $stream.Dispose()
  }
}

function Get-Sha256Hex([byte[]]$Bytes) {
  $hasher = [System.Security.Cryptography.SHA256]::Create()
  try {
    $hashBytes = $hasher.ComputeHash($Bytes)
  } finally {
    $hasher.Dispose()
  }
  return ([System.BitConverter]::ToString($hashBytes).Replace("-", "").ToLowerInvariant())
}

$resolvedUpdateZip = (Resolve-Path -LiteralPath $UpdateZip).Path

$keyPath = $env:SIGNING_KEY_XML_PATH
if ([string]::IsNullOrWhiteSpace($keyPath)) {
  if (-not [Environment]::UserInteractive) {
    throw "Missing SIGNING_KEY_XML_PATH and no interactive console available."
  }
  try {
    if ([System.Console]::IsInputRedirected) {
      throw "Missing SIGNING_KEY_XML_PATH and input is redirected."
    }
  } catch {
    throw "Missing SIGNING_KEY_XML_PATH and input cannot be read interactively."
  }
  $keyPath = (Read-Host "Path to private signing key XML (SIGNING_KEY_XML_PATH)")
}
if ([string]::IsNullOrWhiteSpace($keyPath)) {
  throw "Missing signing key path. Set SIGNING_KEY_XML_PATH or provide it interactively."
}

$resolvedKeyXml = (Resolve-Path -LiteralPath $keyPath).Path
$privateKeyText = Get-Content -LiteralPath $resolvedKeyXml -Raw

$rsa = $null
$zip = $null
try {
  $rsa = New-Object System.Security.Cryptography.RSACryptoServiceProvider
  $rsa.PersistKeyInCsp = $false
  $rsa.FromXmlString($privateKeyText)

  $zip = [System.IO.Compression.ZipFile]::Open($resolvedUpdateZip, [System.IO.Compression.ZipArchiveMode]::Update)
  $manifestEntry = $zip.GetEntry("update-manifest.json")
  if ($null -eq $manifestEntry) {
    throw "update-manifest.json not found in zip: $resolvedUpdateZip"
  }

  $manifestBytes = Read-ZipEntryBytes -Entry $manifestEntry
  $manifestText = [System.Text.Encoding]::UTF8.GetString($manifestBytes)
  $manifest = $manifestText | ConvertFrom-Json

  $signatureFile = "update-manifest.sig"
  $signatureFileProp = $manifest.PSObject.Properties["signature_file"]
  if ($null -ne $signatureFileProp -and $null -ne $signatureFileProp.Value) {
    $signatureFile = [string]$signatureFileProp.Value
  }
  Assert-SafeRelativePath -PathValue $signatureFile -FieldName "signature_file"

  $signatureBytes = $rsa.SignData($manifestBytes, "SHA256")
  $signatureBase64 = [System.Convert]::ToBase64String($signatureBytes)
  Write-StringEntry -Zip $zip -EntryPath $signatureFile -Content $signatureBase64

  $publicXml = $rsa.ToXmlString($false)
  $fingerprintHex = Get-Sha256Hex -Bytes ([System.Text.Encoding]::UTF8.GetBytes($publicXml))
  Write-Host "Signed: $resolvedUpdateZip"
  Write-Host "Signature file: $signatureFile"
  $versionProp = $manifest.PSObject.Properties["to_app_version"]
  if ($null -ne $versionProp -and $null -ne $versionProp.Value) {
    Write-Host "Target app version: $([string]$versionProp.Value)"
  }
  Write-Host "Public key fingerprint (SHA256 over XML): $fingerprintHex"
} finally {
  if ($null -ne $zip) {
    $zip.Dispose()
  }
  if ($null -ne $rsa) {
    $rsa.Clear()
  }
}
