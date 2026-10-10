"""Build the FirstLightCoreLayer content, cross-platform (no PowerShell needed).

The layer is the pure-Python ``firstlight`` package copied into the SAM layer
layout (``sam/build-layer/python/firstlight``) so every Lambda handler can
import it. This is what makes the Ship It verdict byte-for-byte identical to
the Build It verdict: same engine, same DSL, same ledger canons.

It also refreshes ``sam/static/index.html`` from ``web/index.html`` so the
served console can never drift from the local console (single source of truth).

Usage:
    python sam/build_layer.py            # build the layer + refresh the console
    python sam/build_layer.py --check    # verify the committed copy is current (CI)
"""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

SAM = Path(__file__).resolve().parent
REPO = SAM.parent
LAYER_ROOT = SAM / "build-layer"
LAYER_PKG = LAYER_ROOT / "python" / "firstlight"
CONSOLE_SRC = REPO / "web" / "index.html"
CONSOLE_DST = SAM / "static" / "index.html"


def build() -> None:
    if LAYER_ROOT.exists():
        shutil.rmtree(LAYER_ROOT)
    shutil.copytree(
        REPO / "firstlight",
        LAYER_PKG,
        ignore=shutil.ignore_patterns("__pycache__", "*.pyc", "*.pyo"),
    )
    CONSOLE_DST.write_bytes(CONSOLE_SRC.read_bytes())
    modules = sum(1 for _ in LAYER_PKG.rglob("*.py"))
    print(f"layer   -> {LAYER_PKG}  ({modules} modules)")
    print(f"console -> {CONSOLE_DST}  (from web/index.html)")


def check() -> int:
    if not CONSOLE_DST.exists():
        print("console drift: sam/static/index.html is missing", file=sys.stderr)
        return 1
    if CONSOLE_SRC.read_bytes() != CONSOLE_DST.read_bytes():
        print(
            "console drift: web/index.html and sam/static/index.html differ — "
            "run `python sam/build_layer.py` and commit the result.",
            file=sys.stderr,
        )
        return 1
    print("console in sync: web/index.html == sam/static/index.html")
    return 0


def main(argv: list[str]) -> int:
    if "--check" in argv:
        return check()
    build()
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
