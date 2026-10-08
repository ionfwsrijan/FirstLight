# Builds the FirstLightCoreLayer content: the pure-Python firstlight package
# copied into the SAM layer layout (python/firstlight) so every handler can
# import it. Run from the repo root:
#
#   powershell -File sam/build-layer.ps1
#
# The layer is what makes the Ship It verdict byte-for-byte identical to the
# Build It verdict: same engine, same DSL, same ledger canons.
param([string]$LayerDir = "sam/build-layer")

$package = "firstlight"
$repo = Split-Path $PSScriptRoot
$dest = Join-Path $repo "$LayerDir\python\$package"
$src = Join-Path $repo "$package\$package"

if (Test-Path -LiteralPath $dest) { Remove-Item -LiteralPath $dest -Recurse -Force }
New-Item -ItemType Directory -Path $dest -Force | Out-Null
Copy-Item -LiteralPath "$src\*" -Destination $dest -Recurse -Force
Write-Output "Built $dest"