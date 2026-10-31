Param(
  [Parameter(Mandatory = $true)][string]$PublicUrl
)

$ErrorActionPreference = "Stop"

if ($PublicUrl.EndsWith("/")) {
  $PublicUrl = $PublicUrl.TrimEnd("/")
}

$repoRoot = Split-Path -Parent $PSScriptRoot
$openapi = Join-Path $repoRoot "fram_serving/openapi-lite.yaml"
if (!(Test-Path -LiteralPath $openapi)) {
  throw "OpenAPI file not found: $openapi"
}

Write-Host "Checking $PublicUrl/health ..."
try {
  $health = Invoke-WebRequest -UseBasicParsing -Uri "$PublicUrl/health" -TimeoutSec 10
}
catch {
  throw "Cannot reach $PublicUrl/health. Is your tunnel running?"
}

if ($health.StatusCode -ne 200) {
  throw "Cannot reach $PublicUrl/health. HTTP $($health.StatusCode)"
}

try {
  $healthJson = $health.Content | ConvertFrom-Json
}
catch {
  throw "Health endpoint did not return JSON payload"
}

if (-not ($healthJson.PSObject.Properties.Name -contains "ok") -or -not [bool]$healthJson.ok) {
  throw "Health endpoint JSON missing ok=true"
}

Copy-Item -LiteralPath $openapi -Destination "$openapi.bak" -Force

$lines = Get-Content -LiteralPath $openapi
$updated = $false
for ($i = 0; $i -lt $lines.Length; $i++) {
  if (-not $updated -and $lines[$i] -match '^\s*-\s*url:\s*') {
    $indent = ($lines[$i] -replace '^(\s*).*', '$1')
    $lines[$i] = "${indent}- url: $PublicUrl"
    $updated = $true
  }
}

if (-not $updated) {
  throw "Could not find servers url entry to update"
}

$utf8NoBom = New-Object System.Text.UTF8Encoding($false)
[System.IO.File]::WriteAllLines($openapi, $lines, $utf8NoBom)

Write-Host ""
Write-Host "Updated $openapi with public URL:"
Write-Host "  $PublicUrl"
Write-Host ""
Write-Host "Next:"
Write-Host "1) In ChatGPT -> Settings -> Connectors -> Developer Mode -> Add connector -> Upload OpenAPI"
Write-Host "2) Select fram_serving/openapi-lite.yaml"
Write-Host "3) When prompted for headers: X-API-Key = dev-key"
Write-Host "4) Use 'fram_query' with text='What does OrthoRoute+ use?' to test."
