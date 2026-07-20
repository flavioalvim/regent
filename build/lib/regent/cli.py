"""regent CLI entry point: init and doctor subcommands."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import __version__
from .doctor import run_doctor
from .initcmd import run_init


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="regent",
        description="Autonomous conduction and mediated adversarial deliberation "
                    "between AI agents, pluggable into any project.")
    parser.add_argument("--version", action="version", version=f"regent {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    p_init = sub.add_parser("init", help="seed .regent/ and managed integrations here")
    p_init.add_argument("--project", default=".", help="host project root (default: cwd)")

    p_doctor = sub.add_parser("doctor", help="diagnose agent CLI capabilities")
    p_doctor.add_argument("--project", default=".", help="host project root (default: cwd)")

    args = parser.parse_args(argv)
    root = Path(args.project)
    if args.command == "init":
        return run_init(root)
    return run_doctor(root)


def entrypoint() -> None:
    sys.exit(main())


if __name__ == "__main__":
    entrypoint()
