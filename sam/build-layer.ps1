# Builds the FirstLightCoreLayer content via the cross-platform Python builder.
# Run from the repo root:
#
#   powershell -File sam/build-layer.ps1
#
# Kept as a thin wrapper so existing docs/CI on Windows keep working; the real
# logic lives in sam/build_layer.py so Linux/macOS/CI build the same layer.
param([string]$LayerDir = "sam/build-layer")

$repo = Split-Path $PSScriptRoot
$env:FIRSTLIGHT_LAYER_DIR = $LayerDir
py (Join-Path $repo "sam\build_layer.py")
if ($LASTEXITCODE -ne 0) { throw "layer build failed: $LASTEXITCODE" }
