$ErrorActionPreference = "Stop"
$root = Split-Path $PSScriptRoot -Parent
Push-Location $root
try {
    Write-Host "== FirstLight gate ==" -ForegroundColor Cyan
    py -m unittest discover -s tests -v
    if ($LASTEXITCODE -ne 0) { throw "gate failed: $LASTEXITCODE" }
    Write-Host "Gate green." -ForegroundColor Green
} finally {
    Pop-Location
}