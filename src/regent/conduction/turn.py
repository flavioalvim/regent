"""`regent turn run` — one supervised, confined production turn (PLAN-004).

Orchestrates COMPOSED → LAUNCHED (confined claude) → GATED → VERIFIED →
COMMITTED, with a durable per-phase checkpoint, keep-alive heartbeats spanning
launch AND gate, and stop checks at phase boundaries. Only the SUPERVISOR
commits, via a private git index with a HEAD compare-and-swap and a token
re-check immediately before update-ref; the attributed set is proven by git
(blob shas vs authenticated post events), never trusted from the agent. Gate
effects are isolated by a re-baseline (paths that appeared only after the gate)
and must sit in a declared gate_envelope ⊆ envelope.
"""

from __future__ import annotations

import os
import re
import subprocess
import tempfile
import threading
from pathlib import Path

from ..activity import ActivityService
from ..protocol.control import assert_turn_token, NotLockOwner
from .confine import compose, launch_argv, launch_env
from .evidence import EvidenceSet, header
from .gate import run_gate
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


def _under(root: Path, path: Path) -> bool:
    root, path = root.resolve(), path.resolve()
    return path == root or root in path.parents


def _current_step(plan_text: str, artifact_dir: Path) -> str | None:
    """The smallest STEP-NN declared in the plan with no build/STEP-NN.md yet."""
    steps = sorted(set(re.findall(r"STEP-\d+", plan_text)),
                   key=lambda s: int(s.split("-")[1]))
    for step in steps:
        if not (artifact_dir / f"{step}.md").exists():
            return step
    return None


def _step_gate(plan_text: str, step_name: str) -> str | None:
    """Extract the gate from THAT step's block (heading → next STEP heading)."""
    m = re.search(rf"{re.escape(step_name)}\b(.*?)(?=STEP-\d+|\Z)", plan_text, re.S)
    if not m:
        return None
    g = re.search(r"\*\*Gate:\*\*\s*`([^`]+)`", m.group(1))
    return g.group(1) if g else None


def _set_phase(service: ActivityService, phase: str) -> None:
    (service.state_dir / "turn.phase").write_text(phase, encoding="utf-8")


