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

[xml]$xml = $raw
$modulusText = [string]$xml.RSAKeyValue.Modulus
$exponentText = [string]$xml.RSAKeyValue.Exponent
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

if ($modulusBytes.Length -lt 256) {
  throw "RSA Modulus too short ($($modulusBytes.Length) bytes). Require >= 256 bytes (2048-bit)."
}

Write-Host "OK: update public key XML appears valid ($($modulusBytes.Length) bytes modulus)."
