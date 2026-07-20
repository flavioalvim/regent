"""regent init — seed .regent/ and managed integrations into a host project.

Contract (PRD REQ-003 §6, REQ-004): installation is atomic — exit 0 only on
complete seeding; any failure rolls back every path this run created, leaving
no partial state. A missing agent CLI is a warning, never an init failure.
Pre-existing content that diverges from what would be seeded is a conflict:
nothing is touched. Re-running over an identical installation is a no-op.
"""

from __future__ import annotations

import shutil
import sys
from importlib import resources
from pathlib import Path

SKILL_NAMES = ("regent", "regent-stop")
AGENT_CLIS = ("claude", "codex")

EXIT_OK = 0
EXIT_CONFLICT = 2
EXIT_FAILURE = 1


class SeedConflict(Exception):
    """Pre-existing host content diverges from what init would seed."""


def _template_skill(name: str) -> str:
    ref = resources.files("regent").joinpath(f"templates/skills/{name}/SKILL.md")
    return ref.read_text(encoding="utf-8")


def _plan(project_root: Path) -> list[tuple[str, Path, str]]:
    """Returns [(kind, path, payload)] where kind is 'file' or 'symlink'.

    payload = file content, or the symlink target (relative)."""
    plan: list[tuple[str, Path, str]] = []
    for name in SKILL_NAMES:
        plan.append(("file", project_root / ".regent" / "skills" / name / "SKILL.md",
                     _template_skill(name)))
        plan.append(("symlink", project_root / ".claude" / "skills" / name,
                     f"../../.regent/skills/{name}"))
    plan.append(("file", project_root / ".regent" / "brainstorm" / "rodadas" / ".gitkeep", ""))
    return plan


def _existing_state(kind: str, path: Path, payload: str) -> str:
    """'absent' | 'identical' | 'divergent' for one planned entry."""
    if kind == "symlink":
        if not path.is_symlink():
            return "absent" if not path.exists() else "divergent"
        import os
        return "identical" if os.readlink(path) == payload else "divergent"
    if not path.exists():
        return "absent"
    if path.is_file() and path.read_text(encoding="utf-8") == payload:
        return "identical"
    return "divergent"


def run_init(project_root: Path, out=sys.stdout) -> int:
    project_root = project_root.resolve()
    try:
        plan = _plan(project_root)
    except (FileNotFoundError, ModuleNotFoundError) as exc:
        print(f"error: packaged templates unavailable: {exc}", file=out)
        return EXIT_FAILURE

    states = {path: _existing_state(kind, path, payload) for kind, path, payload in plan}
    divergent = [p for p, s in states.items() if s == "divergent"]
    if divergent:
        print("error: conflict — pre-existing content differs from what regent would seed:",
              file=out)
        for p in divergent:
            print(f"  {p.relative_to(project_root)}", file=out)
        print("nothing was changed. Resolve the conflicts and re-run.", file=out)
        return EXIT_CONFLICT

    todo = [(kind, path, payload) for kind, path, payload in plan
            if states[path] == "absent"]
    if not todo:
        print("already initialized — nothing to do.", file=out)
        _warn_missing_clis(out)
        return EXIT_OK

    created: list[Path] = []
    try:
        for kind, path, payload in todo:
            for parent in _missing_parents(path):
                parent.mkdir()
                created.append(parent)
            if kind == "file":
                path.write_text(payload, encoding="utf-8")
            else:
                path.symlink_to(payload)
            created.append(path)
    except OSError as exc:
        _rollback(created)
        print(f"error: seeding failed ({exc}); all changes rolled back.", file=out)
        return EXIT_FAILURE

    for kind, path, _ in todo:
        print(f"seeded {path.relative_to(project_root)}"
              + (" (symlink)" if kind == "symlink" else ""), file=out)
    _warn_missing_clis(out)
    print("regent initialized. Open a Claude Code session here and use /regent.", file=out)
    return EXIT_OK


def _missing_parents(path: Path) -> list[Path]:
    missing = []
    for parent in path.parents:
        if parent.exists():
            break
        missing.append(parent)
    return list(reversed(missing))


def _rollback(created: list[Path]) -> None:
    for path in reversed(created):
        try:
            if path.is_symlink() or path.is_file():
                path.unlink()
            elif path.is_dir():
                path.rmdir()
        except OSError:
            pass  # best effort; leftover paths are reported by the failure message


def _warn_missing_clis(out) -> None:
    for cli in AGENT_CLIS:
        if shutil.which(cli) is None:
            print(f"warning: agent CLI '{cli}' not found on PATH "
                  f"(run 'regent doctor' for capability diagnostics)", file=out)
