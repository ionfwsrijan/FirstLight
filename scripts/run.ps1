$ErrorActionPreference = "Stop"
$root = Split-Path $PSScriptRoot -Parent
Push-Location $root
$port = if ($args.Count -gt 0) { $args[0] } else { "8000" }
Write-Host "== FirstLight on http://localhost:$port ==" -ForegroundColor Cyan
Start-Process py -ArgumentList "-m","firstlight.server",$port -WorkingDirectory $root
Start-Sleep -Seconds 2
Start-Process "http://localhost:$port"
Pop-Location