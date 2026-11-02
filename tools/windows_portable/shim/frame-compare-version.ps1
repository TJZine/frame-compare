# Shared stable/RC grammar. Keep Windows PowerShell 5.1 support.
function ConvertTo-FrameCompareVersion([string]$Value) {
  if ($Value -cnotmatch '^(0|[1-9][0-9]{0,8})\.(0|[1-9][0-9]{0,8})\.(0|[1-9][0-9]{0,8})(?:rc([1-9][0-9]{0,8}))?\z') {
    return $null
  }
  $culture = [Globalization.CultureInfo]::InvariantCulture
  $rc = $null
  if ($Matches[4]) { $rc = [int]::Parse($Matches[4], $culture) }
  return [pscustomobject]@{
    Text = $Value
    Major = [int]::Parse($Matches[1], $culture)
    Minor = [int]::Parse($Matches[2], $culture)
    Patch = [int]::Parse($Matches[3], $culture)
    Rc = $rc
  }
}

function Compare-FrameCompareVersion([string]$Left, [string]$Right) {
  $a = ConvertTo-FrameCompareVersion $Left
  $b = ConvertTo-FrameCompareVersion $Right
  if ($null -eq $a -or $null -eq $b) { throw "Malformed app version: '$Left' or '$Right'" }
  foreach ($field in @("Major", "Minor", "Patch")) {
    $order = $a.$field.CompareTo($b.$field)
    if ($order -ne 0) { return $order }
  }
  if ($null -eq $a.Rc -and $null -eq $b.Rc) { return 0 }
  if ($null -eq $a.Rc) { return 1 }
  if ($null -eq $b.Rc) { return -1 }
  return $a.Rc.CompareTo($b.Rc)
}

function Test-FrameCompareVersionInRange([string]$Value, [string]$Min, [string]$Max) {
  $valueVersion = ConvertTo-FrameCompareVersion $Value
  $minVersion = ConvertTo-FrameCompareVersion $Min
  if ($null -eq $valueVersion -or $null -eq $minVersion) { return $false }
  if ($valueVersion.Major -ne $minVersion.Major -or $valueVersion.Minor -ne $minVersion.Minor) { return $false }
  $minimum = $Min
  # A numeric stable minimum retains old updater compatibility while admitting
  # that base's RCs to the same update line.
  if ($null -eq $minVersion.Rc) { $minimum = $Min + "rc1" }
  if ((Compare-FrameCompareVersion $Value $minimum) -lt 0) { return $false }
  if (![string]::IsNullOrEmpty($Max)) {
    if ($null -eq (ConvertTo-FrameCompareVersion $Max)) { return $false }
    if ((Compare-FrameCompareVersion $Value $Max) -gt 0) { return $false }
  }
  return $true
}
