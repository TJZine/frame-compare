function Test-ArgsContainConfigFlag([string[]]$ArgsValues) {
  foreach ($arg in $ArgsValues) {
    if ($arg -eq "--config" -or $arg -eq "-c") {
      return $true
    }
    if ($arg.StartsWith("--config=")) {
      return $true
    }
    # Match compact "-cVALUE" only when it looks path-like to avoid false positives
    # such as "-cache". We accept typical path markers: "=", ".", "/", "\", ":".
    if ($arg -match '^-c(=|.*[\\/:.].*)') {
      return $true
    }
  }
  return $false
}

function Add-ArgsAtIndex([string[]]$ArgsValues, [int]$Index, [string[]]$InsertValues) {
  if ($Index -le 0) {
    return @($InsertValues + $ArgsValues)
  }
  if ($Index -ge $ArgsValues.Count) {
    return @($ArgsValues + $InsertValues)
  }
  return @($ArgsValues[0..($Index - 1)] + $InsertValues + $ArgsValues[$Index..($ArgsValues.Count - 1)])
}

function Get-ConfigInjectionIndex([string[]]$ArgsValues) {
  $commandIndex = -1
  for ($i = 0; $i -lt $ArgsValues.Count; $i++) {
    $token = $ArgsValues[$i]
    if ($null -ne $token -and $token -ne "" -and -not $token.StartsWith("-")) {
      $commandIndex = $i
      break
    }
  }
  if ($commandIndex -lt 0) {
    return -1
  }

  $command = $ArgsValues[$commandIndex]
  if ($command -eq "run" -or $command -eq "wizard") {
    return $commandIndex + 1
  }
  if ($command -eq "preset") {
    $subcommandIndex = -1
    for ($j = $commandIndex + 1; $j -lt $ArgsValues.Count; $j++) {
      $token = $ArgsValues[$j]
      if ($null -ne $token -and $token -ne "" -and -not $token.StartsWith("-")) {
        $subcommandIndex = $j
        break
      }
    }
    if ($subcommandIndex -lt 0) {
      return -1
    }
    $subcommand = $ArgsValues[$subcommandIndex]
    if ($subcommand -eq "list" -or $subcommand -eq "apply" -or $subcommand -eq "save") {
      return $subcommandIndex + 1
    }
    return -1
  }

  return -1
}

function Invoke-FrameCompareShim([object[]]$ArgsValues) {
  $ErrorActionPreference = "Stop"
  Set-StrictMode -Version Latest

  $shimDir = $PSScriptRoot
  if ([string]::IsNullOrWhiteSpace($shimDir)) {
    $shimDir = Split-Path -Parent $PSCommandPath
  }
  $installRoot = Split-Path -Parent $shimDir
  $stateDir = Join-Path $installRoot "state"
  $configPath = Join-Path $stateDir "config.json"

  if (!(Test-Path -LiteralPath $configPath)) {
    Write-Error -ErrorAction Continue "Config not found: $configPath`nRun install.cmd from the portable bundle."
    return 10
  }

  try {
    $config = Get-Content -LiteralPath $configPath -Raw | ConvertFrom-Json
  } catch {
    Write-Error -ErrorAction Continue "Invalid config file: $configPath`nRun install.cmd from the portable bundle."
    return 11
  }
  if ($null -eq $config) {
    Write-Error -ErrorAction Continue "Invalid config file: $configPath`nRun install.cmd from the portable bundle."
    return 11
  }

  $schemaVersion = 0
  $schemaProp = $config.PSObject.Properties["schema_version"]
  if ($null -ne $schemaProp -and $null -ne $schemaProp.Value) {
    $rawSchemaVersion = [string]$schemaProp.Value
    $parsedSchemaVersion = 0
    if (-not [int]::TryParse($rawSchemaVersion, [ref]$parsedSchemaVersion)) {
      Write-Error -ErrorAction Continue "Unsupported config schema version '$rawSchemaVersion' in $configPath`nRun install.cmd from the portable bundle."
      return 15
    }
    $schemaVersion = $parsedSchemaVersion
  }
  if ($schemaVersion -ne 1) {
    Write-Error -ErrorAction Continue "Unsupported config schema version '$schemaVersion' in $configPath`nRun install.cmd from the portable bundle."
    return 15
  }

  $installType = [string]$config.install_type
  if ($installType -ne "portable_bundle") {
    Write-Error -ErrorAction Continue "Unsupported install_type '$installType' in $configPath"
    return 16
  }

  $bundlePath = [string]$config.bundle_path
  if ([string]::IsNullOrWhiteSpace($bundlePath)) {
    Write-Error -ErrorAction Continue "bundle_path is missing in config: $configPath`nRun install.cmd from the portable bundle."
    return 12
  }

  if (!(Test-Path -LiteralPath $bundlePath)) {
    Write-Error -ErrorAction Continue "Portable bundle directory not found: $bundlePath`nRun install.cmd from the bundle's current location."
    return 13
  }

  $bundleLauncher = Join-Path $bundlePath "frame-compare.ps1"
  if (!(Test-Path -LiteralPath $bundleLauncher)) {
    Write-Error -ErrorAction Continue "Bundle launcher not found: $bundleLauncher`nRebuild or re-extract the portable bundle, then run install.cmd again."
    return 14
  }

  $stateConfigToml = Join-Path $stateDir "config.toml"

  $forwardArgs = @($ArgsValues | ForEach-Object { [string]$_ })
  if (Test-Path -LiteralPath $stateConfigToml) {
    $hasExplicitConfigFlag = Test-ArgsContainConfigFlag -ArgsValues $forwardArgs
    if (-not $hasExplicitConfigFlag) {
      $injectIndex = Get-ConfigInjectionIndex -ArgsValues $forwardArgs
      if ($injectIndex -ge 0) {
        $forwardArgs = Add-ArgsAtIndex -ArgsValues $forwardArgs -Index $injectIndex -InsertValues @("--config", $stateConfigToml)
      }
    }
  }

  $exitCode = 0
  Push-Location $bundlePath
  try {
    & $bundleLauncher @forwardArgs
    if ($null -ne $LASTEXITCODE) {
      $exitCode = $LASTEXITCODE
    } elseif ($?) {
      $exitCode = 0
    } else {
      $exitCode = 1
    }
  } finally {
    Pop-Location
  }
  return $exitCode
}

if ($MyInvocation.InvocationName -ne ".") {
  exit (Invoke-FrameCompareShim -ArgsValues $args)
}
