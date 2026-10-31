# Daily rebuild of the Workbook pages and the Cosmic Cathedral map.
#
# What it does, in order:
#   1. workbook sync   : attach new commits to the cards they name, re-render
#                        WORKBOOK.md and STATUS.md, strict check of the chain.
#   2. build the map   : project files and cards into cosmic-cathedral-map.json.
#   3. commit          : only the workbook pages, the event chain, and the map,
#                        and only if something changed. Nothing else is staged.
#
# Registered as the Windows scheduled task "FRAM Cathedral Daily" (06:00), run
# through cmd.exe so stdout/stderr land in %LOCALAPPDATA%\FRAM\cathedral_daily.stdout.log
# even when this script cannot reach its own log.
# Run by hand any time:
#   powershell -NoProfile -ExecutionPolicy Bypass -File tools\cathedral_daily.ps1
# Remove the task:
#   schtasks /Delete /TN "FRAM Cathedral Daily" /F
#
# Log: %LOCALAPPDATA%\FRAM\cathedral_daily.log

$ErrorActionPreference = "Stop"
# Scheduled tasks sometimes start with a thin PATH; make sure git is reachable.
if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
  foreach ($g in @("C:\Program Files\Git\cmd", "C:\Program Files (x86)\Git\cmd")) {
    if (Test-Path (Join-Path $g "git.exe")) { $env:Path = "$g;$env:Path"; break }
  }
}
$repo = Split-Path -Parent $PSScriptRoot
$py = Join-Path $repo ".venv\Scripts\python.exe"
$logDir = Join-Path $env:LOCALAPPDATA "FRAM"
$log = Join-Path $logDir "cathedral_daily.log"
New-Item -ItemType Directory -Force -Path $logDir | Out-Null

function Log([string]$line) {
  $stamp = (Get-Date).ToUniversalTime().ToString("yyyy-MM-ddTHH:mm:ssZ")
  # Windows PowerShell 5 (what the scheduled task runs) has no -Encoding on
  # Tee-Object; that one parameter silently killed the 06:00 run on 2026-10-30.
  Write-Output "$stamp  $line"
  Add-Content -Path $log -Value "$stamp  $line" -Encoding utf8
}

# Any terminating error from here on is written to the log before exit 1,
# so a failed task is never silent (06:00 on 2026-10-30 was).
trap { Log "FAIL   $($_.Exception.Message) at line $($_.InvocationInfo.ScriptLineNumber)"; exit 1 }
Set-Location $repo
Log "start  repo=$repo branch=$(git branch --show-current) user=$env:USERNAME"

& $py tools/workbook.py sync 2>&1 | ForEach-Object { Log "sync   $_" }
if ($LASTEXITCODE -ne 0) { Log "FAIL   workbook sync returned $LASTEXITCODE; not committing"; exit 1 }

& $py tools/build_cosmic_cathedral.py 2>&1 | ForEach-Object { Log "map    $_" }
if ($LASTEXITCODE -ne 0) { Log "FAIL   map build returned $LASTEXITCODE; not committing"; exit 1 }

git add -- workbook/EVENTS.jsonl workbook/WORKBOOK.md workbook/STATUS.md experiments/cosmic_cathedral/cosmic-cathedral-map.json
git diff --cached --quiet
if ($LASTEXITCODE -eq 0) {
  Log "done   nothing changed; no commit"
  exit 0
}

$day = (Get-Date).ToString("yyyy-MM-dd")
git -c user.name="Cathedral daily rebuild" -c user.email="cathedral-daily@local" commit -q -m "cathedral: daily rebuild $day (autolog, pages, map)"
if ($LASTEXITCODE -ne 0) { Log "FAIL   commit returned $LASTEXITCODE"; exit 1 }
Log "done   committed $(git rev-parse --short HEAD)"
exit 0
