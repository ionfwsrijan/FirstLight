$ErrorActionPreference = "Stop"
$root = Split-Path $PSScriptRoot -Parent
Push-Location $root
try {
    Write-Host "== FirstLight server ==" -ForegroundColor Cyan
    py -m firstlight.cli serve
} finally {
    Pop-Location
}