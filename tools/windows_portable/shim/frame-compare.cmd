@echo off
setlocal
set "SHIM_DIR=%~dp0"
where pwsh >nul 2>nul
if %ERRORLEVEL% EQU 0 (
  pwsh -NoProfile -ExecutionPolicy Bypass -File "%SHIM_DIR%frame-compare.ps1" %*
) else (
  powershell -NoProfile -ExecutionPolicy Bypass -File "%SHIM_DIR%frame-compare.ps1" %*
)
exit /b %ERRORLEVEL%
