"""regent CLI entry point: init, doctor, status, activity and stop subcommands."""

from __future__ import annotations

import sys
from pathlib import Path

from . import __version__
from .activity_cli import _JsonArgumentParser, _UsageError, _fail, build_parser, run
from .doctor import run_doctor
from .initcmd import run_init


def main(argv: list[str] | None = None) -> int:
    parser = _JsonArgumentParser(
        prog="regent",
        description="Autonomous conduction and mediated adversarial deliberation "
                    "between AI agents, pluggable into any project.")
    parser.add_argument("--version", action="version", version=f"regent {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    p_init = sub.add_parser("init", help="seed .regent/ and managed integrations here")
    p_init.add_argument("--project", default=".", help="host project root (default: cwd)")

    p_doctor = sub.add_parser("doctor", help="diagnose agent CLI capabilities")
    p_doctor.add_argument("--project", default=".", help="host project root (default: cwd)")

    build_parser(sub)  # status / activity / stop (JSON contract)

    try:
        args = parser.parse_args(argv)
    except _UsageError as exc:
        return _fail("USAGE", str(exc))

    if args.command == "init":
        return run_init(Path(args.project))
    if args.command == "doctor":
        return run_doctor(Path(args.project))
    try:
        return run(args)
    except _UsageError as exc:
        return _fail("USAGE", str(exc))


def entrypoint() -> None:
    sys.exit(main())


if __name__ == "__main__":
    entrypoint()
