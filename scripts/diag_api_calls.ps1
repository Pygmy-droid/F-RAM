Param(
  [string]$BaseUrl = "http://127.0.0.1:8000"
)

$ErrorActionPreference = 'Stop'

# Ensure local import path (for any local scripts)
$env:PYTHONPATH = (Get-Location).Path

function Write-Json($label, $obj) {
  $j = $obj | ConvertTo-Json -Depth 6 -Compress
  Write-Output ("[$label] " + $j)
}

# 1) Create session
$create = Invoke-RestMethod -Method Post -Uri "$BaseUrl/memory" -ContentType 'application/json' -Body '{}' 
$sessionId = $create.session.id
Write-Json 'POST /memory' $create

# 2) Append note to session
$appendBody = @{ text = 'hello from diag'; metadata = @{ source = 'diag' } } | ConvertTo-Json -Compress
$append = Invoke-RestMethod -Method Post -Uri "$BaseUrl/memory/$sessionId" -ContentType 'application/json' -Body $appendBody
Write-Json 'POST /memory/{session_id}' $append

# 3) Search memory
$search = Invoke-RestMethod -Method Get -Uri "$BaseUrl/memory/search?query=hello"
Write-Json 'GET /memory/search' $search

# 4) Append a belief
$beliefBody = @{ text = 'belief: FRAM memory works'; metadata = @{ source = 'diag' } } | ConvertTo-Json -Compress
$belief = Invoke-RestMethod -Method Post -Uri "$BaseUrl/memory/belief" -ContentType 'application/json' -Body $beliefBody
Write-Json 'POST /memory/belief' $belief

# 5) Query orchestrator (lightweight)
$queryBody = @{ text = 'What is FRAM?' } | ConvertTo-Json -Compress
$query = Invoke-RestMethod -Method Post -Uri "$BaseUrl/query" -ContentType 'application/json' -Body $queryBody
Write-Json 'POST /query' $query

