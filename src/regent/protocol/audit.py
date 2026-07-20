"""Append-only audit log under .regent/protocol/audit.jsonl.

Shareable evidence per REQ-001 §3: takeovers, stale-mutex recoveries and
stop-request discards are auditable artifacts, so they live inside the repo,
never only in disposable local state. Each append is a single-line O_APPEND
write followed by fsync — durable and safe under concurrent writers.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class AuditLog:
    def __init__(self, path: Path) -> None:
        self._path = Path(path)

    @property
    def path(self) -> Path:
        return self._path

    def append(self, record: dict) -> None:
        entry = dict(record)
        entry.setdefault("at", utcnow())
        line = json.dumps(entry, sort_keys=True) + "\n"
        self._path.parent.mkdir(parents=True, exist_ok=True)
        fd = os.open(self._path, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o644)
        try:
            os.write(fd, line.encode("utf-8"))
            os.fsync(fd)
        finally:
            os.close(fd)

    def read_all(self) -> list[dict]:
        if not self._path.exists():
            return []
        records = []
        for line in self._path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                records.append(json.loads(line))
        return records
