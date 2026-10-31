$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$pattern = "uvicorn .*fram_serving\.app:app"

$running = Get-CimInstance Win32_Process | Where-Object {
    $_.CommandLine -and $_.CommandLine -match $pattern
}

if ($running) {
    Write-Host "FRAM server already running. No action taken."
    exit 0
}

$autostart = Join-Path $RepoRoot "scripts\\autostart_fram.cmd"
if (-not (Test-Path $autostart)) {
    Write-Error "Could not find autostart target at $autostart"
    exit 1
}

Start-Process -FilePath $autostart -WorkingDirectory $RepoRoot
Write-Host "Started FRAM server via autostart script."
