param(
  [string]$ManifestPath = "",
  [string]$ReportPath = "",
  [string]$EnvName = "",
  [switch]$PreferGpu,
  [switch]$InstallSceneAnalysis,
  [switch]$InstallSystemDeps,
  [switch]$SkipSystemDeps,
  [switch]$DryRun,
  [switch]$SkipVerify
)

$ErrorActionPreference = "Stop"

function Resolve-JsonFile {
  param(
    [string]$PathValue,
    [string]$DefaultPath
  )
  if ($PathValue) {
    return (Resolve-Path -LiteralPath $PathValue).Path
  }
  return $DefaultPath
}

function Invoke-Step {
  param(
    [string]$Label,
    [string]$FilePath,
    [string[]]$ArgumentList
  )

  $rendered = @($FilePath) + $ArgumentList
  Write-Host "[step] $Label"
  Write-Host ("        " + ($rendered -join " "))
  if ($DryRun) {
    return
  }
  & $FilePath @ArgumentList
  if ($LASTEXITCODE -ne 0) {
    throw "Command failed: $Label (exit code $LASTEXITCODE)"
  }
}

function Invoke-PipInstallIfAny {
  param(
    [string]$Label,
    [string]$Exe,
    [string[]]$PrefixArgs,
    [object[]]$Packages
  )

  $items = @()
  foreach ($pkg in @($Packages)) {
    if ($null -eq $pkg) {
      continue
    }
    $text = [string]$pkg
    if (-not [string]::IsNullOrWhiteSpace($text)) {
      $items += $text
    }
  }
  if ($items.Count -le 0) {
    return
  }

  Invoke-Step -Label $Label -FilePath $Exe -ArgumentList ($PrefixArgs + @("install") + $items)
}

function Test-CondaEnvExists {
  param(
    [string]$CondaExe,
    [string]$Name
  )
  $raw = & $CondaExe env list --json 2>$null
  if ($LASTEXITCODE -ne 0 -or -not $raw) {
    return $false
  }
  try {
    $parsed = $raw | ConvertFrom-Json
    foreach ($envPath in @($parsed.envs)) {
      if ((Split-Path $envPath -Leaf) -eq $Name) {
        return $true
      }
    }
  } catch {
    return $false
  }
  return $false
}

function Resolve-CondaEnvPath {
  param(
    [string]$CondaExe,
    [string]$Name
  )
  $raw = & $CondaExe env list --json 2>$null
  if ($LASTEXITCODE -ne 0 -or -not $raw) {
    return $null
  }
  try {
    $parsed = $raw | ConvertFrom-Json
    foreach ($envPath in @($parsed.envs)) {
      if ((Split-Path $envPath -Leaf) -eq $Name) {
        return [string]$envPath
      }
    }
  } catch {
    return $null
  }
  return $null
}

function Invoke-WingetCandidates {
  param(
    [string]$WingetExe,
    [string[]]$Ids
  )
  foreach ($id in $Ids) {
    Write-Host "[system-dep] trying winget id: $id"
    if ($DryRun) {
      continue
    }
    & $WingetExe install --id $id --exact --accept-package-agreements --accept-source-agreements --silent
    if ($LASTEXITCODE -eq 0) {
      Write-Host "[system-dep] installed via winget: $id"
      return $true
    }
  }
  return $false
}

function Resolve-CommandPath {
  param([string]$Name)
  $cmd = Get-Command $Name -ErrorAction SilentlyContinue
  if ($null -eq $cmd) {
    return $null
  }
  return $cmd.Source
}

function Get-FirstExistingPath {
  param([object[]]$Paths)
  foreach ($value in @($Paths)) {
    $path = [string]$value
    if ($path -and (Test-Path -LiteralPath $path)) {
      return $path
    }
  }
  return $null
}

function Resolve-SystemToolPath {
  param(
    [object[]]$PreferredPaths,
    [string[]]$CommandNames
  )

  $preferred = Get-FirstExistingPath -Paths @($PreferredPaths)
  if ($preferred) {
    return $preferred
  }
  foreach ($name in @($CommandNames)) {
    $resolved = Resolve-CommandPath -Name $name
    if ($resolved) {
      return $resolved
    }
  }
  return $null
}

