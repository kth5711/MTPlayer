param(
  [string]$OutputPath = ""
)

$ErrorActionPreference = "Stop"

function New-DirectoryIfMissing {
  param([string]$Path)
  if (-not (Test-Path -LiteralPath $Path)) {
    New-Item -ItemType Directory -Path $Path -Force | Out-Null
  }
}

function Resolve-CommandPath {
  param([string]$Name)
  $cmd = Get-Command $Name -ErrorAction SilentlyContinue
  if ($null -eq $cmd) {
    return $null
  }
  return $cmd.Source
}

function Invoke-ProcessCapture {
  param(
    [string]$FilePath,
    [string[]]$ArgumentList
  )

  try {
    $psi = New-Object System.Diagnostics.ProcessStartInfo
    $psi.FileName = $FilePath
    foreach ($arg in $ArgumentList) {
      [void]$psi.ArgumentList.Add($arg)
    }
    $psi.RedirectStandardOutput = $true
    $psi.RedirectStandardError = $true
    $psi.UseShellExecute = $false
    $psi.CreateNoWindow = $true

    $proc = New-Object System.Diagnostics.Process
    $proc.StartInfo = $psi
    [void]$proc.Start()
    $stdout = $proc.StandardOutput.ReadToEnd()
    $stderr = $proc.StandardError.ReadToEnd()
    $proc.WaitForExit()

    return @{
      ok = $true
      exit_code = $proc.ExitCode
      stdout = $stdout.Trim()
      stderr = $stderr.Trim()
    }
  } catch {
    return @{
      ok = $false
      exit_code = -1
      stdout = ""
      stderr = $_.Exception.Message
    }
  }
}

function Test-PythonImports {
  param(
    [string]$PythonExe,
    [string[]]$Modules
  )

  if (-not $PythonExe) {
    return @{}
  }

  $script = @"
import importlib.util
import json
mods = %MODULES%
out = {}
for name in mods:
    try:
        out[name] = bool(importlib.util.find_spec(name))
    except Exception:
        out[name] = False
print(json.dumps(out))
"@.Replace("%MODULES%", ($Modules | ConvertTo-Json -Compress))

  $result = Invoke-ProcessCapture -FilePath $PythonExe -ArgumentList @("-c", $script)
  if (-not $result.ok -or $result.exit_code -ne 0 -or -not $result.stdout) {
    return @{}
  }
  try {
    return ($result.stdout | ConvertFrom-Json -AsHashtable)
  } catch {
    return @{}
  }
}

function Get-FirstExistingPath {
  param([string[]]$Paths)
  foreach ($p in $Paths) {
    if ($p -and (Test-Path -LiteralPath $p)) {
      return $p
    }
  }
  return $null
}

$scriptRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$projectRoot = Split-Path -Parent $scriptRoot
$outputDir = Join-Path $scriptRoot "output"
New-DirectoryIfMissing -Path $outputDir

if (-not $OutputPath) {
  $OutputPath = Join-Path $outputDir "system_report.json"
}

$pythonCandidates = @()
$cmdPython = Resolve-CommandPath -Name "python"
$cmdPy = Resolve-CommandPath -Name "py"
if ($cmdPython) { $pythonCandidates += $cmdPython }
if ($cmdPy) { $pythonCandidates += $cmdPy }

$condaPath = Resolve-CommandPath -Name "conda"
$wingetPath = Resolve-CommandPath -Name "winget"
$nvidiaSmiPath = Resolve-CommandPath -Name "nvidia-smi"

$ffmpegCandidatePaths = @(
  "C:\ffmpeg\bin\ffmpeg.exe",
  "C:\Program Files\ffmpeg\bin\ffmpeg.exe",
  "C:\ProgramData\chocolatey\bin\ffmpeg.exe",
  "C:\Tools\ffmpeg\bin\ffmpeg.exe"
)
$ffmpegPath = Get-FirstExistingPath -Paths $ffmpegCandidatePaths
if (-not $ffmpegPath) {
  $ffmpegPath = Resolve-CommandPath -Name "ffmpeg"
}

$vlcCandidatePaths = @(
  "C:\Program Files\VideoLAN\VLC\vlc.exe",
  "C:\Program Files (x86)\VideoLAN\VLC\vlc.exe"
)
$vlcPath = Get-FirstExistingPath -Paths $vlcCandidatePaths
if (-not $vlcPath) {
  $vlcPath = Resolve-CommandPath -Name "vlc"
}

$videoControllers = @()
try {
  $videoControllers = @(Get-CimInstance Win32_VideoController | ForEach-Object {
    @{
      name = $_.Name
      driver_version = $_.DriverVersion
      adapter_ram = $_.AdapterRAM
    }
  })
} catch {
  $videoControllers = @()
}

