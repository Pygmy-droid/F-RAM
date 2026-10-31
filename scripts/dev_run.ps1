[CmdletBinding()]
param(
  [string]$BindHost = "127.0.0.1",
  [ValidateRange(1, 65535)]
  [int]$Port = 8000,
  [switch]$EnableDevProfile,
  [switch]$EnableAutolog,
  [switch]$NoReload
)

$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Path $PSScriptRoot -Parent
$VenvPython = Join-Path $RepoRoot ".venv\Scripts\python.exe"
if (-not (Test-Path -LiteralPath $VenvPython -PathType Leaf)) {
  throw "Missing .venv. Run scripts\make_it_work.ps1 first."
}

. (Join-Path $PSScriptRoot "bootstrap_env.ps1") `
  -EnableDevProfile:$EnableDevProfile `
  -EnableAutolog:$EnableAutolog

$LoopbackHosts = @("127.0.0.1", "localhost", "::1")
if ($BindHost -notin $LoopbackHosts) {
  if (-not $env:MCP_BEARER -or $env:MCP_BEARER.Length -lt 32) {
    throw "Non-loopback binding requires an explicit MCP_BEARER of at least 32 characters."
  }
}
if ($env:MCP_BEARER -eq "change-me") {
  throw "Refusing the insecure placeholder MCP_BEARER value."
}

Set-Location -LiteralPath $RepoRoot
$UvicornArgs = @(
  "-m", "uvicorn", "fram_serving.app:app",
  "--host", $BindHost,
  "--port", $Port
)
if (-not $NoReload) {
  $UvicornArgs += "--reload"
}

& $VenvPython @UvicornArgs
