param(
  [string]$TaskName = "FRAM Weekly Regression"
)

$ErrorActionPreference = 'Stop'

$Task = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
if (-not $Task) {
  Write-Host "Weekly regression task not found: $TaskName"
  return
}

Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
Write-Host "Weekly regression task disabled: $TaskName"
