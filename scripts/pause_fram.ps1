param(
    [switch]$Force
)

$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$pattern = "uvicorn .*fram_serving\.app:app"

$procs = Get-CimInstance Win32_Process | Where-Object {
    $_.CommandLine -and $_.CommandLine -match $pattern
}

if (-not $procs) {
    Write-Host "No FRAM uvicorn process found."
    exit 0
}

foreach ($proc in $procs) {
    try {
        Stop-Process -Id $proc.ProcessId -ErrorAction Stop
        Write-Host ("Stopped FRAM server PID {0}." -f $proc.ProcessId)
    } catch {
        if ($Force.IsPresent) {
            Stop-Process -Id $proc.ProcessId -Force -ErrorAction SilentlyContinue
            Write-Host ("Force-stopped FRAM server PID {0}." -f $proc.ProcessId)
        } else {
            Write-Warning ("Failed to stop PID {0}. Re-run with -Force if needed." -f $proc.ProcessId)
        }
    }
}
