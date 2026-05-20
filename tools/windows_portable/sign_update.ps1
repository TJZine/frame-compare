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
  $buffer = [System.IO.MemoryStream]::new()
  try {
    $stream.CopyTo($buffer)
    return $buffer.ToArray()
  } finally {
    $buffer.Dispose()
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
  $writer = New-Object System.IO.StreamWriter($stream, (New-Object System.Text.UTF8Encoding($false)))
  try {
    $writer.Write($Content)
  } finally {
    $writer.Dispose()
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

function Get-RsaParameterBytes([xml]$KeyXml, [string]$Name, [bool]$Required) {
  $node = $KeyXml.RSAKeyValue.$Name
  if ($null -eq $node -or [string]::IsNullOrWhiteSpace([string]$node)) {
    if ($Required) {
      throw "RSA key XML is missing required '$Name' value."
    }
    return $null
  }
  return [System.Convert]::FromBase64String([string]$node)
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
      $rsa.FromXmlString($KeyXmlText)
      return $rsa
    } catch {
      $rsa.Clear()
      $rsa.Dispose()
      throw
    }
  }
}

function Get-PublicRsaXml([string]$KeyXmlText) {
  [xml]$keyXml = $KeyXmlText
  if ($null -eq $keyXml.RSAKeyValue) {
    throw "RSA key XML must have an RSAKeyValue root."
  }
  $modulus = [string]$keyXml.RSAKeyValue.Modulus
  $exponent = [string]$keyXml.RSAKeyValue.Exponent
  if ([string]::IsNullOrWhiteSpace($modulus) -or [string]::IsNullOrWhiteSpace($exponent)) {
    throw "RSA key XML is missing public key values."
  }
  return "<RSAKeyValue><Modulus>$modulus</Modulus><Exponent>$exponent</Exponent></RSAKeyValue>"
}

function Sign-ManifestBytes([System.Security.Cryptography.RSA]$Rsa, [byte[]]$Bytes) {
  try {
    return $Rsa.SignData(
      $Bytes,
      [System.Security.Cryptography.HashAlgorithmName]::SHA256,
      [System.Security.Cryptography.RSASignaturePadding]::Pkcs1
    )
  } catch [System.Management.Automation.MethodException] {
    return $Rsa.SignData($Bytes, "SHA256")
  } catch [System.MissingMethodException] {
    return $Rsa.SignData($Bytes, "SHA256")
  }
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
    throw "Missing SIGNING_KEY_XML_PATH and input cannot be read interactively: $($_.Exception.Message)"
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
  $rsa = New-RsaFromXml -KeyXmlText $privateKeyText

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

  $signatureBytes = Sign-ManifestBytes -Rsa $rsa -Bytes $manifestBytes
  $signatureBase64 = [System.Convert]::ToBase64String($signatureBytes)
  Write-StringEntry -Zip $zip -EntryPath $signatureFile -Content $signatureBase64

  Write-Host "Signed: $resolvedUpdateZip"
  Write-Host "Signature file: $signatureFile"
  $versionProp = $manifest.PSObject.Properties["to_app_version"]
  if ($null -ne $versionProp -and $null -ne $versionProp.Value) {
    Write-Host "Target app version: $([string]$versionProp.Value)"
  }
  $publicKeyText = Get-PublicRsaXml -KeyXmlText $privateKeyText
  $fingerprintHex = Get-Sha256Hex -Bytes ([System.Text.Encoding]::UTF8.GetBytes($publicKeyText))
  Write-Host "Public key fingerprint (SHA256 over XML): $fingerprintHex"
} finally {
  if ($null -ne $zip) {
    $zip.Dispose()
  }
  if ($null -ne $rsa) {
    try { $rsa.Clear() } catch { }
    $rsa.Dispose()
  }
}
