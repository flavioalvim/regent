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
    """Extract the gate from THAT step's block — bounded by the next step
    HEADING line (^#+ ... STEP-NN), so a gate command that merely CONTAINS a
    step name (e.g. a path work/STEP-01.out) is not truncated."""
    m = re.search(rf"{re.escape(step_name)}\b(.*?)(?=\n#+[^\n]*STEP-\d+|\Z)",
                  plan_text, re.S)
    if not m:
        return None
    g = re.search(r"\*\*Gate:\*\*\s*`([^`]+)`", m.group(1))
    return g.group(1) if g else None


def _set_phase(service: ActivityService, phase: str) -> None:
    """Durable checkpoint (atomic tmp+replace+fsync) in the disposable XDG state."""
    target = service.state_dir / "turn.phase"
    tmp = target.with_name(".turn.phase.tmp")
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o644)
    try:
        os.write(fd, phase.encode())
        os.fsync(fd)
    finally:
        os.close(fd)
    os.replace(tmp, target)
    dfd = os.open(target.parent, os.O_RDONLY)
    try:
        os.fsync(dfd)
    finally:
        os.close(dfd)


def _stopped_suspend(service, token, phase, *, reason="stop requested mid-turn") -> None:
    """Suspend via the APPLICATION LAYER so the turn lock is RELEASED (PLAN-004's
    protocol-level suspend left the lock held — corrected here per PLAN-005).
    Never swallowed: a taken-over token → CONFLICT for the mediator."""
    from ..protocol.control import NotLockOwner as _NLO
    try:
        service._suspend_locked(checkpoint=f"turn:{phase}", reason=reason)
    except _NLO:
        raise TurnError("CONFLICT", {"reason": "token diverged; cannot suspend "
                                     "(taken over?) — mediator must reconcile"})


def recover_turn(root: Path, *, linkage: str, step: str,
                 service: ActivityService | None = None) -> dict:
    """Recovery by inspection (PLAN-004): trailer → STEP file → worktree. Never
    resumes mid-agent; a partial turn leaves a dirty worktree for the mediator."""
    import json as _json
    from . import abort as _abort
    root = Path(root).resolve()
    service = service or ActivityService(root)
    plan_id, step_name = step.split("/", 1)
    step_file = root / ".regent" / "plans" / plan_id / "build" / f"{step_name}.md"

    # An UNRECONCILED abort takes precedence over any trailer/STEP evidence (the
    # ABORTED op-commit itself carries a Regent-Turn trailer, which must NOT be
    # mistaken for a completed turn while the activity is still un-suspended).
    claimed = _abort.pending_claimed(service.state_dir)
    if claimed:
        control = service.store.load()
        activity = control.get("activity") or {}
        state = activity.get("state")
        # the fencing token: turn.token while ACTIVE, suspension.owning_turn once
        # SUSPENDED (suspend sets turn=null and preserves the token there).
        cur_token = ((activity.get("turn") or {}).get("token") if state == "ACTIVE"
                     else (activity.get("suspension") or {}).get("owning_turn"))
        try:
            marker = _json.loads(claimed[0].read_text(encoding="utf-8"))
        except (OSError, ValueError):
            marker = {}
        bound = (marker.get("activity_id") == activity.get("id")
                 and marker.get("activity_epoch") == activity.get("epoch")
                 and marker.get("turn_token") == cur_token)
        binding = dict(activity_id=marker.get("activity_id"),
                       activity_epoch=marker.get("activity_epoch"),
                       turn_token=marker.get("turn_token"))
        if not bound:
            return {"state": "ABORT_MARKER_UNBOUND", "action": "mediator must reconcile"}
        if state == "SUSPENDED":
            if service.lock.status()["state"] == "free":
                _abort.clear_claimed(service.state_dir, **binding)
                return {"state": "ABORT_RECONCILED",
                        "action": "already suspended; /regent resumes"}
            return {"state": "ABORT_RECOVERY_INCOMPLETE",
                    "action": "mediator must reconcile"}
        if state == "ACTIVE":
            try:
                service._suspend_locked(checkpoint="turn:ABORT_RECOVERY",
                                        reason="abort reconciled on recovery")
            except Exception as exc:  # noqa: BLE001 — surface, do NOT clear
                return {"state": "ABORT_RECOVERY_FAILED", "error": repr(exc),
                        "action": "mediator must reconcile"}
            if service.store.load()["activity"]["state"] == "SUSPENDED" \
                    and service.lock.status()["state"] == "free":
                _abort.clear_claimed(service.state_dir, **binding)
                return {"state": "ABORT_RECONCILED", "action": "suspended; /regent resumes"}
            return {"state": "ABORT_RECOVERY_INCOMPLETE",
                    "action": "mediator must reconcile"}
        return {"state": "ABORT_MARKER_UNBOUND", "action": "mediator must reconcile"}

    log = _git(root, "log", "--grep", f"Regent-Turn: {re.escape(linkage)}",
               "--format=%H")
    if log.strip():
        return {"state": "COMMITTED", "commit": log.splitlines()[0]}
    if step_file.exists():
        return {"state": "STEP_DONE", "step_file": str(step_file)}
    if _dirty_non_exempt(root):
        return {"state": "PARTIAL", "action": "mediator must inspect/discard the "
                "worktree; a mid-agent turn is never auto-resumed"}
    return {"state": "CLEAN", "action": "rerun the turn"}