function Resolve-RequiredSystemTool {
  param(
    [string]$Label,
    [object[]]$PreferredPaths,
    [string[]]$CommandNames,
    [string]$WingetExe,
    [string[]]$WingetIds,
    [bool]$ShouldInstall
  )

  $resolved = Resolve-SystemToolPath -PreferredPaths $PreferredPaths -CommandNames $CommandNames
  if ($resolved) {
    Write-Host "[system-dep] found $Label: $resolved"
    return $resolved
  }

  if ($ShouldInstall -and $WingetExe) {
    [void](Invoke-WingetCandidates -WingetExe $WingetExe -Ids $WingetIds)
    $resolved = Resolve-SystemToolPath -PreferredPaths $PreferredPaths -CommandNames $CommandNames
    if ($resolved) {
      Write-Host "[system-dep] ready $Label: $resolved"
      return $resolved
    }
  }

  $pathList = (@($PreferredPaths) | Where-Object { -not [string]::IsNullOrWhiteSpace([string]$_) }) -join ", "
  if ($DryRun) {
    Write-Warning "$Label not found. Expected one of: $pathList"
    return $null
  }

  if (-not $ShouldInstall) {
    throw "$Label not found because system dependency installation was skipped. Expected one of: $pathList"
  }
  if (-not $WingetExe) {
    throw "$Label not found and winget is unavailable. Install it manually, then rerun. Expected one of: $pathList"
  }
  throw "$Label not found after winget install attempts. Install it manually, then rerun. Expected one of: $pathList"
}

function New-CondaLauncherContent {
  param(
    [string]$CondaExe,
    [string]$EnvName
  )

  return (
    @(
      "@echo off",
      "setlocal",
      "",
      "set ""SCRIPT_DIR=%~dp0""",
      "set ""MAIN_PY=%SCRIPT_DIR%main.py""",
      "set ""CONDA_EXE=$CondaExe""",
      "set ""ENV_NAME=$EnvName""",
      "",
      "if not exist ""%MAIN_PY%"" (",
      "  echo main.py not found:",
      "  echo   %MAIN_PY%",
      "  pause",
      "  exit /b 1",
      ")",
      "",
      "pushd ""%SCRIPT_DIR%""",
      "if errorlevel 1 (",
      "  echo Failed to enter project directory:",
      "  echo   %SCRIPT_DIR%",
      "  pause",
      "  exit /b 1",
      ")",
      "",
      "if exist ""%CONDA_EXE%"" (",
      "  call ""%CONDA_EXE%"" run -n ""%ENV_NAME%"" python ""%MAIN_PY%""",
      ") else (",
      "  echo Conda executable not found:",
      "  echo   %CONDA_EXE%",
      "  echo.",
      "  echo Falling back to PATH lookup for conda...",
      "  conda run -n ""%ENV_NAME%"" python ""%MAIN_PY%""",
      ")",
      "set ""EXIT_CODE=%ERRORLEVEL%""",
      "popd",
      "",
      "if not ""%EXIT_CODE%""==""0"" (",
      "  echo.",
      "  echo Multi-Play exited with code %EXIT_CODE%.",
      "  pause",
      ")",
      "",
      "exit /b %EXIT_CODE%"
    ) -join "`r`n"
  )
}

