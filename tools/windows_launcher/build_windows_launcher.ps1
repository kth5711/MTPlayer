param(
  [string]$ProjectRoot = (Split-Path -Parent (Split-Path -Parent $PSScriptRoot)),
  [string]$OutputExe = "MultiPlay.exe",
  [string]$IconPath = ""
)

$ErrorActionPreference = "Stop"

$sourcePath = Join-Path $PSScriptRoot "MultiPlayLauncher.cs"
$outputPath = Join-Path $ProjectRoot $OutputExe
$defaultIconPath = Join-Path $PSScriptRoot "MultiPlay.ico"

if (-not (Test-Path -LiteralPath $sourcePath)) {
  throw "Launcher source not found: $sourcePath"
}

if (-not $IconPath -and (Test-Path -LiteralPath $defaultIconPath)) {
  $IconPath = $defaultIconPath
}

Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName Microsoft.CSharp

$provider = New-Object Microsoft.CSharp.CSharpCodeProvider
$compilerParameters = New-Object System.CodeDom.Compiler.CompilerParameters
$compilerParameters.GenerateExecutable = $true
$compilerParameters.OutputAssembly = $outputPath
$compilerParameters.GenerateInMemory = $false
$compilerParameters.IncludeDebugInformation = $false
$compilerParameters.TreatWarningsAsErrors = $false
$compilerParameters.CompilerOptions = "/target:winexe /optimize+"

if ($IconPath -and (Test-Path -LiteralPath $IconPath)) {
  $resolvedIcon = (Resolve-Path -LiteralPath $IconPath).Path
  $compilerParameters.CompilerOptions += " /win32icon:`"$resolvedIcon`""
}

[void]$compilerParameters.ReferencedAssemblies.Add("System.dll")
[void]$compilerParameters.ReferencedAssemblies.Add("System.Windows.Forms.dll")

$sourceCode = Get-Content -LiteralPath $sourcePath -Raw
$compileResult = $provider.CompileAssemblyFromSource($compilerParameters, $sourceCode)

if ($compileResult.Errors.Count -gt 0) {
  $messages = @()
  foreach ($compileError in $compileResult.Errors) {
    if (-not $compileError.IsWarning) {
      $messages += $compileError.ToString()
    }
  }
  if ($messages.Count -gt 0) {
    throw ("Launcher build failed:`n" + ($messages -join "`n"))
  }
}

Write-Host "Built launcher: $outputPath"
