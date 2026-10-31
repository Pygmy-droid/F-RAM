[CmdletBinding()]
param(
  [string]$StorageRoot,
  [switch]$EnableDevProfile,
  [switch]$EnableAutolog
)

# Dot-source this script when the variables must remain in the current shell.
$RepoRoot = Split-Path -Path $PSScriptRoot -Parent

if (-not $StorageRoot) {
  if ($env:FRAM_STORAGE_ROOT) {
    $StorageRoot = $env:FRAM_STORAGE_ROOT
  } elseif ($env:USERPROFILE) {
    # Packaged desktop processes can virtualize LOCALAPPDATA while an ordinary
    # VS Code/PowerShell process does not. A profile-relative non-known folder
    # resolves to the same physical runtime from both launch surfaces.
    $StorageRoot = Join-Path $env:USERPROFILE ".fram\runtimes\fram_v22_starter\storage"
  } else {
    $StorageRoot = Join-Path $RepoRoot ".runtime\storage"
  }
}

$env:FRAM_STORAGE_ROOT = [IO.Path]::GetFullPath($StorageRoot)
$env:FRAM_DEV_PROFILE = if ($EnableDevProfile) { "1" } else { "0" }
$env:COGMEM_AUTOLOG = if ($EnableAutolog) { "1" } else { "0" }
if (-not $env:COGMEM_SESSION_ID) {
  $env:COGMEM_SESSION_ID = "dev"
}
if (-not $env:ALLOWED_ORIGINS) {
  $env:ALLOWED_ORIGINS = "http://127.0.0.1:8000"
}

Write-Host "F-RAM environment prepared."
Write-Host "  Storage: $env:FRAM_STORAGE_ROOT"
Write-Host "  Dev profile: $env:FRAM_DEV_PROFILE"
Write-Host "  Cognitive autolog: $env:COGMEM_AUTOLOG"