function New-PythonLauncherContent {
  param([string]$PythonExe)

  return (
    @(
      "@echo off",
      "setlocal",
      "",
      "set ""SCRIPT_DIR=%~dp0""",
      "set ""MAIN_PY=%SCRIPT_DIR%main.py""",
      "set ""PYTHON_EXE=$PythonExe""",
      "set ""ENV_DIR=""""",
      "set ""CONDA_ROOT=""""",
      "set ""CONDA_BAT=""""",
      "",
      "if not exist ""%MAIN_PY%"" (",
      "  echo main.py not found:",
      "  echo   %MAIN_PY%",
      "  pause",
      "  exit /b 1",
      ")",
      "",
      "if not exist ""%PYTHON_EXE%"" (",
      "  echo Python executable not found:",
      "  echo   %PYTHON_EXE%",
      "  pause",
      "  exit /b 1",
      ")",
      "",
      "for %%I in (""%PYTHON_EXE%"") do set ""ENV_DIR=%%~dpI""",
      "for %%I in (""%ENV_DIR%."") do set ""ENV_DIR=%%~fI""",
      "for %%I in (""%ENV_DIR%\..\.."") do set ""CONDA_ROOT=%%~fI""",
      "set ""CONDA_BAT=%CONDA_ROOT%\condabin\conda.bat""",
      "",
      "pushd ""%SCRIPT_DIR%""",
      "if errorlevel 1 (",
      "  echo Failed to enter project directory:",
      "  echo   %SCRIPT_DIR%",
      "  pause",
      "  exit /b 1",
      ")",
      "",
      "if exist ""%CONDA_BAT%"" (",
      "  call ""%CONDA_BAT%"" activate ""%ENV_DIR%""",
      "  if errorlevel 1 (",
      "    popd",
      "    echo Failed to activate conda environment:",
      "    echo   %ENV_DIR%",
      "    echo Using:",
      "    echo   %CONDA_BAT%",
      "    pause",
      "    exit /b 1",
      "  )",
      "  ""%PYTHON_EXE%"" ""%MAIN_PY%""",
      ") else (",
      "  ""%PYTHON_EXE%"" ""%MAIN_PY%""",
      ")",
      "",
      "set ""EXIT_CODE=%ERRORLEVEL%""",
      "popd",
      "",
      "if not defined EXIT_CODE (",
      "  set ""EXIT_CODE=1""",
      ")",
      "",
      "exit /b %EXIT_CODE%"
    ) -join "`r`n"
  )
}

$scriptRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$projectRoot = Split-Path -Parent $scriptRoot
$outputDir = Join-Path $scriptRoot "output"
if (-not (Test-Path -LiteralPath $outputDir)) {
  New-Item -ItemType Directory -Path $outputDir -Force | Out-Null
}

$ManifestPath = Resolve-JsonFile -PathValue $ManifestPath -DefaultPath (Join-Path $scriptRoot "install_manifest.json")
$ReportPath = Resolve-JsonFile -PathValue $ReportPath -DefaultPath (Join-Path $outputDir "system_report.json")

if (-not (Test-Path -LiteralPath $ManifestPath)) {
  throw "Manifest not found: $ManifestPath"
}
if (-not (Test-Path -LiteralPath $ReportPath)) {
  throw "System report not found: $ReportPath"
}

$manifest = Get-Content -LiteralPath $ManifestPath -Raw | ConvertFrom-Json -AsHashtable
$report = Get-Content -LiteralPath $ReportPath -Raw | ConvertFrom-Json -AsHashtable

if (-not $EnvName) {
  $EnvName = [string]$manifest.recommended_env_name
}

$condaExe = [string]$report.tools.conda.path
$pythonExe = [string]$report.tools.python.path
$wingetExe = [string]$report.tools.winget.path

$useConda = [bool]$condaExe
$preferGpuInstall = [bool]$PreferGpu
if (-not $PreferGpu.IsPresent) {
  $preferGpuInstall = [bool]$report.gpu.nvidia_present
}

$shouldInstallSystemDeps = $true
if ($PSBoundParameters.ContainsKey("InstallSystemDeps")) {
  $shouldInstallSystemDeps = [bool]$InstallSystemDeps
}
if ($SkipSystemDeps) {
  $shouldInstallSystemDeps = $false
}

$ffmpegPath = Resolve-RequiredSystemTool -Label "FFmpeg" `
  -PreferredPaths @($manifest.ffmpeg_policy.preferred_paths) `
  -CommandNames @("ffmpeg", "ffmpeg.exe") `
  -WingetExe $wingetExe `
  -WingetIds @($manifest.ffmpeg_policy.winget_ids) `
  -ShouldInstall $shouldInstallSystemDeps

$vlcRequired = [bool]$manifest.vlc_policy.required
$vlcPath = $null
if ($vlcRequired) {
  $vlcPath = Resolve-RequiredSystemTool -Label "VLC" `
    -PreferredPaths @($manifest.vlc_policy.common_paths) `
    -CommandNames @("vlc", "vlc.exe") `
    -WingetExe $wingetExe `
    -WingetIds @($manifest.vlc_policy.winget_ids) `
    -ShouldInstall $shouldInstallSystemDeps
}

