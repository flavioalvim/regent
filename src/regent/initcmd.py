"""regent init — seed .regent/ and managed integrations into a host project.

Contract (PRD REQ-003 §6, REQ-004; PLAN-002 STEP-03): installation is atomic —
exit 0 only on complete seeding; any failure rolls back every path this run
created OR OVERWROTE (originals restored), leaving no partial state. A missing
agent CLI is a warning, never an init failure.

Upgrade protocol (PLAN-002): templates/MANIFEST.json lists the sha256 of every
KNOWN released version of each seeded template. Existing content whose hash is
listed is UPGRADED atomically to the current template; unknown content is a
conflict and is preserved untouched. `.regent/control.json` is seeded when
absent; a present-and-valid control (any evolved version) is a no-op; a corrupt
control is a conflict.
"""

from __future__ import annotations

import hashlib
import json
import shutil
import sys
from importlib import resources
from pathlib import Path

SKILL_NAMES = ("regent", "regent-stop")
AGENT_CLIS = ("claude", "codex")

EXIT_OK = 0
EXIT_CONFLICT = 2
EXIT_FAILURE = 1


def _template_skill(name: str) -> str:
    ref = resources.files("regent").joinpath(f"templates/skills/{name}/SKILL.md")
    return ref.read_text(encoding="utf-8")


def _manifest() -> dict:
    ref = resources.files("regent").joinpath("templates/MANIFEST.json")
    return json.loads(ref.read_text(encoding="utf-8"))


def _plan(project_root: Path) -> list[tuple[str, Path, str]]:
    """[(kind, path, payload)]: kind ∈ file|symlink|control; payload = content,
    symlink target, or manifest key (for files under the manifest)."""
    plan: list[tuple[str, Path, str]] = []
    for name in SKILL_NAMES:
        plan.append(("file", project_root / ".regent" / "skills" / name / "SKILL.md",
                     _template_skill(name)))
        plan.append(("symlink", project_root / ".claude" / "skills" / name,
                     f"../../.regent/skills/{name}"))
    plan.append(("file", project_root / ".regent" / "brainstorm" / "rounds" / ".gitkeep", ""))
    plan.append(("file", project_root / ".regent" / "plans" / ".gitkeep", ""))
    plan.append(("control", project_root / ".regent" / "control.json", ""))
    return plan


def _manifest_key(project_root: Path, path: Path) -> str | None:
    try:
        rel = path.relative_to(project_root / ".regent")
    except ValueError:
        return None
    return str(rel)


def _existing_state(kind: str, path: Path, payload: str,
                    known_hashes: list[str]) -> str:
    """'absent' | 'identical' | 'upgradeable' | 'divergent'."""
    if kind == "symlink":
        if not path.is_symlink():
            return "absent" if not path.exists() else "divergent"
        import os
        return "identical" if os.readlink(path) == payload else "divergent"
    if kind == "control":
        if not path.exists():
            return "absent"
        from .protocol.audit import AuditLog
        from .protocol.control import ControlSchemaError, ControlStore
        try:
            ControlStore(path, AuditLog(path.parent / "protocol" / "audit.jsonl")).load()
            return "identical"  # valid at ANY evolved version = no-op
        except ControlSchemaError:
            return "divergent"
    if path.is_symlink():
        return "divergent"  # never follow/overwrite a symlinked skill target
    if not path.exists():
        return "absent"
    if not path.is_file():
        return "divergent"
    content = path.read_bytes()
    if content.decode("utf-8", errors="replace") == payload:
        return "identical"
    if hashlib.sha256(content).hexdigest() in known_hashes:
        return "upgradeable"  # known released version → atomic upgrade
    return "divergent"


def run_init(project_root: Path, out=sys.stdout) -> int:
    project_root = project_root.resolve()
    try:
        plan = _plan(project_root)
        manifest = _manifest()
    except (FileNotFoundError, ModuleNotFoundError, json.JSONDecodeError) as exc:
        print(f"error: packaged templates unavailable: {exc}", file=out)
        return EXIT_FAILURE

    states = {}
    for kind, path, payload in plan:
        key = _manifest_key(project_root, path)
        known = manifest.get(key, []) if key else []
        states[path] = _existing_state(kind, path, payload, known)

    divergent = [p for p, s in states.items() if s == "divergent"]
    if divergent:
        print("error: conflict — pre-existing content differs from every known "
              "regent version:", file=out)
        for p in divergent:
            print(f"  {p.relative_to(project_root)}", file=out)
        print("nothing was changed. Resolve the conflicts and re-run.", file=out)
        return EXIT_CONFLICT

    todo = [(kind, path, payload) for kind, path, payload in plan
            if states[path] in ("absent", "upgradeable")]
    if not todo:
        print("already initialized — nothing to do.", file=out)
        _warn_missing_clis(out)
        return EXIT_OK

    created: list[Path] = []
    replaced: list[tuple[Path, bytes]] = []
    try:
        for kind, path, payload in todo:
            for parent in _missing_parents(path):
                parent.mkdir()
                created.append(parent)
            if kind == "file":
                if states[path] == "upgradeable":
                    replaced.append((path, path.read_bytes()))
                    _atomic_write(path, payload)
                else:
                    _atomic_write(path, payload)
                    created.append(path)
            elif kind == "symlink":
                path.symlink_to(payload)
                created.append(path)
            else:  # control
                from .protocol.audit import AuditLog
                from .protocol.control import ControlStore
                ControlStore(path, AuditLog(path.parent / "protocol" / "audit.jsonl")
                             ).seed()
                created.append(path)
    except OSError as exc:
        _rollback(created, replaced)
        print(f"error: seeding failed ({exc}); all changes rolled back.", file=out)
        return EXIT_FAILURE

    for kind, path, _ in todo:
        verb = "upgraded" if states[path] == "upgradeable" else "seeded"
        print(f"{verb} {path.relative_to(project_root)}"
              + (" (symlink)" if kind == "symlink" else ""), file=out)
    _warn_missing_clis(out)
    print("regent initialized. Open a Claude Code session here and use /regent.",
          file=out)
    return EXIT_OK


def _missing_parents(path: Path) -> list[Path]:
    missing = []
    for parent in path.parents:
        if parent.exists():
            break
        missing.append(parent)
    return list(reversed(missing))


def _atomic_write(path: Path, payload: str) -> None:
    import os
    tmp = path.with_name(path.name + ".regent-tmp")
    tmp.write_text(payload, encoding="utf-8")
    os.replace(tmp, path)


def _rollback(created: list[Path], replaced: list[tuple[Path, bytes]]) -> None:
    import os
    for path, original in replaced:
        try:
            tmp = path.with_name(path.name + ".regent-tmp")
            tmp.write_bytes(original)
            os.replace(tmp, path)
        except OSError:
            pass
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
