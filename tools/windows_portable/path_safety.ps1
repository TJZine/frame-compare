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
