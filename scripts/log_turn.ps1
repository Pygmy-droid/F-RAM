param()

# Simple helper to append a turn to cognitive memory using tools/autolog_once.py
# No coding required. It will default to session "dev" and enable autolog.

$ErrorActionPreference = 'Stop'

# Resolve repo root and preferred Python
$ScriptDir = Split-Path -Path $MyInvocation.MyCommand.Path -Parent
$RepoRoot = Split-Path -Path $ScriptDir -Parent
$VenvPython = Join-Path $RepoRoot ".venv/Scripts/python.exe"
if (Test-Path $VenvPython) {
  $Python = $VenvPython
} else {
  $Python = "python"
}

$AutologOnce = Join-Path $RepoRoot "tools/autolog_once.py"

# Inputs
$session = Read-Host "Session ID (default: dev)"
if ([string]::IsNullOrWhiteSpace($session)) { $session = "dev" }
$user = Read-Host "User text"
$assistant = Read-Host "Assistant text (optional; Enter to skip)"

# Env setup for one-shot logging
if (-not $env:COGMEM_AUTOLOG) { $env:COGMEM_AUTOLOG = "1" }
$env:COGMEM_SESSION_ID = $session
$env:COGMEM_USER_TMP = $user
$env:COGMEM_ASSISTANT_TMP = $assistant

& $Python $AutologOnce
if ($LASTEXITCODE -ne 0) {
  Write-Error "Failed to log turn (exit $LASTEXITCODE)."
  exit $LASTEXITCODE
}
Write-Host "Saved to cognitive memory (session '$session')."