$nvidiaPresent = $false
foreach ($gpu in $videoControllers) {
  if (($gpu.name | Out-String).ToLower().Contains("nvidia")) {
    $nvidiaPresent = $true
    break
  }
}

$pythonForChecks = $cmdPython
if (-not $pythonForChecks -and $cmdPy) {
  $pythonForChecks = $cmdPy
}

$modulesToCheck = @(
  "PyQt6",
  "vlc",
  "cv2",
  "numpy",
  "scenedetect",
  "PIL",
  "torch",
  "transformers",
  "huggingface_hub",
  "safetensors",
  "accelerate"
)

$pythonImports = Test-PythonImports -PythonExe $pythonForChecks -Modules $modulesToCheck

$ffmpegVersion = $null
$ffmpegEncoders = $null
$ffmpegHwaccels = $null
$ffmpegHasLibx264 = $false
$ffmpegHasAac = $false
if ($ffmpegPath) {
  $ffmpegVersion = Invoke-ProcessCapture -FilePath $ffmpegPath -ArgumentList @("-hide_banner", "-version")
  $ffmpegEncoders = Invoke-ProcessCapture -FilePath $ffmpegPath -ArgumentList @("-hide_banner", "-encoders")
  $ffmpegHwaccels = Invoke-ProcessCapture -FilePath $ffmpegPath -ArgumentList @("-hide_banner", "-hwaccels")
  $encoderText = (($ffmpegEncoders.stdout + "`n" + $ffmpegEncoders.stderr) | Out-String)
  $ffmpegHasLibx264 = $encoderText -match "libx264"
  $ffmpegHasAac = $encoderText -match "(^|\s)aac(\s|$)"
}

$torchCuda = @{
  torch_found = $false
  cuda_available = $false
  torch_version = $null
  cuda_version = $null
  device_count = 0
}

if ($pythonForChecks) {
  $torchScript = @"
import json
out = {
  "torch_found": False,
  "cuda_available": False,
  "torch_version": None,
  "cuda_version": None,
  "device_count": 0,
}
try:
    import torch
    out["torch_found"] = True
    out["torch_version"] = getattr(torch, "__version__", None)
    out["cuda_available"] = bool(torch.cuda.is_available())
    out["cuda_version"] = getattr(torch.version, "cuda", None)
    out["device_count"] = int(torch.cuda.device_count()) if out["cuda_available"] else 0
except Exception:
    pass
print(json.dumps(out))
"@
  $torchResult = Invoke-ProcessCapture -FilePath $pythonForChecks -ArgumentList @("-c", $torchScript)
  if ($torchResult.ok -and $torchResult.exit_code -eq 0 -and $torchResult.stdout) {
    try {
      $torchCuda = ($torchResult.stdout | ConvertFrom-Json -AsHashtable)
    } catch {
      $torchCuda = $torchCuda
    }
  }
}

$report = [ordered]@{
  generated_at = (Get-Date).ToString("s")
  project_root = $projectRoot
  script_root = $scriptRoot
  os = @{
    platform = "windows"
    version = [System.Environment]::OSVersion.VersionString
  }
  tools = @{
    conda = @{
      found = [bool]$condaPath
      path = $condaPath
    }
    winget = @{
      found = [bool]$wingetPath
      path = $wingetPath
    }
    python = @{
      found = [bool]$pythonForChecks
      path = $pythonForChecks
      candidates = $pythonCandidates
      imports = $pythonImports
    }
    ffmpeg = @{
      found = [bool]$ffmpegPath
      path = $ffmpegPath
      preferred_candidates = $ffmpegCandidatePaths
      has_libx264 = [bool]$ffmpegHasLibx264
      has_aac = [bool]$ffmpegHasAac
      version = $ffmpegVersion
      hwaccels = $ffmpegHwaccels
    }
    vlc = @{
      found = [bool]$vlcPath
      path = $vlcPath
      preferred_candidates = $vlcCandidatePaths
    }
    nvidia_smi = @{
      found = [bool]$nvidiaSmiPath
      path = $nvidiaSmiPath
      probe = $(if ($nvidiaSmiPath) { Invoke-ProcessCapture -FilePath $nvidiaSmiPath -ArgumentList @("--query-gpu=name,driver_version", "--format=csv,noheader") } else { $null })
    }
  }
  gpu = @{
    nvidia_present = [bool]$nvidiaPresent
    adapters = $videoControllers
    torch = $torchCuda
  }
}

$json = $report | ConvertTo-Json -Depth 8
Set-Content -LiteralPath $OutputPath -Value $json -Encoding UTF8
Write-Host "Wrote system report to $OutputPath"
