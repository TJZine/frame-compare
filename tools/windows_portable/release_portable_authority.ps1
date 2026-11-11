. (Join-Path $PSScriptRoot "portable_launchers.ps1")

function Get-ArchiveEntryRecord([IO.Compression.ZipArchiveEntry]$Entry) {
  $hash = [Security.Cryptography.IncrementalHash]::CreateHash([Security.Cryptography.HashAlgorithmName]::SHA256)
  $stream = $null
  try {
    $stream = $Entry.Open()
    $buffer = [byte[]]::new(65536)
    $size = [long]0
    while (($read = $stream.Read($buffer, 0, $buffer.Length)) -gt 0) {
      $size += $read
      if ($size -gt $Entry.Length) { throw "ZIP member exceeds its declared size." }
      $hash.AppendData($buffer, 0, $read)
    }
    if ($size -ne $Entry.Length) { throw "ZIP member does not match its declared size." }
    return @{
      bytes = $size
      sha256 = [Convert]::ToHexString($hash.GetHashAndReset()).ToLowerInvariant()
    }
  } finally {
    if ($null -ne $stream) { $stream.Dispose() }
    $hash.Dispose()
  }
}

function Get-PortableAuthority([string]$ExpectedSha, [hashtable]$Source) {
  $owner = "tools/windows_portable"
  $paths = [Collections.Generic.Dictionary[string, string]]::new([StringComparer]::Ordinal)
  foreach ($file in @("README.txt", "install.cmd", "install.ps1", "uninstall.cmd", "uninstall.ps1")) {
    $paths.Add("$owner/$file", $file)
  }
  $paths.Add("$owner/update_public_key.xml", "shim/update_public_key.xml")
  $paths.Add("$owner/manifest.windows-x64.json", "manifest.json")

  $include = @($paths.Keys) + @("$owner/shim")
  $snapshot = Join-Path ([IO.Path]::GetTempPath()) ("frame-compare-portable-authority-" + [guid]::NewGuid())
  $approved = [Collections.Generic.Dictionary[string, object]]::new([StringComparer]::OrdinalIgnoreCase)
  try {
    $null = New-Item -ItemType Directory -Path $snapshot
    $sourcePath = Join-Path $snapshot "source.zip"
    git archive --format=zip "--output=$sourcePath" $ExpectedSha -- @include
    $zip = [IO.Compression.ZipFile]::OpenRead($sourcePath)
    try {
      foreach ($entry in $zip.Entries) {
        $name = $entry.FullName
        if ($name.EndsWith("/")) { continue }
        Assert-ReleaseZipEntry $entry
        if ($paths.ContainsKey($name)) {
          $approved.Add($paths[$name], (Get-ArchiveEntryRecord $entry))
        } elseif ($name.StartsWith("$owner/shim/", [StringComparison]::Ordinal)) {
          $approved.Add($name.Substring($owner.Length + 1), (Get-ArchiveEntryRecord $entry))
        }
      }
    } finally { $zip.Dispose() }

    Write-LauncherFiles $snapshot
    foreach ($launcher in @("frame-compare.ps1", "frame-compare.cmd", "frame-compare-update.ps1", "frame-compare-update.cmd")) {
      $item = Get-Item -LiteralPath (Join-Path $snapshot $launcher)
      $approved.Add($launcher, @{ bytes = $item.Length; sha256 = Get-ReleaseFileDigest $item.FullName })
    }
  } finally {
    if (Test-Path -LiteralPath $snapshot) { Remove-Item -LiteralPath $snapshot -Recurse -Force }
  }
  foreach ($file in $Source.Files) { $approved.Add($file.path, $file) }
  return @{ SourceFiles = $approved }
}

function Write-IndependentPortableZip(
  [string]$Candidate, [string]$Target, [string]$RequirementsPath
) {
  $tempRoot = if ($env:RUNNER_TEMP) { $env:RUNNER_TEMP } else { [IO.Path]::GetTempPath() }
  $scratch = Join-Path $tempRoot ("fc-" + [guid]::NewGuid().ToString("N"))
  $root = Join-Path $scratch "layout"
  try {
    & (Join-Path $PSScriptRoot "build_portable.ps1") `
      -OutDir $root -CacheDir (Join-Path $scratch "pins") -RequirementsPath $RequirementsPath `
      -AssemblyOnly -RequireReleasePublicKey | Out-Host
    $hostPython = (& uv python find --system --no-project --no-python-downloads 3.13).Trim()
    & $hostPython -B -I -S (Join-Path $PSScriptRoot "portable_bundle.py") verify-and-pack `
      --root $root --candidate $Candidate --output $Target | Out-Host
  } finally {
    if (Test-Path -LiteralPath $scratch) { Remove-Item -LiteralPath $scratch -Recurse -Force }
  }
}
