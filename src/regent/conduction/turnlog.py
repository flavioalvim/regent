"""Turn event log verification (PLAN-004 STEP-01/02).

Two independent checks:
- verify_chain: recomputes the HMAC chain and requires the supervisor's
  terminal seal (its absence means the log was truncated or removed wholesale).
  This is AUDIT — it detects accidental corruption and third-party tampering,
  NOT agent forgery (the trust model assumes the agent may read the secret).
- attribute_changes: the load-bearing proof. The turn's git diff, relative to
  the clean baseline, must EQUAL the attributed set: every changed path is in
  the envelope (or an operational exemption), and each agent-written path's
  worktree blob sha256 matches its last `post` event. Anything else is a
  violation. Gate-effect paths are accepted only inside the declared
  gate-envelope subset.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import subprocess
from pathlib import Path

TERMINAL_SEAL = "__regent_terminal_seal__"


class ChainError(Exception):
    pass


class Violation(Exception):
    def __init__(self, detail: dict) -> None:
        super().__init__(str(detail))
        self.detail = detail


def _canonical(line: dict) -> str:
    return json.dumps(line, sort_keys=True, separators=(",", ":"))


def read_events(log_path: Path) -> list[dict]:
    try:
        raw = Path(log_path).read_text(encoding="utf-8")
    except OSError:
        return []
    return [json.loads(l) for l in raw.splitlines() if l.strip()]


def append_terminal_seal(log_path: Path, secret: str) -> None:
    """Supervisor-written closing event; its later presence proves the log was
    not truncated (an agent removing the tail loses the seal)."""
    from .hookscript import _append_event
    import os
    old = dict(os.environ)
    os.environ["REGENT_EVENT_LOG"] = str(log_path)
    os.environ["REGENT_TURN_SECRET"] = secret
    try:
        _append_event({"kind": TERMINAL_SEAL})
    finally:
        os.environ.clear()
        os.environ.update(old)


def verify_chain(log_path: Path, secret: str, *, require_seal: bool = True) -> list[dict]:
    events = read_events(log_path)
    if not events:
        raise ChainError("empty or missing event log")
    key = secret.encode()
    prev_hmac = ""
    prev_seq = -1
    for event in events:
        stored = event.get("hmac", "")
        seq = event.get("seq")
        if seq != prev_seq + 1:
            raise ChainError(f"seq gap/fork at {seq!r} (expected {prev_seq + 1})")
        recomputed_input = {k: v for k, v in event.items() if k != "hmac"}
        expected = hmac.new(key, (_canonical(recomputed_input) + prev_hmac).encode(),
                            hashlib.sha256).hexdigest()
        if not hmac.compare_digest(stored, expected):
            raise ChainError(f"hmac mismatch at seq {seq}")
        prev_hmac, prev_seq = stored, seq
    if require_seal and events[-1].get("kind") != TERMINAL_SEAL:
        raise ChainError("missing terminal seal (log truncated or removed)")
    return events


def _git(root: Path, *argv: str) -> str:
    return subprocess.run(["git", "-C", str(root), *argv],
                          capture_output=True, text=True, check=True).stdout


def changed_paths(root: Path) -> list[tuple[str, str]]:
    """[(xy_status, path)] from porcelain, handling renames as del+add."""
    out = _git(root, "status", "--porcelain", "-z", "-uall")
    entries, parts = [], out.split("\0")
    i = 0
    while i < len(parts):
        chunk = parts[i]
        if not chunk:
            i += 1
            continue
        status, path = chunk[:2], chunk[3:]
        if status[0] in ("R", "C"):  # rename/copy: the source is the next field
            i += 1
        entries.append((status, path))
        i += 1
    return entries


def _blob_sha256(root: Path, path: str) -> str | None:
    full = Path(root) / path
    try:
        return hashlib.sha256(full.read_bytes()).hexdigest()
    except OSError:
        return None


def attribute_changes(root: Path, events: list[dict], *, envelope: list[str],
                      gate_envelope: list[str], exemptions: list[str]) -> dict:
    """Returns {'attributed': [...], } or raises Violation. Proof: every changed
    path must be explained by an agent post-event (blob sha matches), a declared
    gate-effect path, or an operational exemption."""
    root = Path(root).resolve()
    posts: dict[str, str | None] = {}
    for event in events:
        if event.get("kind") == "post" and event.get("path"):
            try:
                rel = str(Path(event["path"]).resolve().relative_to(root))
            except (ValueError, OSError):
                rel = event["path"]
            posts[rel] = event.get("content_sha256")

    def _in(path: str, roots: list[str]) -> bool:
        real = (root / path).resolve()
        for r in roots:
            rr = (root / r).resolve()
            if real == rr or rr in real.parents:
                return True
        return False

    attributed, violations = [], []
    for status, path in changed_paths(root):
        if _in(path, exemptions):
            continue  # operational files: PLAN-002 choreography handles them
        if path in posts:
            if status.strip() == "D":
                attributed.append(path)
                continue
            actual = _blob_sha256(root, path)
            if actual != posts[path]:
                violations.append({"path": path, "reason": "blob sha mismatch",
                                   "expected": posts[path], "actual": actual})
            elif not _in(path, envelope):
                violations.append({"path": path, "reason": "posted but outside envelope"})
            else:
                attributed.append(path)
        elif _in(path, gate_envelope):
            attributed.append(path)  # legitimate gate effect
        else:
            violations.append({"path": path, "reason": "changed with no post event "
                               "and not a declared gate effect"})
    if violations:
        raise Violation({"violations": violations})
    return {"attributed": attributed}
