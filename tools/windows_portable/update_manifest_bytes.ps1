# Canonical bytes used by the builder and independently regenerated for release signing.
function New-UpdateManifestBytes(
  [string]$Version,
  [string]$RequirementsDigest,
  [string]$RuntimeFingerprint,
  [object[]]$Files
) {
  $parsedVersion = ConvertTo-FrameCompareVersion $Version
  if ($null -eq $parsedVersion) { throw "Invalid update version." }
  $manifest = [ordered]@{
    schema_version = 2
    target_platform = "windows-x64"
    to_app_version = $Version
    from_app_version_min = "{0}.{1}.0" -f $parsedVersion.Major, $parsedVersion.Minor
    from_app_version_max = $null
    expected_requirements_lock_sha256 = $RequirementsDigest
    expected_media_runtime_fingerprint = $RuntimeFingerprint
    signature_algorithm = "rsa-sha256-pkcs1"
    signature_file = "update-manifest.sig"
    payload_root = "payload"
    files = $Files
  }
  return ,([System.Text.Encoding]::UTF8.GetBytes(($manifest | ConvertTo-Json -Depth 6) + "`n"))
}
