Param(
  [ValidateSet("Move", "Leave")]
  [string]$UserData = "Move"
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

. (Join-Path $PSScriptRoot "portable_activation.ps1")
Write-Host "Portable installer PowerShell version: $($PSVersionTable.PSVersion)"
Invoke-PortableActivation -BundleRoot $PSScriptRoot -StateDirectory (Get-PortableStateDirectory) -UserData $UserData
