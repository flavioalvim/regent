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
    if full.is_symlink():
        return None  # never dereference; symlink writes are rejected upstream
    try:
        return hashlib.sha256(full.read_bytes()).hexdigest()
    except OSError:
        return None


def attribute_changes(root: Path, events: list[dict], *, envelope: list[str],
                      exemption_files: list[str], gate_effect_paths: list[str],
                      gate_envelope: list[str]) -> dict:
    """The load-bearing proof. Returns {'attributed': [...]} or raises Violation.

    Every changed path must be EXACTLY one of:
    - a specific supervisor-owned exemption file (exact path, never a whole dir);
    - a gate effect: in the RE-BASELINE delta the caller computed
      (gate_effect_paths, i.e. it appeared only after the gate ran) AND inside a
      declared gate_envelope that is a SUBSET of the agent envelope;
    - an agent write: a matching `pre` allow + `post` for the same tool_use_id,
      with the worktree blob sha256 equal to the post digest and the real-path
      inside the envelope. Deletions still require envelope membership.
    Anything else is a Violation. mode/type changes without a matching post fail."""
    root = Path(root).resolve()

    # (path, tool_use_id) → post digest, only for paths whose `pre` was ALLOWED.
    allowed_pre = {(e.get("tool_use_id"), _rel(root, p))
                   for e in events if e.get("kind") == "pre"
                   and e.get("decision") == "allow" for p in e.get("paths", [])}
    posts: dict[str, dict] = {}
    for e in events:
        if e.get("kind") == "post" and e.get("path"):
            rel = _rel(root, e["path"])
            if (e.get("tool_use_id"), rel) in allowed_pre:
                posts[rel] = {"sha": e.get("content_sha256"), "mode": e.get("mode")}

    exempt = {_rel(root, p) for p in exemption_files}
    gate_effects = {_rel(root, p) for p in gate_effect_paths}

    def _in(path: str, roots: list[str]) -> bool:
        real = (root / path).resolve()
        for r in roots:
            rr = Path(r).resolve() if Path(r).is_absolute() else (root / r).resolve()
            if real == rr or rr in real.parents:
                return True
        return False

    # gate_envelope must be a subset of the agent envelope.
    for g in gate_envelope:
        if not _in(_rel(root, g) if not Path(g).is_absolute() else
                   str(Path(g).resolve()), envelope):
            raise Violation({"reason": "gate_envelope not subset of envelope",
                             "path": g})

    attributed, violations = [], []
    for status, path in changed_paths(root):
        if path in exempt:
            continue
        if path in posts:
            full = root / path
            if full.is_symlink():
                # regular→symlink swap after the post: git stores a different
                # type/blob than what was posted (checked before envelope, whose
                # resolve() would also reject it, to give a specific reason).
                violations.append({"path": path, "reason": "posted path is now a symlink"})
            elif status.strip() == "D" or not full.exists():
                violations.append({"path": path, "reason": "posted path deleted/missing"})
            elif not _in(path, envelope):
                violations.append({"path": path, "reason": "posted but outside envelope"})
            else:
                actual = _blob_sha256(root, path)
                actual_mode = _file_mode(root, path)
                if actual != posts[path]["sha"]:
                    violations.append({"path": path, "reason": "blob sha mismatch",
                                       "expected": posts[path]["sha"], "actual": actual})
                elif posts[path]["mode"] is not None \
                        and actual_mode != posts[path]["mode"]:
                    violations.append({"path": path, "reason": "mode changed after post",
                                       "expected": posts[path]["mode"],
                                       "actual": actual_mode})
                else:
                    attributed.append(path)
        elif path in gate_effects and _in(path, gate_envelope):
            attributed.append(path)  # a genuine gate effect, in scope
        else:
            violations.append({"path": path, "reason": "changed with no allowed "
                               "post event and not a scoped gate effect"})
    if violations:
        raise Violation({"violations": violations})
    return {"attributed": attributed}


def _file_mode(root: Path, path: str) -> str | None:
    try:
        import os
        return oct(os.lstat(root / path).st_mode & 0o777)  # lstat: no deref
    except OSError:
        return None


def _rel(root: Path, path: str) -> str:
    p = Path(path)
    try:
        return str((p.parent.resolve() / p.name).relative_to(root))
    except (ValueError, OSError):
        return path
