@echo off
REM One-click memory log (Windows). Prompts for texts and appends to cognitive memory.
setlocal
powershell -ExecutionPolicy Bypass -NoProfile -File "%~dp0log_turn.ps1"
endlocal
