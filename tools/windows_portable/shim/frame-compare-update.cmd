@echo off
setlocal
set "SHIM_DIR=%~dp0"
set "POWERSHELL_EXE="
where pwsh >nul 2>nul
if %ERRORLEVEL% EQU 0 (
  set "POWERSHELL_EXE=pwsh"
)
if not defined POWERSHELL_EXE if exist "%ProgramFiles%\PowerShell\7\pwsh.exe" set "POWERSHELL_EXE=%ProgramFiles%\PowerShell\7\pwsh.exe"
if not defined POWERSHELL_EXE if exist "%SystemRoot%\System32\WindowsPowerShell\v1.0\powershell.exe" set "POWERSHELL_EXE=%SystemRoot%\System32\WindowsPowerShell\v1.0\powershell.exe"
if not defined POWERSHELL_EXE (
  echo PowerShell was not found. Install PowerShell 7 or restore Windows PowerShell. 1>&2
  exit /b 9009
)
"%POWERSHELL_EXE%" -NoProfile -ExecutionPolicy Bypass -File "%SHIM_DIR%frame-compare-update.ps1" %*
exit /b %ERRORLEVEL%
