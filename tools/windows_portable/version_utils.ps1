function Get-AppVersionFromSource([string]$RepoRootPath) {
  $initPy = Join-Path $RepoRootPath "src\\frame_compare\\__init__.py"
  if (!(Test-Path -LiteralPath $initPy)) {
    throw "Version source file not found: $initPy"
  }
  $content = Get-Content -LiteralPath $initPy -Raw
  $match = [regex]::Match($content, '__version__\s*=\s*"([^"]+)"')
  if (!$match.Success) {
    throw "Could not parse __version__ from $initPy"
  }
  $version = $match.Groups[1].Value
  if ($version -cnotmatch '\A(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)(?:rc[1-9][0-9]*)?\z') {
    throw "Malformed app version '$version' in $initPy"
  }
  return $version
}
