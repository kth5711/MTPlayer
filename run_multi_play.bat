@echo off
setlocal

set "SCRIPT_DIR=%~dp0"
set "MAIN_PY=%SCRIPT_DIR%app\main.py"
set "VBS_LAUNCHER=%SCRIPT_DIR%run_multi_play.vbs"
set "LOCAL_LAUNCHER=%SCRIPT_DIR%run_multi_play_local.bat"
set "ENV_PYTHON=%SCRIPT_DIR%..\python.exe"
set "ENV_PYTHONW=%SCRIPT_DIR%..\pythonw.exe"

if not exist "%MAIN_PY%" (
  echo app\main.py not found:
  echo   %MAIN_PY%
  pause
  exit /b 1
)

if exist "%VBS_LAUNCHER%" (
  wscript //nologo "%VBS_LAUNCHER%"
  exit /b %ERRORLEVEL%
)

if exist "%LOCAL_LAUNCHER%" (
  call "%LOCAL_LAUNCHER%"
  exit /b %ERRORLEVEL%
)

pushd "%SCRIPT_DIR%"
if errorlevel 1 (
  echo Failed to enter project directory:
  echo   %SCRIPT_DIR%
  pause
  exit /b 1
)

if exist "%ENV_PYTHONW%" (
  start "" "%ENV_PYTHONW%" "%MAIN_PY%"
  popd
  exit /b 0
)

if exist "%ENV_PYTHON%" (
  "%ENV_PYTHON%" "%MAIN_PY%"
  set "EXIT_CODE=%ERRORLEVEL%"
  popd
  if not defined EXIT_CODE (
    set "EXIT_CODE=1"
  )
  exit /b %EXIT_CODE%
)

where pythonw >nul 2>nul
if not errorlevel 1 (
  start "" pythonw "%MAIN_PY%"
  popd
  exit /b 0
)

where python >nul 2>nul
if errorlevel 1 (
  popd
  echo No launcher or Python executable was found.
  echo Run install\install_windows.ps1 first, or create run_multi_play_local.bat.
  pause
  exit /b 1
)

python "%MAIN_PY%"
set "EXIT_CODE=%ERRORLEVEL%"
popd

if not defined EXIT_CODE (
  set "EXIT_CODE=1"
)

exit /b %EXIT_CODE%
