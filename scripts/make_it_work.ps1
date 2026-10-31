<#
  Safe Windows setup:
  - creates an isolated Python 3.11 environment;
  - installs the project and complete development toolchain;
  - verifies imports and dependency consistency;
  - starts a loopback-only server only when -StartServer is explicit.
#>

[CmdletBinding()]
param(
  [switch]$StartServer,
  [switch]$EnableDevProfile,
  [switch]$EnableAutolog
)

$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Path $PSScriptRoot -Parent
$VenvPython = Join-Path $RepoRoot ".venv\Scripts\python.exe"
Set-Location -LiteralPath $RepoRoot

if (-not (Test-Path -LiteralPath $VenvPython -PathType Leaf)) {
  $PyLauncher = Get-Command py -ErrorAction SilentlyContinue
  if ($PyLauncher) {
    & $PyLauncher.Source -3.11 -m venv .venv
  } else {
    $Python = Get-Command python -ErrorAction Stop
    & $Python.Source -m venv .venv
  }
}

& $VenvPython -m pip install --upgrade pip
& $VenvPython -m pip install -e . -r requirements-dev.txt
& $VenvPython -m pip check
& $VenvPython scripts\verify_imports.py

. (Join-Path $PSScriptRoot "bootstrap_env.ps1") `
  -EnableDevProfile:$EnableDevProfile `
  -EnableAutolog:$EnableAutolog

Write-Host "Setup complete. No memory was hydrated and no server was started implicitly."
if ($StartServer) {
  & (Join-Path $PSScriptRoot "dev_run.ps1") `
    -EnableDevProfile:$EnableDevProfile `
    -EnableAutolog:$EnableAutolog
}