def run_turn(root: Path, *, prompt_file: Path, envelope: list[str],
             gate_command: str, declared_in: Path, step: str,
             artifact_dir: Path, linkage: str, gate_envelope: list[str] | None = None,
             timeout: float = 900.0, claude_bin: str = "claude",
             runner=None, service: ActivityService | None = None,
             attempt: int | None = None) -> dict:
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
    canonical_build = (root / ".regent" / "plans" / plan_id / "build").resolve()
    if artifact_dir != canonical_build or not _under(root, artifact_dir):
        # equality AND real containment: a `build` symlink pointing outside the
        # repo resolves away and fails _under.
        raise TurnError("ARTIFACT_OUTSIDE_REGENT",
                        {"artifact_dir": str(artifact_dir),
                         "expected": str(canonical_build)})
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
    sfx = f"-try{attempt}" if attempt is not None else ""
    artifact = artifact_dir / f"TURN-{_slug(linkage)}{sfx}.md"
    gate_artifact = artifact_dir / f"GATE-{step_name}{sfx}.md"
    gate_full = artifact_dir / f"GATE-{step_name}{sfx}.md-FULL.log"
    evidence = EvidenceSet(artifact, {})
    evidence.precheck()
    outcome, claude_exit, attributed, commit_sha, detail = "FAILURE", None, [], None, ""
    gate_evidence_ours = True
    import uuid as _uuid
    from . import abort as _abort
    cancel = threading.Event()
    nonce = _uuid.uuid4().hex
    _abort.write_turn_nonce(service.state_dir, nonce)
    stop = threading.Event()
    beat = threading.Thread(target=_keepalive,
                            args=(service, token, stop, cancel, activity), daemon=True)
    beat.start()
    def _boundary(phase: str) -> None:
        service.heartbeat()
        if service.stop_check()["stop_requested"]:
            _stopped_suspend(service, token, phase)
            raise TurnError("STOPPED", {"phase": phase})

    try:
        _boundary("COMPOSED")
        # -- LAUNCHED -----------------------------------------------------
        _set_phase(service, "LAUNCHED")
        prompt = Path(prompt_file).read_text(encoding="utf-8")
        argv = launch_argv(turn, prompt=prompt, claude_bin=claude_bin)
        run = runner or SubprocessRunner()
        result = run.run(argv, cwd=str(root), timeout=timeout,
                         env=launch_env(turn), cancel=cancel)
        claude_exit = result.exit_code
        append_terminal_seal(turn.event_log, turn.secret)
        events = read_events(turn.event_log)
        _boundary("LAUNCHED")  # honor a stop during launch on ANY exit
        pre_gate_changes = {p for _s, p in changed_paths(root)}

        if getattr(result, "aborted", False):
            outcome, detail = "ABORTED", "abort requested (agent killed)"
        elif result.timed_out:
            outcome = "TIMEOUT"
        elif result.exit_code not in (0, None):
            outcome, detail = "FAILURE", f"claude exited {result.exit_code}"
        else:
            # -- GATED (keep-alive still running; heartbeat + stop check) --
            _set_phase(service, "GATED")
            from .evidence import EvidenceConflict
            gate_conflict = False
            try:
                gate = run_gate(root, command=gate_command, declared_in=declared_in,
                                artifact=gate_artifact, linkage=step, runner=run,
                                cancel=cancel)
                gate_outcome = gate["outcome"]
            except EvidenceConflict:
                # The agent pre-created the supervisor's gate evidence path — a
                # confinement breach, not a gate result. It is NOT exempted and
                # NEVER committed.
                gate_conflict, gate_outcome = True, "GATE_CONFLICT"
                gate_evidence_ours = False
            except Exception as exc:  # noqa: BLE001
                gate_outcome = f"GATE_ERROR:{exc}"
            gate_effects = [str(root / p) for _s, p in changed_paths(root)
                            if p not in pre_gate_changes]

            if cancel.is_set():  # an abort was claimed during the gate
                outcome, detail = "ABORTED", "abort requested during gate"
                body = _log_body(turn.event_log)
                evidence.write_main(header(outcome, claude_exit, linkage,
                                           base_sha=base_sha, attributed=0,
                                           detail=detail), body)
                stop.set(); beat.join(timeout=2)
                _abort.clear_turn_nonce(service.state_dir)
                turn.cleanup()
                op = _operational_commit(root, base_sha,
                                         [str(artifact.relative_to(root))],
                                         linkage=linkage, outcome="ABORTED",
                                         token=token, service=service)
                _stopped_suspend(service, token, "GATED", reason="abort requested")
                _abort.clear_claimed(service.state_dir, activity_id=activity["id"],
                                     activity_epoch=activity["epoch"], turn_token=token)
                return {"ok": False, "outcome": "ABORTED", "files_committed": [],
                        "artifact": str(artifact), "commit": op, "detail": detail}

            # -- VERIFIED (stop check BEFORE the checkpoint) --------------
            _boundary("GATED")
            _set_phase(service, "VERIFIED")
            exemption_files = EXEMPTIONS + [
                str(artifact.relative_to(root)), str(step_file.relative_to(root))]
            if not gate_conflict:  # only exempt supervisor-written gate evidence
                exemption_files += [str(gate_artifact.relative_to(root)),
                                    str(gate_full.relative_to(root))]
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

        # Final abort check: an abort claimed during verify/attribute/evidence
        # (the keepalive is still running) overrides the outcome — the evidence
        # records ABORTED and the COMMITTED handler suspends without committing.
        if cancel.is_set() and outcome not in ("ABORTED", "TIMEOUT"):
            outcome, attributed, detail = "ABORTED", [], "abort requested during verify"
        body = _log_body(turn.event_log)
        evidence.write_main(header(outcome, claude_exit, linkage, base_sha=base_sha,
                                   attributed=len(attributed), detail=detail), body)
    except BaseException:
        stop.set(); beat.join(timeout=2)
        _abort.clear_turn_nonce(service.state_dir)
        evidence.cleanup_orphans()
        turn.cleanup()
        raise
    stop.set(); beat.join(timeout=2)
    _abort.clear_turn_nonce(service.state_dir)
    turn.cleanup()

    # ABORTED suspends (app layer releases the lock), then reconciles the
    # claimed abort marker — idempotent recovery point.
    if outcome == "ABORTED":
        # commit the TURN evidence operationally BEFORE clearing the marker so
        # there is a durable ABORTED record even if we crash right after; the
        # activity is still ACTIVE here (suspend happens next), so this is a
        # fenced op-commit.
        op = _operational_commit(root, base_sha, [str(artifact.relative_to(root))],
                                 linkage=linkage, outcome="ABORTED", token=token,
                                 service=service)
        _stopped_suspend(service, token, "LAUNCHED", reason="abort requested")
        _abort.clear_claimed(service.state_dir, activity_id=activity["id"],
                             activity_epoch=activity["epoch"], turn_token=token)
        return {"ok": False, "outcome": "ABORTED", "files_committed": [],
                "artifact": str(artifact), "commit": op, "detail": detail}

    # -- COMMITTED (supervisor only) --------------------------------------
    # A stop that arrived during verify/attribute/evidence (for ANY outcome)
    # suspends instead of committing product OR operational evidence — the
    # mediator resumes with /regent (the evidence artifact is on disk,
    # uncommitted, and the worktree is left for inspection).
    if service.stop_check()["stop_requested"]:
        _stopped_suspend(service, token, "PRE_COMMIT")
        raise TurnError("STOPPED", {"phase": "PRE_COMMIT", "outcome": outcome})
    _set_phase(service, "COMMITTING")
    if outcome == "TURN_OK":
        _write_step_file(step_file, step_name, attributed, base_sha, linkage,
                         gate_command)
        product_evidence = [str(step_file.relative_to(root)),
                            str(artifact.relative_to(root)),
                            str(gate_artifact.relative_to(root))]
        if gate_full.exists():
            product_evidence.append(str(gate_full.relative_to(root)))
        commit_sha = _supervisor_commit(root, base_sha, attributed + product_evidence,
                                        step=step, linkage=linkage, token=token,
                                        service=service)
    else:
        extra = ([str(p.relative_to(root)) for p in (gate_artifact, gate_full)
                  if p.exists()] if gate_evidence_ours else [])
        commit_sha = _operational_commit(
            root, base_sha, [str(artifact.relative_to(root))] + extra,
            linkage=linkage, outcome=outcome, token=token, service=service)
    _set_phase(service, "COMMITTED")

    return {"ok": outcome == "TURN_OK", "outcome": outcome,
            "files_committed": attributed if outcome == "TURN_OK" else [],
            "artifact": str(artifact), "commit": commit_sha, "detail": detail}


