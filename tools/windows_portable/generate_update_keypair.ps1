#Requires -Version 7.3

Param(
  [Parameter(Mandatory = $true)]
  [string]$PublicKeyPath,

  [Parameter(Mandatory = $true)]
  [string]$PrivateKeyPath,

  [Parameter(Mandatory = $true)]
  [ValidatePattern('^[A-Za-z0-9][A-Za-z0-9._-]{2,127}$')]
  [string]$KeyId,

  [ValidateRange(2048, 16384)]
  [int]$KeySize = 3072,

  [switch]$ReplacePlaceholderPublicKey
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest
$PSNativeCommandUseErrorActionPreference = $true

function Resolve-NewFilePath([string]$PathValue, [string]$FieldName) {
  if ([string]::IsNullOrWhiteSpace($PathValue)) {
    throw "$FieldName must not be empty."
  }

  $fullPath = [System.IO.Path]::GetFullPath($PathValue)
  $parent = [System.IO.Path]::GetDirectoryName($fullPath)
  if ([string]::IsNullOrWhiteSpace($parent) -or !(Test-Path -LiteralPath $parent -PathType Container)) {
    throw "$FieldName parent directory does not exist: $parent"
  }

  $resolvedParent = (Resolve-Path -LiteralPath $parent).Path
  return [System.IO.Path]::Combine($resolvedParent, [System.IO.Path]::GetFileName($fullPath))
}

function Test-PathContainedBy([string]$Candidate, [string]$Root) {
  $separator = [System.IO.Path]::DirectorySeparatorChar
  $rootWithSeparator = $Root.TrimEnd(
    [System.IO.Path]::DirectorySeparatorChar,
    [System.IO.Path]::AltDirectorySeparatorChar
  ) + $separator
  return $Candidate.StartsWith($rootWithSeparator, [System.StringComparison]::OrdinalIgnoreCase)
}

function Test-KnownPlaceholder([string]$PathValue, [string]$ExpectedPath) {
  if (![string]::Equals($PathValue, $ExpectedPath, [System.StringComparison]::OrdinalIgnoreCase)) {
    return $false
  }

  $raw = Get-Content -LiteralPath $PathValue -Raw
  if ($raw -notmatch "REPLACE_WITH_RELEASE_KEY_ID" -or $raw -notmatch "REPLACE_WITH_UTC_DATE") {
    return $false
  }

  try {
    [xml]$xml = $raw
  } catch {
    return $false
  }
  if ($null -eq $xml.RSAKeyValue) {
    return $false
  }

  $fields = @($xml.RSAKeyValue.ChildNodes | ForEach-Object { $_.Name })
  return (
    $fields.Count -eq 2 -and
    $fields[0] -eq "Modulus" -and
    $fields[1] -eq "Exponent" -and
    ([string]$xml.RSAKeyValue.Modulus).Trim() -eq "AQAB" -and
    ([string]$xml.RSAKeyValue.Exponent).Trim() -eq "AQAB"
  )
}

function Convert-ToBase64([byte[]]$Bytes) {
  return [System.Convert]::ToBase64String($Bytes)
}

function Get-PublicXml([System.Security.Cryptography.RSAParameters]$Parameters) {
  $modulus = Convert-ToBase64 -Bytes $Parameters.Modulus
  $exponent = Convert-ToBase64 -Bytes $Parameters.Exponent
  return "<RSAKeyValue><Modulus>$modulus</Modulus><Exponent>$exponent</Exponent></RSAKeyValue>"
}

function Get-PrivateXml([System.Security.Cryptography.RSAParameters]$Parameters) {
  $modulus = Convert-ToBase64 -Bytes $Parameters.Modulus
  $exponent = Convert-ToBase64 -Bytes $Parameters.Exponent
  $p = Convert-ToBase64 -Bytes $Parameters.P
  $q = Convert-ToBase64 -Bytes $Parameters.Q
  $dp = Convert-ToBase64 -Bytes $Parameters.DP
  $dq = Convert-ToBase64 -Bytes $Parameters.DQ
  $inverseQ = Convert-ToBase64 -Bytes $Parameters.InverseQ
  $d = Convert-ToBase64 -Bytes $Parameters.D
  return (
    "<RSAKeyValue><Modulus>$modulus</Modulus><Exponent>$exponent</Exponent>" +
    "<P>$p</P><Q>$q</Q><DP>$dp</DP><DQ>$dq</DQ>" +
    "<InverseQ>$inverseQ</InverseQ><D>$d</D></RSAKeyValue>"
  )
}

function Get-OwnerOnlyUnixFileMode() {
  return (
    [System.IO.UnixFileMode]::UserRead -bor
    [System.IO.UnixFileMode]::UserWrite
  )
}

function Set-PrivateFilePermissions([string]$PathValue) {
  if (!(Test-Path -LiteralPath $PathValue -PathType Leaf)) {
    throw "Private key file does not exist: $PathValue"
  }

  if ($env:OS -ne "Windows_NT") {
    $ownerOnly = Get-OwnerOnlyUnixFileMode
    [System.IO.File]::SetUnixFileMode($PathValue, $ownerOnly)
    if ([System.IO.File]::GetUnixFileMode($PathValue) -ne $ownerOnly) {
      throw "Failed to enforce owner-only permissions on private key: $PathValue"
    }
    return
  }

  $identity = [System.Security.Principal.WindowsIdentity]::GetCurrent()
  $acl = Get-Acl -LiteralPath $PathValue
  $acl.SetAccessRuleProtection($true, $false)
  foreach ($rule in @($acl.Access)) {
    [void]$acl.RemoveAccessRuleAll($rule)
  }
  $accessRule = [System.Security.AccessControl.FileSystemAccessRule]::new(
    $identity.User,
    [System.Security.AccessControl.FileSystemRights]::FullControl,
    [System.Security.AccessControl.InheritanceFlags]::None,
    [System.Security.AccessControl.PropagationFlags]::None,
    [System.Security.AccessControl.AccessControlType]::Allow
  )
  [void]$acl.AddAccessRule($accessRule)
  $acl.SetOwner($identity.User)
  Set-Acl -LiteralPath $PathValue -AclObject $acl
}

function Write-PrivateFile(
  [string]$PathValue,
  [string]$Content,
  [System.Text.Encoding]$Encoding
) {
  $options = [System.IO.FileStreamOptions]::new()
  $options.Mode = [System.IO.FileMode]::CreateNew
  $options.Access = [System.IO.FileAccess]::Write
  $options.Share = [System.IO.FileShare]::None
  if ($env:OS -ne "Windows_NT") {
    $options.UnixCreateMode = Get-OwnerOnlyUnixFileMode
  }

  $stream = $null
  $writer = $null
  try {
    $stream = [System.IO.FileStream]::new($PathValue, $options)
    Set-PrivateFilePermissions -PathValue $PathValue

    $writer = [System.IO.StreamWriter]::new($stream, $Encoding, 4096, $false)
    $stream = $null
    $writer.Write($Content)
    $writer.Flush()
  } finally {
    if ($null -ne $writer) {
      $writer.Dispose()
    } elseif ($null -ne $stream) {
      $stream.Dispose()
    }
  }
}

function Get-Sha256Hex([string]$Text) {
  $hasher = [System.Security.Cryptography.SHA256]::Create()
  try {
    $bytes = [System.Text.Encoding]::UTF8.GetBytes($Text)
    $hash = $hasher.ComputeHash($bytes)
    return [System.BitConverter]::ToString($hash).Replace("-", "").ToLowerInvariant()
  } finally {
    $hasher.Dispose()
  }
}

if ($KeyId -match "REPLACE_WITH_" -or $KeyId -match "(?i)placeholder") {
  throw "KeyId must be a non-placeholder identifier."
}

$repositoryRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot "..\..")).Path
$expectedPlaceholder = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot "update_public_key.xml")).Path
$resolvedPublicPath = Resolve-NewFilePath -PathValue $PublicKeyPath -FieldName "PublicKeyPath"
$resolvedPrivatePath = Resolve-NewFilePath -PathValue $PrivateKeyPath -FieldName "PrivateKeyPath"

