param(
  [string]$TaskName = "FRAM Weekly Regression",
  [ValidateSet("Sunday","Monday","Tuesday","Wednesday","Thursday","Friday","Saturday")]
  [string]$Day = "Sunday",
  [string]$Time = "09:00",
  [string]$SessionId = "always-on"
)

$ErrorActionPreference = 'Stop'

$ScriptDir = Split-Path -Path $MyInvocation.MyCommand.Path -Parent
$RepoRoot = Split-Path -Path $ScriptDir -Parent
$LogsDir = Join-Path $RepoRoot "logs"
if (-not (Test-Path $LogsDir)) {
  New-Item -ItemType Directory -Force -Path $LogsDir | Out-Null
}

$Python = Join-Path $RepoRoot ".venv\\Scripts\\python.exe"
if (-not (Test-Path $Python)) {
  try {
    $Python = (Get-Command python -ErrorAction Stop).Source
  } catch {
    throw "Python not found. Install Python or create .venv."
  }
}

$Command = "cd /d `"$RepoRoot`"; `$env:COGMEM_SESSION_ID=`"$SessionId`"; & `"$Python`" tools\\weekly_regression_snapshot.py --digest >> logs\\weekly_regression.log 2>&1; & `"$Python`" tools\\refactor_checklist.py >> logs\\weekly_regression.log 2>&1"
$Action = New-ScheduledTaskAction -Execute "powershell.exe" -Argument "-NoProfile -ExecutionPolicy Bypass -Command `"$Command`""
$Trigger = New-ScheduledTaskTrigger -Weekly -DaysOfWeek $Day -At $Time
$Principal = New-ScheduledTaskPrincipal -UserId $env:USERNAME -LogonType Interactive -RunLevel Limited

Register-ScheduledTask -TaskName $TaskName -Action $Action -Trigger $Trigger -Principal $Principal -Force | Out-Null

Write-Host "Weekly regression task enabled: $TaskName ($Day $Time)"
