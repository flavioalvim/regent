"""Atomic evidence sets for conduction artifacts (PLAN-003 contracts).

An evidence SET (main artifact + siblings such as the prompt copy or the
FULL.log) has ONE atomic contract: every path is pre-checked BEFORE anything
is written (any pre-existing member = conflict — evidence is never
overwritten); siblings are committed first (tmp+replace each), the main
artifact last; every terminal outcome leaves the set complete; a non-terminal
failure removes the orphan siblings written so far.
"""

from __future__ import annotations

import os
import uuid
from pathlib import Path

from ..protocol.audit import utcnow


class EvidenceConflict(Exception):
    def __init__(self, paths: list[str]) -> None:
        super().__init__(f"evidence already exists: {paths}")
        self.paths = paths


def atomic_write(path: Path, content: "str | bytes") -> None:
    """Atomic NO-CLOBBER publish: os.link fails with EEXIST if the target
    appeared meanwhile (closes the precheck→publish TOCTOU — evidence is never
    overwritten, not even by a concurrent writer)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.tmp-{uuid.uuid4().hex}")
    payload = content.encode("utf-8") if isinstance(content, str) else content
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o644)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(payload)
        os.link(tmp, path)  # atomic no-clobber (EEXIST if raced)
    except OSError as exc:
        import errno as _errno
        if exc.errno == _errno.EEXIST:
            try:
                tmp.unlink()
            except OSError:
                pass
            raise EvidenceConflict([str(path)]) from None
        try:
            tmp.unlink()
        except OSError:
            pass
        raise
    tmp.unlink()


class EvidenceSet:
    def __init__(self, main: Path, siblings: dict[str, Path]) -> None:
        self.main = Path(main)
        self.siblings = {k: Path(v) for k, v in siblings.items()}
        self._written: list[Path] = []

    def precheck(self) -> None:
        existing = [str(p) for p in (self.main, *self.siblings.values())
                    if p.exists() or p.is_symlink()]
        if existing:
            raise EvidenceConflict(existing)

    def write_sibling(self, key: str, content: "str | bytes") -> Path:
        path = self.siblings[key]
        try:
            atomic_write(path, content)
        except (OSError, EvidenceConflict):
            self.cleanup_orphans()
            raise
        self._written.append(path)
        return path

    def write_main(self, header: dict, body: str) -> Path:
        lines = ["---"]
        for key, value in header.items():
            lines.append(f"{key}: {value if value is not None else 'null'}")
        lines.append("---")
        content = "\n".join(lines) + "\n\n" + body
        try:
            atomic_write(self.main, content)
        except (OSError, EvidenceConflict):
            self.cleanup_orphans()
            raise
        return self.main

    def cleanup_orphans(self) -> None:
        for path in self._written:
            try:
                path.unlink()
            except OSError:
                pass


def header(outcome: str, exit_code: int | None, linkage: str, **extra) -> dict:
    base = {"outcome": outcome, "exit_code": exit_code,
            "timestamp": utcnow(), "linkage": linkage}
    base.update(extra)
    return base