if ($useConda) {
  if (-not (Test-CondaEnvExists -CondaExe $condaExe -Name $EnvName)) {
    Invoke-Step -Label "Create conda env" -FilePath $condaExe -ArgumentList @(
      "create", "-y", "-n", $EnvName, ("python=" + [string]$manifest.python.version)
    )
  }
  $pythonRun = @($condaExe, "run", "-n", $EnvName, "python")
  $pipRun = @($condaExe, "run", "-n", $EnvName, "python", "-m", "pip")
} elseif ($pythonExe) {
  $pythonRun = @($pythonExe)
  $pipRun = @($pythonExe, "-m", "pip")
} else {
  throw "No usable Python or Conda installation found."
}

$launcherPythonExe = $pythonExe
if ($useConda) {
  $condaEnvPath = Resolve-CondaEnvPath -CondaExe $condaExe -Name $EnvName
  if (-not $condaEnvPath) {
    throw "Unable to resolve conda environment path for launcher: $EnvName"
  }
  $launcherPythonExe = Join-Path $condaEnvPath "python.exe"
}

Invoke-Step -Label "Upgrade pip tooling" -FilePath $pipRun[0] -ArgumentList (@($pipRun[1..($pipRun.Length - 1)]) + @(
  "install", "--upgrade", "pip", "setuptools", "wheel"
))

$pipPrefix = @($pipRun[1..($pipRun.Length - 1)])

Invoke-PipInstallIfAny -Label "Install core Python packages" -Exe $pipRun[0] -PrefixArgs $pipPrefix -Packages @($manifest.pip_packages_core)

if ($InstallSceneAnalysis) {
  Invoke-PipInstallIfAny -Label "Install scene analysis core packages" -Exe $pipRun[0] -PrefixArgs $pipPrefix -Packages @($manifest.pip_packages_scene_analysis_core)

  if ($preferGpuInstall) {
    Invoke-Step -Label "Install scene analysis torch GPU packages" -FilePath $pipRun[0] -ArgumentList ($pipPrefix + @(
      "install"
    ) + @($manifest.torch.packages) + @("--index-url", [string]$manifest.torch.gpu_index_url))
  } else {
    Invoke-Step -Label "Install scene analysis torch CPU packages" -FilePath $pipRun[0] -ArgumentList ($pipPrefix + @(
      "install"
    ) + @($manifest.torch.packages) + @("--index-url", [string]$manifest.torch.cpu_index_url))
  }

  Invoke-PipInstallIfAny -Label "Install scene analysis AI common packages" -Exe $pipRun[0] -PrefixArgs $pipPrefix -Packages @($manifest.pip_packages_scene_analysis_ai_common)
  Invoke-PipInstallIfAny -Label "Install scene analysis AI optional packages" -Exe $pipRun[0] -PrefixArgs $pipPrefix -Packages @($manifest.pip_packages_scene_analysis_ai_optional)
} else {
  Write-Host "[step] Skip optional scene analysis pack"
}

$launcherPath = Join-Path $projectRoot "run_multi_play_local.bat"
$launcherContent = New-PythonLauncherContent -PythonExe $launcherPythonExe
if (-not $DryRun) {
  Set-Content -LiteralPath $launcherPath -Value $launcherContent -Encoding ASCII
} else {
  Write-Host "[step] Would write launcher: $launcherPath"
}

$verifyJson = Join-Path $outputDir "post_install_report.json"
if (-not $SkipVerify) {
  Invoke-Step -Label "Run post-install verification" -FilePath $pythonRun[0] -ArgumentList (@($pythonRun[1..($pythonRun.Length - 1)]) + @(
    (Join-Path $scriptRoot "post_install_check.py"),
    "--json-out",
    $verifyJson
  ))
}

Write-Host ""
Write-Host "Install flow completed."
Write-Host "Project root: $projectRoot"
Write-Host "Launcher: $launcherPath"
if (-not $SkipVerify) {
  Write-Host "Verification report: $verifyJson"
}
