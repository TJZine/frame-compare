function Test-PathWithin([string]$Path, [string]$Parent) {
  $parentPrefix = $Parent.TrimEnd(
    [System.IO.Path]::DirectorySeparatorChar,
    [System.IO.Path]::AltDirectorySeparatorChar
  ) + [System.IO.Path]::DirectorySeparatorChar
  return $Path.StartsWith($parentPrefix, [System.StringComparison]::OrdinalIgnoreCase)
}

# Shared build-time helpers; safe to dot-source more than once.
if (-not ("FrameCompareNativeDirectory" -as [type])) {
  Add-Type @"
using System;
using System.Runtime.InteropServices;
public static class FrameCompareNativeDirectory {
    [DllImport("kernel32.dll", CharSet = CharSet.Unicode, SetLastError = true)]
    [return: MarshalAs(UnmanagedType.Bool)]
    public static extern bool CreateDirectory(string path, IntPtr securityAttributes);
}

"@
}

function New-AtomicallyReservedDirectory([string]$Path, [string]$Label = "ExtractRoot") {
  Assert-NoReparsePointAncestor -Path $Path -Label $Label
  [System.IO.Directory]::CreateDirectory((Split-Path -Parent $Path)) | Out-Null
  if ([FrameCompareNativeDirectory]::CreateDirectory($Path, [IntPtr]::Zero)) {
    return $Path
  }
  $errorCode = [Runtime.InteropServices.Marshal]::GetLastWin32Error()
  if ($errorCode -eq 183) {
    throw "$Label must not already exist; choose a fresh verification directory: $Path"
  }
  throw [System.ComponentModel.Win32Exception]::new(
    $errorCode,
    "Could not atomically reserve ${Label}: $Path"
  )
}

# Prefix comparisons are meaningful only when no existing ancestor redirects the
# path. Refuse junctions, symlinks, mount points, and unreadable ancestry rather
# than claiming containment from a lexical spelling.
function Assert-NoReparsePointAncestor([string]$Path, [string]$Label) {
  $ancestor = [IO.Path]::GetFullPath($Path)
  while (![string]::IsNullOrEmpty($ancestor)) {
    try {
      $item = Get-Item -LiteralPath $ancestor -Force -ErrorAction Stop
      if (($item.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0) {
        throw "$Label has a reparse-point ancestor; choose a physical path: $Path (ancestor: $ancestor)"
      }
    } catch [System.Management.Automation.ItemNotFoundException] {
      # Missing suffixes are expected for fresh output paths. Continue through
      # their existing parents, where redirects or access errors still matter.
    }
    $parent = Split-Path -Parent $ancestor
    if ($parent -eq $ancestor) { break }
    $ancestor = $parent
  }
}
