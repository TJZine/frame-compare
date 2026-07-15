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
  if ($command -eq "preset" -or $command -eq "history") {
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
    if (
      ($command -eq "preset" -and ($subcommand -eq "list" -or $subcommand -eq "apply" -or $subcommand -eq "save")) -or
      ($command -eq "history" -and ($subcommand -eq "list" -or $subcommand -eq "open"))
    ) {
      return $subcommandIndex + 1
    }
    return -1
  }

  return -1
}

$script:FrameCompareShimExitCode = 1

function Set-FrameCompareShimExitCode([int]$ExitCode) {
  $script:FrameCompareShimExitCode = $ExitCode
}

function Get-FrameCompareShimEnvironmentValue([string]$Name) {
  return [Environment]::GetEnvironmentVariable($Name, "Process")
}

function Restore-FrameCompareShimEnvironmentValue([string]$Name, [object]$Value) {
  if ($null -eq $Value) {
    Remove-Item -LiteralPath "Env:$Name" -ErrorAction SilentlyContinue
    return
  }
  [Environment]::SetEnvironmentVariable($Name, [string]$Value, "Process")
}

function Invoke-FrameCompareShim([object[]]$ArgsValues) {
  $ErrorActionPreference = "Stop"
  Set-StrictMode -Version Latest

  if ($null -eq $ArgsValues) {
    $ArgsValues = @()
  } else {
    $ArgsValues = @($ArgsValues)
  }

  $shimDir = $PSScriptRoot
  if ([string]::IsNullOrWhiteSpace($shimDir)) {
    $shimDir = Split-Path -Parent $PSCommandPath
  }
  $installRoot = Split-Path -Parent $shimDir
  $stateDir = Join-Path $installRoot "state"
  $configPath = Join-Path $stateDir "config.json"

  if (!(Test-Path -LiteralPath $configPath)) {
    Write-Error -ErrorAction Continue "Config not found: $configPath`nRun install.cmd from the portable bundle."
    Set-FrameCompareShimExitCode -ExitCode 10
    return
  }

  try {
    $config = Get-Content -LiteralPath $configPath -Raw | ConvertFrom-Json
  } catch {
    Write-Error -ErrorAction Continue "Invalid config file: $configPath`nRun install.cmd from the portable bundle."
    Set-FrameCompareShimExitCode -ExitCode 11
    return
  }
  if ($null -eq $config) {
    Write-Error -ErrorAction Continue "Invalid config file: $configPath`nRun install.cmd from the portable bundle."
    Set-FrameCompareShimExitCode -ExitCode 11
    return
  }

  $schemaVersion = 0
  $schemaProp = $config.PSObject.Properties["schema_version"]
  if ($null -ne $schemaProp -and $null -ne $schemaProp.Value) {
    $rawSchemaVersion = [string]$schemaProp.Value
    $parsedSchemaVersion = 0
    if (-not [int]::TryParse($rawSchemaVersion, [ref]$parsedSchemaVersion)) {
      Write-Error -ErrorAction Continue "Unsupported config schema version '$rawSchemaVersion' in $configPath`nRun install.cmd from the portable bundle."
      Set-FrameCompareShimExitCode -ExitCode 15
      return
    }
    $schemaVersion = $parsedSchemaVersion
  }
  if ($schemaVersion -ne 1) {
    Write-Error -ErrorAction Continue "Unsupported config schema version '$schemaVersion' in $configPath`nRun install.cmd from the portable bundle."
    Set-FrameCompareShimExitCode -ExitCode 15
    return
  }

  $installType = [string]$config.install_type
  if ($installType -ne "portable_bundle") {
    Write-Error -ErrorAction Continue "Unsupported install_type '$installType' in $configPath"
    Set-FrameCompareShimExitCode -ExitCode 16
    return
  }

  $bundlePath = [string]$config.bundle_path
  if ([string]::IsNullOrWhiteSpace($bundlePath)) {
    Write-Error -ErrorAction Continue "bundle_path is missing in config: $configPath`nRun install.cmd from the portable bundle."
    Set-FrameCompareShimExitCode -ExitCode 12
    return
  }

  if (!(Test-Path -LiteralPath $bundlePath)) {
    Write-Error -ErrorAction Continue "Portable bundle directory not found: $bundlePath`nRun install.cmd from the bundle's current location."
    Set-FrameCompareShimExitCode -ExitCode 13
    return
  }

  $bundleLauncher = Join-Path $bundlePath "frame-compare.ps1"
  if (!(Test-Path -LiteralPath $bundleLauncher)) {
    Write-Error -ErrorAction Continue "Bundle launcher not found: $bundleLauncher`nRebuild or re-extract the portable bundle, then run install.cmd again."
    Set-FrameCompareShimExitCode -ExitCode 14
    return
  }

  $stateConfigToml = Join-Path $stateDir "config.toml"
  $bundleConfigToml = Join-Path (Join-Path $bundlePath "config") "config.toml"
  $defaultConfigToml = ""
  if (Test-Path -LiteralPath $bundleConfigToml) {
    $defaultConfigToml = $bundleConfigToml
  } elseif (Test-Path -LiteralPath $stateConfigToml) {
    $defaultConfigToml = $stateConfigToml
  }

  $forwardArgs = @($ArgsValues | ForEach-Object { [string]$_ })
  if (-not [string]::IsNullOrWhiteSpace($defaultConfigToml)) {
    $hasExplicitConfigFlag = Test-ArgsContainConfigFlag -ArgsValues $forwardArgs
    if (-not $hasExplicitConfigFlag) {
      $injectIndex = Get-ConfigInjectionIndex -ArgsValues $forwardArgs
      if ($injectIndex -ge 0) {
        $forwardArgs = Add-ArgsAtIndex -ArgsValues $forwardArgs -Index $injectIndex -InsertValues @("--config", $defaultConfigToml)
      }
    }
  }

  $exitCode = 0
  $originalPath = Get-FrameCompareShimEnvironmentValue -Name "PATH"
  $originalPythonUtf8 = Get-FrameCompareShimEnvironmentValue -Name "PYTHONUTF8"
  $originalPythonPath = Get-FrameCompareShimEnvironmentValue -Name "PYTHONPATH"
  $originalVsExtraPluginPath = Get-FrameCompareShimEnvironmentValue -Name "VAPOURSYNTH_EXTRA_PLUGIN_PATH"
  $originalVsPluginPath = Get-FrameCompareShimEnvironmentValue -Name "VAPOURSYNTH_PLUGIN_PATH"
  $locationPushed = $false
  try {
    Push-Location $bundlePath
    $locationPushed = $true
    & $bundleLauncher @forwardArgs
    if ($null -ne $LASTEXITCODE) {
      $exitCode = $LASTEXITCODE
    } elseif ($?) {
      $exitCode = 0
    } else {
      $exitCode = 1
    }
  } finally {
    if ($locationPushed) {
      Pop-Location
    }
    Restore-FrameCompareShimEnvironmentValue -Name "PATH" -Value $originalPath
    Restore-FrameCompareShimEnvironmentValue -Name "PYTHONUTF8" -Value $originalPythonUtf8
    Restore-FrameCompareShimEnvironmentValue -Name "PYTHONPATH" -Value $originalPythonPath
    Restore-FrameCompareShimEnvironmentValue -Name "VAPOURSYNTH_EXTRA_PLUGIN_PATH" -Value $originalVsExtraPluginPath
    Restore-FrameCompareShimEnvironmentValue -Name "VAPOURSYNTH_PLUGIN_PATH" -Value $originalVsPluginPath
  }
  Set-FrameCompareShimExitCode -ExitCode $exitCode
}

if ($MyInvocation.InvocationName -ne ".") {
  Invoke-FrameCompareShim -ArgsValues $args
  exit $script:FrameCompareShimExitCode
}