def run_turn(root: Path, *, prompt_file: Path, envelope: list[str],
             gate_command: str, declared_in: Path, step: str,
             artifact_dir: Path, linkage: str, gate_envelope: list[str] | None = None,
             timeout: float = 900.0, claude_bin: str = "claude",
             runner=None, service: ActivityService | None = None) -> dict:
    root = Path(root).resolve()
    service = service or ActivityService(root)
    artifact_dir = (root / artifact_dir).resolve() if not Path(artifact_dir).is_absolute() \
        else Path(artifact_dir).resolve()
    envelope = [str((root / p).resolve()) if not Path(p).is_absolute()
                else str(Path(p).resolve()) for p in envelope]
    gate_envelope = [str((root / p).resolve()) if not Path(p).is_absolute()
                     else str(Path(p).resolve()) for p in (gate_envelope or [])]

    # -- preconditions (REQ-005 binding, rigid) ---------------------------
    control = service.store.load()
    activity = control.get("activity")
    if activity is None or activity["state"] != "ACTIVE" \
            or activity["type"] != "build":
        raise TurnError("NOT_ACTIVE", {"state": (activity or {}).get("state", "idle")})
    plan_id, step_name = step.split("/", 1)
    if activity["id"] != plan_id:
        raise TurnError("STEP_MISMATCH", {"activity": activity["id"],
                                          "step_plan": plan_id})
    declared_in = Path(declared_in).resolve()
    expected_plan = (root / ".regent" / "plans" / plan_id / "PLAN.md").resolve()
    if declared_in != expected_plan:
        raise TurnError("STEP_MISMATCH", {"declared_in": str(declared_in),
                                          "expected": str(expected_plan)})
    if not _under(root / ".regent", artifact_dir):
        raise TurnError("ARTIFACT_OUTSIDE_REGENT", {"artifact_dir": str(artifact_dir)})
    plan_text = declared_in.read_text(encoding="utf-8", errors="replace")
    current = _current_step(plan_text, artifact_dir)
    if current != step_name:
        raise TurnError("STEP_MISMATCH", {"step": step_name, "current_step": current})
    declared_gate = _step_gate(plan_text, step_name)
    if declared_gate is None or gate_command != declared_gate:
        raise TurnError("PROVENANCE",
                        {"reason": "gate command is not this step's declared gate",
                         "declared": declared_gate})
    step_file = artifact_dir / f"{step_name}.md"
    if step_file.exists():
        raise TurnError("STEP_ALREADY_DONE", {"step_file": str(step_file)})
    token = activity["turn"]["token"]
    if _dirty_non_exempt(root):
        raise TurnError("WORKTREE_DIRTY", {})
    base_sha = _git(root, "rev-parse", "HEAD").strip()

    # -- COMPOSED ---------------------------------------------------------
    _set_phase(service, "COMPOSED")
    turn = compose(envelope=envelope, claude_bin=claude_bin)
    artifact = artifact_dir / f"TURN-{_slug(linkage)}.md"
    gate_artifact = artifact_dir / f"GATE-{step_name}.md"
    evidence = EvidenceSet(artifact, {})
    evidence.precheck()
    outcome, claude_exit, attributed, commit_sha, detail = "FAILURE", None, [], None, ""
    stop = threading.Event()
    beat = threading.Thread(target=_keepalive, args=(service, token, stop), daemon=True)
    beat.start()
    try:
        service.heartbeat()
        if service.stop_check()["stop_requested"]:
            raise TurnError("STOPPED", {"phase": "COMPOSED"})
        # -- LAUNCHED -----------------------------------------------------
        _set_phase(service, "LAUNCHED")
        prompt = Path(prompt_file).read_text(encoding="utf-8")
        argv = launch_argv(turn, prompt=prompt, claude_bin=claude_bin)
        run = runner or SubprocessRunner()
        result = run.run(argv, cwd=str(root), timeout=timeout, env=launch_env(turn))
        claude_exit = result.exit_code
        append_terminal_seal(turn.event_log, turn.secret)
        events = read_events(turn.event_log)
        pre_gate_changes = {p for _s, p in changed_paths(root)}

        if result.timed_out:
            outcome = "TIMEOUT"
        elif result.exit_code not in (0, None):
            outcome, detail = "FAILURE", f"claude exited {result.exit_code}"
        else:
            # -- GATED (keep-alive still running; heartbeat first) --------
            _set_phase(service, "GATED")
            service.heartbeat()
            try:
                gate = run_gate(root, command=gate_command, declared_in=declared_in,
                                artifact=gate_artifact, linkage=step, runner=run)
                gate_outcome = gate["outcome"]
            except Exception as exc:  # noqa: BLE001
                gate_outcome = f"GATE_ERROR:{exc}"
            gate_effects = [str(root / p) for _s, p in changed_paths(root)
                            if p not in pre_gate_changes]

            # -- VERIFIED -------------------------------------------------
            _set_phase(service, "VERIFIED")
            exemption_files = EXEMPTIONS + [
                str(gate_artifact.relative_to(root)), str(artifact.relative_to(root)),
                str(step_file.relative_to(root))]
            try:
                verify_chain(turn.event_log, turn.secret)
                attributed = attribute_changes(
                    root, events, envelope=envelope,
                    exemption_files=exemption_files,
                    gate_effect_paths=gate_effects,
                    gate_envelope=gate_envelope)["attributed"]
                outcome = "TURN_OK" if gate_outcome == "GREEN" else "GATE_RED"
                if gate_outcome != "GREEN":
                    detail = f"gate outcome {gate_outcome}"
            except ChainError as exc:
                outcome, attributed, detail = "TURN_TAMPERED", [], str(exc)
            except Violation as exc:
                outcome, attributed, detail = "TURN_VIOLATION", [], str(exc.detail)

        body = _log_body(turn.event_log)
        evidence.write_main(header(outcome, claude_exit, linkage, base_sha=base_sha,
                                   attributed=len(attributed), detail=detail), body)
    except BaseException:
        stop.set(); beat.join(timeout=2)
        evidence.cleanup_orphans()
        turn.cleanup()
        raise
    stop.set(); beat.join(timeout=2)
    turn.cleanup()

    # -- COMMITTED (supervisor only) --------------------------------------
    _set_phase(service, "COMMITTING")
    if outcome == "TURN_OK":
        _write_step_file(step_file, step_name, attributed, base_sha, linkage,
                         gate_command)
        commit_sha = _supervisor_commit(
            root, base_sha, attributed + [
                str(step_file.relative_to(root)), str(artifact.relative_to(root)),
                str(gate_artifact.relative_to(root))],
            step=step, linkage=linkage, token=token, service=service)
    else:
        extra = [str(gate_artifact.relative_to(root))] if gate_artifact.exists() else []
        commit_sha = _operational_commit(
            root, [str(artifact.relative_to(root))] + extra,
            linkage=linkage, outcome=outcome, token=token, service=service)
    _set_phase(service, "COMMITTED")

    return {"ok": outcome == "TURN_OK", "outcome": outcome,
            "files_committed": attributed if outcome == "TURN_OK" else [],
            "artifact": str(artifact), "commit": commit_sha, "detail": detail}


