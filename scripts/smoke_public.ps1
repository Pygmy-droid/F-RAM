Param(
  [Parameter(Mandatory = $true)][string]$PublicUrl
)

$ErrorActionPreference = "Stop"

if ($PublicUrl.EndsWith("/")) {
  $PublicUrl = $PublicUrl.TrimEnd("/")
}

Write-Host "POST $PublicUrl/mcp/fram_query"
$body = '{"text":"What does OrthoRoute+ use?"}'
$resp = Invoke-WebRequest -UseBasicParsing -Uri "$PublicUrl/mcp/fram_query" -Method POST -ContentType "application/json" -Headers @{"X-API-Key"="dev-key"} -Body $body
$resp.Content
