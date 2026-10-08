"""CLI entrypoints: `python -m firstlight.cli`.
Use it to seed, run, or gate the project.
"""

from __future__ import annotations


def main() -> None:
    import sys

    argv = sys.argv[1:]
    cmd = argv[0] if argv else "serve"
    if cmd == "seed":
        from .seed import main as seed_main

        seed_main(argv[1:])
    elif cmd == "serve":
        from ..api.server import main as serve_main

        serve_main()
    elif cmd == "gate":
        from .gate import main as gate_main

        gate_main()
    else:
        print("usage: python -m firstlight.cli [seed|serve|gate]")


if __name__ == "__main__":
    main()