@echo off
setlocal
set "SHIM_DIR=%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -File "%SHIM_DIR%frame-compare-update.ps1" %*
exit /b %ERRORLEVEL%
