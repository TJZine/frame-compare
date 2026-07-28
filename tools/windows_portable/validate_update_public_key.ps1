Param(
  [Parameter(Mandatory = $true)]
  [string]$PublicKeyPath
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest
$PSNativeCommandUseErrorActionPreference = $true

if (!(Test-Path -LiteralPath $PublicKeyPath)) {
  throw "Update public key not found: $PublicKeyPath"
}

$raw = Get-Content -LiteralPath $PublicKeyPath -Raw
if ($raw -match "REPLACE_WITH_RELEASE_KEY_ID") {
  throw "update_public_key.xml still contains placeholder metadata (REPLACE_WITH_RELEASE_KEY_ID)."
}

try {
  [xml]$xml = $raw
} catch {
  throw "Update public key is not valid XML: $PublicKeyPath"
}

$root = $xml.DocumentElement
if ($null -eq $root -or $root.LocalName -ne "RSAKeyValue" -or $root.NamespaceURI -ne "") {
  throw "Update public key root must be an unqualified RSAKeyValue element."
}
if ($root.Attributes.Count -ne 0) {
  throw "RSAKeyValue must not contain attributes."
}

$children = @($root.ChildNodes)
$expectedChildren = @("Modulus", "Exponent")
if ($children.Count -ne $expectedChildren.Count) {
  throw "RSAKeyValue must contain exactly Modulus and Exponent."
}
for ($index = 0; $index -lt $expectedChildren.Count; $index++) {
  $child = $children[$index]
  if (
    $child.NodeType -ne [System.Xml.XmlNodeType]::Element -or
    $child.LocalName -ne $expectedChildren[$index] -or
    $child.NamespaceURI -ne "" -or
    $child.Attributes.Count -ne 0
  ) {
    throw "RSAKeyValue must contain exactly Modulus and Exponent in that order."
  }
}

$modulusText = [string]$children[0].InnerText
$exponentText = [string]$children[1].InnerText
if ([string]::IsNullOrWhiteSpace($modulusText)) {
  throw "RSA Modulus is missing in $PublicKeyPath"
}
if ([string]::IsNullOrWhiteSpace($exponentText)) {
  throw "RSA Exponent is missing in $PublicKeyPath"
}

try {
  $modulusBytes = [Convert]::FromBase64String($modulusText.Trim())
} catch {
  throw "RSA Modulus is not valid base64 in $PublicKeyPath"
}
try {
  $exponentBytes = [Convert]::FromBase64String($exponentText.Trim())
} catch {
  throw "RSA Exponent is not valid base64 in $PublicKeyPath"
}
$exponentValue = [System.Numerics.BigInteger]::new($exponentBytes, $true, $true)
if ($exponentValue -lt 3 -or $exponentValue.IsEven) {
  throw "RSA Exponent must be an odd integer greater than or equal to 3."
}

if ($modulusBytes.Length -lt 256) {
  throw "RSA Modulus too short ($($modulusBytes.Length) bytes). Require >= 256 bytes (2048-bit)."
}

$rsa = [System.Security.Cryptography.RSA]::Create()
try {
  $parameters = [System.Security.Cryptography.RSAParameters]@{
    Modulus = $modulusBytes
    Exponent = $exponentBytes
  }
  try {
    $rsa.ImportParameters($parameters)
  } catch {
    throw "RSA Modulus and Exponent do not form an importable public key."
  }
  if ($rsa.KeySize -lt 2048) {
    throw "RSA public key is too short ($($rsa.KeySize) bits). Require >= 2048 bits."
  }
} finally {
  $rsa.Dispose()
}

Write-Host "OK: update public key XML appears valid ($($modulusBytes.Length) bytes modulus)."
