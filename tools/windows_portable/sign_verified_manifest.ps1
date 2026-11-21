param(
  [Parameter(Mandatory)][string]$ManifestPath,
  [Parameter(Mandatory)][string]$ManifestDigest,
  [Parameter(Mandatory)][string]$VerificationDigest,
  [Parameter(Mandatory)][string]$OutFile
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest
. (Join-Path $PSScriptRoot "release_update_contract.ps1")

Assert-ReleaseFileDigest $ManifestPath $ManifestDigest 4MB
$bytes = [IO.File]::ReadAllBytes($ManifestPath)
if ((Get-ReleaseDigest $bytes) -cne $ManifestDigest -or $VerificationDigest -cnotmatch '\A[0-9a-f]{64}\z') {
  throw "Invalid approved signing input."
}
$privateKeyXml = $env:WINDOWS_UPDATE_SIGNING_KEY_XML
Remove-Item Env:\WINDOWS_UPDATE_SIGNING_KEY_XML -ErrorAction SilentlyContinue
if ([string]::IsNullOrWhiteSpace($privateKeyXml) -or $privateKeyXml -ceq "environment-only") {
  throw "The protected environment signing key is required."
}

$signer = [Security.Cryptography.RSA]::Create()
$publicKey = [Security.Cryptography.RSA]::Create()
try {
  try { $signer.FromXmlString($privateKeyXml) } catch { throw "Invalid protected RSA signing key." }
  $publicKey.FromXmlString((Get-Content -LiteralPath (Join-Path $PSScriptRoot "update_public_key.xml") -Raw))
  if ($signer.ToXmlString($false) -cne $publicKey.ToXmlString($false)) {
    throw "Protected signing key does not match the committed update public key."
  }
  $sha256 = [Security.Cryptography.HashAlgorithmName]::SHA256
  $padding = [Security.Cryptography.RSASignaturePadding]::Pkcs1
  $signature = $signer.SignData($bytes, $sha256, $padding)
  if (!$publicKey.VerifyData($bytes, $signature, $sha256, $padding)) {
    throw "Detached signature verification failed."
  }
  # A single raw artifact carries the detached signature and its receipt binding.
  [ordered]@{
    verification_sha256 = $VerificationDigest
    manifest_sha256 = $ManifestDigest
    signature = [Convert]::ToBase64String($signature)
  } | ConvertTo-Json -Compress | Set-Content -LiteralPath $OutFile -Encoding utf8NoBOM
} finally {
  $privateKeyXml = $null
  $signer.Dispose()
  $publicKey.Dispose()
}
