. (Join-Path $PSScriptRoot "version_utils.ps1")
. (Join-Path $PSScriptRoot "update_manifest_bytes.ps1")

function Get-ReleaseDigest([byte[]]$Bytes) {
  return [Convert]::ToHexString([Security.Cryptography.SHA256]::HashData($Bytes)).ToLowerInvariant()
}

function Get-ReleaseFileDigest([string]$Path) {
  return (Get-FileHash -LiteralPath $Path -Algorithm SHA256).Hash.ToLowerInvariant()
}

function Assert-ReleaseFileDigest([string]$Path, [string]$Expected, [long]$MaxBytes) {
  $item = Get-Item -LiteralPath $Path -Force
  if (
    $item -isnot [IO.FileInfo] -or ($item.Attributes -band [IO.FileAttributes]::ReparsePoint) -or
    $item.Length -le 0 -or $item.Length -gt $MaxBytes
  ) {
    throw "Missing, unsafe, or overlong release input: $Path"
  }
  if ($Expected -cnotmatch '\A[0-9a-f]{64}\z' -or (Get-ReleaseFileDigest $Path) -cne $Expected) {
    throw "Release input digest mismatch: $Path"
  }
}

function Get-ReleaseSourceContract([string]$ExpectedSha, [string]$ReleaseTag) {
  $head = (git rev-parse HEAD).Trim()
  if ($ExpectedSha -cnotmatch '\A[0-9a-f]{40}\z' -or $head -cne $ExpectedSha) {
    throw "Windows release checkout does not match the exact expected SHA."
  }
  $version = Get-AppVersionFromSource (Get-Location).ProviderPath
  $expectedTag = "v" + ($version -creplace 'rc([0-9]+)$', '-rc.$1')
  if ($ReleaseTag -cne "" -and $ReleaseTag -cne $expectedTag) {
    throw "Release tag does not match the approved source version."
  }
  $runtimeManifestPath = "tools/windows_portable/manifest.windows-x64.json"
  $runtimeManifest = Get-Content -LiteralPath $runtimeManifestPath -Raw | ConvertFrom-Json
  $runtimeFingerprint = $runtimeManifest.bundle.runtime_fingerprints.full
  if ($runtimeFingerprint -cnotmatch '\A[0-9a-f]{64}\z') {
    throw "Invalid Windows runtime fingerprint in the approved source."
  }

  # Git's raw tree bytes avoid workstation EOL conversion and untracked files.
  $snapshot = Join-Path ([IO.Path]::GetTempPath()) ("frame-compare-source-" + [guid]::NewGuid() + ".zip")
  try {
    git archive --format=zip "--output=$snapshot" $ExpectedSha -- src/frame_compare
    $sourceZip = [IO.Compression.ZipFile]::OpenRead($snapshot)
    try {
      $files = @(foreach ($entry in $sourceZip.Entries) {
        $name = $entry.FullName
        if ($name.EndsWith("/") -or $name -match '(^|/)__pycache__(/|$)|\.py[co]$') { continue }
        if (($entry.ExternalAttributes -shr 16 -band 0xF000) -eq 0xA000) {
          throw "Update source contains a symbolic link."
        }
        $stream = $entry.Open()
        try {
          [ordered]@{
            path = "app/$name"
            sha256 = [Convert]::ToHexString([Security.Cryptography.SHA256]::HashData($stream)).ToLowerInvariant()
            bytes = $entry.Length
          }
        } finally { $stream.Dispose() }
      })
    } finally { $sourceZip.Dispose() }
  } finally {
    Remove-Item -LiteralPath $snapshot -ErrorAction SilentlyContinue
  }
  if ($files.Count -eq 0) { throw "Approved source tree has no update files." }
  return @{
    Version = $version
    RuntimeFingerprint = $runtimeFingerprint
    RuntimeManifest = $runtimeManifest
    Files = @($files | Sort-Object { $_["path"] })
  }
}
