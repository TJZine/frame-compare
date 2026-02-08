@echo off
setlocal
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0install-from-source.ps1" %*
exit /b %ERRORLEVEL%
