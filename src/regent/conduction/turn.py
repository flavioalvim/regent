"""`regent turn run` — one supervised, confined production turn (PLAN-004 STEP-03).

Orchestrates COMPOSED → LAUNCHED (confined claude) → GATED → VERIFIED →
COMMITTED, with a durable per-phase checkpoint in the control, heartbeats and
stop checks at every boundary. Only the SUPERVISOR commits, via a private git
index with a HEAD compare-and-swap; the attributed set is proven by git (blob
shas vs post events), never trusted from the agent.
"""

from __future__ import annotations

import re
import subprocess
import threading
from pathlib import Path

from ..activity import ActivityService
from .confine import compose, launch_argv, launch_env
from .evidence import EvidenceSet, header
from .gate import run_gate, ProvenanceError
from .process import SubprocessRunner
from .turnlog import (ChainError, Violation, append_terminal_seal,
                      attribute_changes, changed_paths, read_events, verify_chain)

EXEMPTIONS = [".regent/control.json", ".regent/protocol/audit.jsonl"]


class TurnError(Exception):
    def __init__(self, code: str, detail: dict) -> None:
        super().__init__(code)
        self.code, self.detail = code, detail


def _git(root: Path, *argv: str, **kw) -> str:
    return subprocess.run(["git", "-C", str(root), *argv], capture_output=True,
                          text=True, check=True, **kw).stdout


def _slug(linkage: str) -> str:
    return re.sub(r"[^A-Za-z0-9]+", "-", linkage).strip("-")


def _current_step(plan_text: str) -> list[str]:
    return re.findall(r"STEP-\d+", plan_text)


def run_turn(root: Path, *, prompt_file: Path, envelope: list[str],
             gate_command: str, declared_in: Path, step: str,
             artifact_dir: Path, linkage: str, gate_envelope: list[str] | None = None,
             timeout: float = 900.0, claude_bin: str = "claude",
             runner=None, service: ActivityService | None = None) -> dict:
    root = Path(root).resolve()
    service = service or ActivityService(root)
    gate_envelope = gate_envelope or []

    # -- preconditions (REQ-005 binding) ----------------------------------
    control = service.store.load()
    activity = control.get("activity")
    if activity is None or activity["state"] != "ACTIVE" \
            or activity["type"] != "build":
        raise TurnError("NOT_ACTIVE", {"state": (activity or {}).get("state", "idle")})
    plan_id, step_name = step.split("/", 1)
    if activity["id"] != plan_id:
        raise TurnError("STEP_MISMATCH",
                        {"activity": activity["id"], "step_plan": plan_id})
    if not str(Path(artifact_dir).resolve()).startswith(str(root / ".regent")):
        raise TurnError("ARTIFACT_OUTSIDE_REGENT", {"artifact_dir": str(artifact_dir)})
    plan_text = Path(declared_in).read_text(encoding="utf-8", errors="replace")
    if step_name not in _current_step(plan_text):
        raise TurnError("STEP_MISMATCH", {"step": step_name, "not_in": str(declared_in)})
    if gate_command not in plan_text:
        raise ProvenanceError(f"gate command not declared in {declared_in}")
    step_file = Path(artifact_dir) / f"{step_name}.md"
    if step_file.exists():
        raise TurnError("STEP_ALREADY_DONE", {"step_file": str(step_file)})
    token = activity["turn"]["token"]
    if _dirty_non_exempt(root):
        raise TurnError("WORKTREE_DIRTY", {})
    base_sha = _git(root, "rev-parse", "HEAD").strip()

    # -- COMPOSED ---------------------------------------------------------
    turn = compose(envelope=envelope, claude_bin=claude_bin)
    artifact = Path(artifact_dir) / f"TURN-{_slug(linkage)}.md"
    evidence = EvidenceSet(artifact, {})
    evidence.precheck()
    outcome, claude_exit, attributed, commit_sha = "FAILURE", None, [], None
    try:
        service.heartbeat()
        # -- LAUNCHED (confined claude, keep-alive heartbeats) ------------
        prompt = Path(prompt_file).read_text(encoding="utf-8")
        argv = launch_argv(turn, prompt=prompt, claude_bin=claude_bin)
        env = launch_env(turn)
        run = runner or SubprocessRunner()
        stop = threading.Event()
        beat = threading.Thread(target=_keepalive, args=(service, token, stop),
                                daemon=True)
        beat.start()
        try:
            result = run.run(argv, cwd=str(root), timeout=timeout, env=env)
        finally:
            stop.set()
            beat.join(timeout=2)
        claude_exit = result.exit_code
        append_terminal_seal(turn.event_log, turn.secret)
        events = read_events(turn.event_log)

        if result.timed_out:
            outcome = "TIMEOUT"
        else:
            # -- GATED (after the agent; heartbeat first) ----------------
            service.heartbeat()
            gate_artifact = Path(artifact_dir) / f"GATE-{step_name}.md"
            try:
                gate = run_gate(root, command=gate_command, declared_in=declared_in,
                                artifact=gate_artifact, linkage=step, runner=run)
                gate_outcome = gate["outcome"]
            except Exception as exc:  # noqa: BLE001 — recorded as gate failure
                gate_outcome = f"GATE_ERROR:{exc}"

            # -- VERIFIED (chain + git attribution) ----------------------
            try:
                verify_chain(turn.event_log, turn.secret)
                art_rel = str(Path(artifact_dir).resolve().relative_to(root))
                attributed = attribute_changes(
                    root, events, envelope=[str(Path(p).resolve()) for p in envelope],
                    gate_envelope=[str(Path(p).resolve()) for p in gate_envelope],
                    exemptions=EXEMPTIONS + [art_rel])["attributed"]
                if gate_outcome != "GREEN":
                    outcome = "GATE_RED"
                else:
                    outcome = "TURN_OK"
            except ChainError as exc:
                outcome = "TURN_TAMPERED"
                attributed = []
                evidence_detail = str(exc)
            except Violation as exc:
                outcome = "TURN_VIOLATION"
                attributed = []
                evidence_detail = str(exc.detail)

        # -- evidence (persisted on EVERY outcome) -----------------------
        body = _log_body(turn.event_log)
        evidence.write_main(header(outcome, claude_exit, linkage,
                                   base_sha=base_sha, attributed=len(attributed)),
                            body)
    except BaseException:
        evidence.cleanup_orphans()
        turn.cleanup()
        raise
    turn.cleanup()

    # -- COMMITTED (supervisor only, private index, HEAD CAS) -------------
    if outcome == "TURN_OK":
        _write_step_file(step_file, step_name, attributed, base_sha)
        commit_sha = _supervisor_commit(root, base_sha, attributed + [
            str(step_file.relative_to(root)), str(artifact.relative_to(root))],
            step=step, linkage=linkage, token=token, service=service)
    else:
        # operational commit of the evidence only (no product)
        commit_sha = _operational_commit(root, [str(artifact.relative_to(root))],
                                         linkage=linkage, outcome=outcome)

    return {"ok": outcome == "TURN_OK", "outcome": outcome,
            "files_committed": attributed if outcome == "TURN_OK" else [],
            "artifact": str(artifact), "commit": commit_sha}