def _keepalive(service, token, stop, cancel=None, activity=None) -> None:
    from . import abort as _abort
    beats = 0
    while not stop.wait(1):  # ~1s cadence for abort responsiveness
        beats += 1
        if cancel is not None and activity is not None:
            claimed = _abort.claim_matching_abort(
                service.state_dir, service.audit,
                activity_id=activity["id"], activity_epoch=activity["epoch"],
                turn_token=token)
            if claimed is not None:
                cancel.set()
                return
        if beats % 60 == 0:  # heartbeat every ~60s (well under stale 1800s)
            try:
                service.lock.heartbeat(token)
            except Exception:  # noqa: BLE001 — a lost token surfaces at commit
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


def _operational_commit(root: Path, base_sha: str, paths: list[str], *,
                        linkage: str, outcome: str, token: str,
                        service: ActivityService) -> str | None:
    """Same fencing+CAS discipline as the product commit: private index,
    token re-check and update-ref <new> <old> in the smallest window."""
    index = Path(tempfile.mktemp(prefix="regent-index-"))
    env = dict(os.environ, GIT_INDEX_FILE=str(index))
    try:
        _git(root, "read-tree", "HEAD", env=env)
        for path in paths:
            _git(root, "add", "--", path, env=env)
        base_tree = _git(root, "rev-parse", "HEAD^{tree}").strip()
        tree = _git(root, "write-tree", env=env).strip()
        if tree == base_tree:
            return None
        msg = (f"turn(PLAN-004): {outcome} evidence (no product)\n\n"
               f"Regent-Turn: {linkage}")
        commit = _git(root, "commit-tree", tree, "-p", base_sha, "-m", msg,
                      env=env).strip()
        assert_turn_token(service.store.load(), token)
        if _git(root, "rev-parse", "HEAD").strip() != base_sha:
            raise TurnError("CONFLICT", {"reason": "HEAD moved since baseline"})
        _git(root, "update-ref", "-m", "regent turn (op)", "HEAD", commit, base_sha,
             env=env)
        _git(root, "reset", "--mixed", "HEAD")
        return commit
    finally:
        try:
            index.unlink()
        except OSError:
            pass
