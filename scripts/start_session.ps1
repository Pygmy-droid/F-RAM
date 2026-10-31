# Start-session helper: primes env + hydrates cognitive memory.
# Run in the same PowerShell session where you want env vars applied.

param(
    [int]$Window = 5,
    [switch]$Warmup,
    [switch]$Summary,
    [switch]$RecentDocs,
    [string]$SessionId
)

. "$PSScriptRoot\bootstrap_env.ps1"

if ($SessionId) {
    $env:COGMEM_SESSION_ID = $SessionId
} elseif (-not $env:COGMEM_SESSION_ID -or $env:COGMEM_SESSION_ID -eq "dev") {
    $env:COGMEM_SESSION_ID = (Get-Date -Format "yyyyMMdd-HHmmss")
}

python tools/bootstrap_memory.py --window $Window

if ($Warmup) {
    python tools/session_warmup.py --json
}

if ($Summary) {
    python tools/cognitive_memory_summary.py
}

if ($RecentDocs) {
    python tools/list_recent_docs.py --hours 48 --limit 25
}

Write-Host "Session ready: COGMEM_AUTOLOG=$env:COGMEM_AUTOLOG (session=$env:COGMEM_SESSION_ID)"