if (Test-PathContainedBy -Candidate $resolvedPrivatePath -Root $repositoryRoot) {
  throw "PrivateKeyPath must resolve outside the repository."
}
if ([string]::Equals(
  $resolvedPublicPath,
  $resolvedPrivatePath,
  [System.StringComparison]::OrdinalIgnoreCase
)) {
  throw "PublicKeyPath and PrivateKeyPath must be different files."
}
if (Test-Path -LiteralPath $resolvedPrivatePath) {
  throw "PrivateKeyPath already exists; refusing overwrite."
}

$replacePlaceholder = $false
if (Test-Path -LiteralPath $resolvedPublicPath) {
  if (!$ReplacePlaceholderPublicKey) {
    throw "PublicKeyPath already exists; use -ReplacePlaceholderPublicKey only for the repository placeholder."
  }
  if (!(Test-KnownPlaceholder -PathValue $resolvedPublicPath -ExpectedPath $expectedPlaceholder)) {
    throw "PublicKeyPath is not the known repository placeholder; refusing overwrite."
  }
  $replacePlaceholder = $true
} elseif ($ReplacePlaceholderPublicKey) {
  throw "-ReplacePlaceholderPublicKey requires the known repository placeholder to exist."
}

$generatedAt = [System.DateTime]::UtcNow.ToString("yyyy-MM-ddTHH:mm:ssZ")
$rsa = $null
$publicTemp = $null
$privateTemp = $null
$privatePromoted = $false
try {
  $rsa = [System.Security.Cryptography.RSA]::Create()
  $rsa.KeySize = $KeySize
  if ($rsa.KeySize -lt 2048) {
    throw "RSA provider returned an unsafe key size: $($rsa.KeySize)"
  }

  $publicParameters = $rsa.ExportParameters($false)
  $privateParameters = $rsa.ExportParameters($true)
  $publicXml = Get-PublicXml -Parameters $publicParameters
  $privateXml = Get-PrivateXml -Parameters $privateParameters
  $publicFileText = (
    "<!--`n" +
    "  key_id: $KeyId`n" +
    "  generated_at: $generatedAt`n" +
    "-->`n" +
    $publicXml +
    "`n"
  )

  $publicTemp = Join-Path ([System.IO.Path]::GetDirectoryName($resolvedPublicPath)) (
    ".$([System.IO.Path]::GetFileName($resolvedPublicPath)).$([System.Guid]::NewGuid().ToString('N')).tmp"
  )
  $privateTemp = Join-Path ([System.IO.Path]::GetDirectoryName($resolvedPrivatePath)) (
    ".$([System.IO.Path]::GetFileName($resolvedPrivatePath)).$([System.Guid]::NewGuid().ToString('N')).tmp"
  )
  $utf8NoBom = [System.Text.UTF8Encoding]::new($false)
  [System.IO.File]::WriteAllText($publicTemp, $publicFileText, $utf8NoBom)
  Write-PrivateFile `
    -PathValue $privateTemp `
    -Content ($privateXml + "`n") `
    -Encoding $utf8NoBom

  [System.IO.File]::Move($privateTemp, $resolvedPrivatePath)
  $privateTemp = $null
  $privatePromoted = $true
  if ($replacePlaceholder) {
    [System.IO.File]::Move($publicTemp, $resolvedPublicPath, $true)
  } else {
    [System.IO.File]::Move($publicTemp, $resolvedPublicPath)
  }
  $publicTemp = $null

  $fingerprint = Get-Sha256Hex -Text $publicXml
  Write-Host "Generated Windows update keypair."
  Write-Host "Public key: $resolvedPublicPath"
  Write-Host "Private key: $resolvedPrivatePath"
  Write-Host "Key ID: $KeyId"
  Write-Host "Generated UTC: $generatedAt"
  Write-Host "RSA key size: $($rsa.KeySize)"
  Write-Host "Public key fingerprint (SHA256 over XML): $fingerprint"
} catch {
  if ($privatePromoted -and (Test-Path -LiteralPath $resolvedPrivatePath)) {
    Remove-Item -LiteralPath $resolvedPrivatePath -Force
  }
  throw
} finally {
  if ($null -ne $publicTemp -and (Test-Path -LiteralPath $publicTemp)) {
    Remove-Item -LiteralPath $publicTemp -Force
  }
  if ($null -ne $privateTemp -and (Test-Path -LiteralPath $privateTemp)) {
    Remove-Item -LiteralPath $privateTemp -Force
  }
  if ($null -ne $rsa) {
    try { $rsa.Clear() } catch { }
    $rsa.Dispose()
  }
}