def _keepalive(service, token, stop) -> None:
    while not stop.wait(300):  # every 5 min, well under stale_after (1800s)
        try:
            service.lock.heartbeat(token)
        except Exception:  # noqa: BLE001 — a lost token surfaces at commit
            return


def _dirty_non_exempt(root: Path) -> bool:
    for status, path in changed_paths(root):
        if path not in EXEMPTIONS:
            return True
    return False


def _log_body(log_path: Path) -> str:
    try:
        return Path(log_path).read_text(encoding="utf-8")
    except OSError:
        return "(event log unavailable)"


def _write_step_file(step_file: Path, step_name: str, attributed: list[str],
                     base_sha: str) -> None:
    lines = [f"# {step_name} — produced by a supervised confined turn", "",
             f"step_base_sha: {base_sha}", "files (attributed to the agent):"]
    lines += [f"  - {p}" for p in attributed] or ["  - (none)"]
    step_file.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _supervisor_commit(root: Path, base_sha: str, paths: list[str], *, step: str,
                       linkage: str, token: str, service: ActivityService) -> str:
    import os
    import tempfile
    if _git(root, "rev-parse", "HEAD").strip() != base_sha:
        raise TurnError("CONFLICT", {"reason": "HEAD moved since baseline"})
    from ..protocol.control import assert_turn_token
    assert_turn_token(service.store.load(), token)  # fencing
    index = Path(tempfile.mktemp(prefix="regent-index-"))
    env = dict(os.environ, GIT_INDEX_FILE=str(index))
    try:
        _git(root, "read-tree", "HEAD", env=env)
        for path in paths:
            _git(root, "add", "--", path, env=env)
        tree = _git(root, "write-tree", env=env).strip()
        msg = (f"turn(PLAN-004): supervised confined turn\n\n"
               f"Regent-Step: {step}\nRegent-Turn: {linkage}")
        commit = _git(root, "commit-tree", tree, "-p", base_sha, "-m", msg,
                      env=env).strip()
        # CAS: only advance if HEAD is still the baseline.
        _git(root, "update-ref", "--create-reflog", "-m", "regent turn",
             "HEAD", commit, base_sha, env=env)
        _git(root, "checkout", "--", ".", env=env)  # sync worktree index
        return commit
    finally:
        try:
            index.unlink()
        except OSError:
            pass


def _operational_commit(root: Path, paths: list[str], *, linkage: str,
                        outcome: str) -> str | None:
    for path in paths:
        _git(root, "add", "--", path)
    if not _git(root, "diff", "--cached", "--name-only").strip():
        return None
    _git(root, "commit", "-q", "-m",
         f"turn(PLAN-004): {outcome} evidence (no product)\n\nRegent-Turn: {linkage}")
    return _git(root, "rev-parse", "HEAD").strip()
