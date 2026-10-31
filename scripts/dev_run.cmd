@echo off
REM One-click dev run (Windows). Opens a PowerShell that sets env and runs the server.
setlocal
powershell -ExecutionPolicy Bypass -NoProfile -File "%~dp0dev_run.ps1"
endlocal
