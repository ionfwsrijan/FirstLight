$ErrorActionPreference = "Stop"
$root = Split-Path $PSScriptRoot -Parent
Push-Location $root
try {
    Write-Host "== FirstLight gate (full suite) ==" -ForegroundColor Cyan
    py -m firstlight.cli gate
    if ($LASTEXITCODE -ne 0) { throw "gate failed: $LASTEXITCODE" }
    Write-Host "Gate green." -ForegroundColor Green
} finally {
    Pop-Location
}