def _keepalive(service, token, stop) -> None:
    while not stop.wait(120):  # every 2 min, well under stale_after (1800s)
        try:
            service.lock.heartbeat(token)
        except Exception:  # noqa: BLE001 — a lost token surfaces at commit fencing
            return


def _dirty_non_exempt(root: Path) -> bool:
    return any(path not in EXEMPTIONS for _s, path in changed_paths(root))


def _log_body(log_path: Path) -> str:
    try:
        return Path(log_path).read_text(encoding="utf-8")
    except OSError:
        return "(event log unavailable)"


def _write_step_file(step_file: Path, step_name: str, attributed: list[str],
                     base_sha: str, linkage: str, gate_command: str) -> None:
    lines = [f"# {step_name} — produced by a supervised confined turn", "",
             f"step_base_sha: {base_sha}", f"linkage: {linkage}",
             f"gate_command: {gate_command}", "gate_outcome: GREEN",
             "files (attributed to the agent):"]
    lines += [f"  - {p}" for p in attributed] or ["  - (none)"]
    step_file.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _supervisor_commit(root: Path, base_sha: str, paths: list[str], *, step: str,
                       linkage: str, token: str, service: ActivityService) -> str:
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
        # Fencing + CAS in the SMALLEST window before advancing HEAD.
        assert_turn_token(service.store.load(), token)
        if _git(root, "rev-parse", "HEAD").strip() != base_sha:
            raise TurnError("CONFLICT", {"reason": "HEAD moved since baseline"})
        _git(root, "update-ref", "-m", "regent turn", "HEAD", commit, base_sha,
             env=env)
        _git(root, "reset", "--mixed", "HEAD")  # sync normal index + worktree
        return commit
    finally:
        try:
            index.unlink()
        except OSError:
            pass


def _operational_commit(root: Path, paths: list[str], *, linkage: str,
                        outcome: str, token: str, service: ActivityService) -> str | None:
    try:
        assert_turn_token(service.store.load(), token)
    except NotLockOwner:
        raise TurnError("CONFLICT", {"reason": "token diverged before commit"})
    for path in paths:
        _git(root, "add", "--", path)
    if not _git(root, "diff", "--cached", "--name-only").strip():
        return None
    _git(root, "commit", "-q", "-m",
         f"turn(PLAN-004): {outcome} evidence (no product)\n\nRegent-Turn: {linkage}")
    return _git(root, "rev-parse", "HEAD").strip()
