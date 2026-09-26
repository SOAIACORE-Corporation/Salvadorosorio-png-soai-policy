@echo off
setlocal
set SCRIPT_DIR=%~dp0
powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%SCRIPT_DIR%Invoke-SOAIntelligenceBootstrapPreflight.ps1" %*
exit /b %ERRORLEVEL%
