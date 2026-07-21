"""`regent loop run` — chains supervised turns over an approved build plan
(PLAN-005 STEP-02). Deterministic driver: recompute the current step from disk,
run one confined turn, map the outcome to a terminal condition. No own state
(disk is the truth); no auto-retry; a mid-agent turn is never resumed.
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

from ..activity import ActivityService
from ..protocol.control import _FlockMutex, MutationMutexBusy
from .evidence import EvidenceSet, EvidenceConflict as _EvidenceConflict, header
from .turn import TurnError, run_turn, _git, _slug

# Outcome → loop stop condition (the complete map, PLAN-005 v3 §6).
_HALT_OUTCOMES = {"GATE_RED", "TURN_VIOLATION", "TURN_TAMPERED", "FAILURE", "TIMEOUT"}


class LoopError(Exception):
    def __init__(self, code: str, detail: dict) -> None:
        super().__init__(code)
        self.code, self.detail = code, detail


def _committed_steps(root: Path, plan_id: str) -> set[str]:
    """Steps proven done: a commit reachable from HEAD whose message has the
    exact `Regent-Step: PLAN-NNN/STEP-NN` trailer AND that touched
    build/STEP-NN.md AND the file exists in HEAD."""
    done = set()
    build_rel = f".regent/plans/{plan_id}/build"
    out = _git(root, "log", "--format=%H", f"--grep=^Regent-Step: {re.escape(plan_id)}/",
               "-E")
    for sha in out.split():
        msg = _git(root, "log", "-1", "--format=%B", sha)
        for m in re.finditer(rf"^Regent-Step: {re.escape(plan_id)}/(STEP-\d+)$",
                             msg, re.M):
            step = m.group(1)
            step_path = f"{build_rel}/{step}.md"
            touched = _git(root, "show", "--name-only", "--format=", sha)
            if step_path in touched.split() and _file_in_head(root, step_path):
                done.add(step)
    return done


def _file_in_head(root: Path, rel: str) -> bool:
    r = subprocess.run(["git", "-C", str(root), "cat-file", "-e", f"HEAD:{rel}"],
                       capture_output=True)
    return r.returncode == 0


def _declared_steps(plan_text: str) -> list[str]:
    return sorted(set(re.findall(r"STEP-\d+", plan_text)),
                  key=lambda s: int(s.split("-")[1]))


def _step_gate(plan_text: str, step_name: str) -> str | None:
    # Boundary = next step HEADING line, so a gate command containing a step
    # name (e.g. a path) is not truncated (matches turn._step_gate).
    m = re.search(rf"{re.escape(step_name)}\b(.*?)(?=\n#+[^\n]*STEP-\d+|\Z)",
                  plan_text, re.S)
    if not m:
        return None
    g = re.search(r"\*\*Gate:\*\*\s*`([^`]+)`", m.group(1))
    return g.group(1) if g else None


def _attempt_number(artifact_dir: Path, step_name: str) -> int:
    """K = max existing tryN for this step + 1 (not a count)."""
    existing = [int(m.group(1)) for p in artifact_dir.glob(f"TURN-*{step_name}*try*.md")
                for m in [re.search(r"try(\d+)", p.name)] if m]
    return (max(existing) + 1) if existing else 1


def _approval_status(root: Path, plan_id: str) -> str | None:
    path = root / ".regent" / "plans" / plan_id / "APPROVAL.md"
    try:
        m = re.search(r"^status:\s*(\S+)", path.read_text(encoding="utf-8"), re.M)
        return m.group(1) if m else None
    except OSError:
        return None


def run_loop(root: Path, *, plan_id: str, prompt_template: Path, envelope: list[str],
             gate_envelope: list[str] | None, declared_in: Path, artifact_dir: Path,
             max_turns: int = 20, timeout: float = 900.0, claude_bin: str = "claude",
             runner=None, service: ActivityService | None = None) -> dict:
    root = Path(root).resolve()
    service = service or ActivityService(root)
    artifact_dir = (root / artifact_dir).resolve() if not Path(artifact_dir).is_absolute() \
        else Path(artifact_dir).resolve()
    if max_turns < 1:
        raise LoopError("USAGE", {"reason": "--max-turns must be >= 1"})
    template = Path(prompt_template).read_text(encoding="utf-8")

    loop_lock = _FlockMutex(service.state_dir / "loop.lock", timeout=0.5)
    try:
        loop_lock.__enter__()
    except MutationMutexBusy:
        raise LoopError("LOOP_BUSY", {"reason": "another loop run holds the loop lock"})
    turns: list[dict] = []
    condition = "COMPLETE"
    try:
      try:
        while True:
            control = service.store.load()
            activity = control.get("activity")
            if activity is None or activity["state"] != "ACTIVE" \
                    or activity["type"] != "build" or activity["id"] != plan_id:
                condition = "PLAN_NOT_EXECUTABLE"
                break
            if _approval_status(root, plan_id) != "APPROVED":
                condition = "PLAN_NOT_EXECUTABLE"
                break
            plan_text = Path(declared_in).read_text(encoding="utf-8", errors="replace")
            declared = _declared_steps(plan_text)
            done = _committed_steps(root, plan_id)
            remaining = [s for s in declared if s not in done]
            if not remaining:
                condition = "COMPLETE"
                break
            if len(turns) >= max_turns:
                condition = "MAX_TURNS"
                break
            step = remaining[0]
            gate = _step_gate(plan_text, step)
            attempt = _attempt_number(artifact_dir, step)
            prompt = template.replace("{step}", step).replace("{gate}", gate or "") \
                .replace("{plan}", plan_id)
            # write the prompt OUTSIDE the repo (state dir) — never dirty the
            # worktree that run_turn requires clean.
            prompt_file = service.state_dir / f"prompt-{step}-try{attempt}.txt"
            prompt_file.write_text(prompt, encoding="utf-8")
            try:
                result = run_turn(
                    root, prompt_file=prompt_file, envelope=envelope,
                    gate_command=gate, declared_in=declared_in, step=f"{plan_id}/{step}",
                    artifact_dir=artifact_dir, linkage=f"{plan_id}/{step}/try{attempt}",
                    gate_envelope=gate_envelope, timeout=timeout, claude_bin=claude_bin,
                    runner=runner, service=service, attempt=attempt)
            except TurnError as exc:
                condition = _EXC_TO_CONDITION.get(exc.code, "LOOP_CONFLICT")
                turns.append({"step": step, "attempt": attempt, "outcome": exc.code,
                              "commit": None})
                break
            except _EvidenceConflict:
                condition = "LOOP_CONFLICT"
                turns.append({"step": step, "attempt": attempt,
                              "outcome": "EVIDENCE_CONFLICT", "commit": None})
                break
            except OSError as exc:
                # spawn / IO failure of the turn itself → treat as a failed turn
                condition = "HALTED"
                turns.append({"step": step, "attempt": attempt,
                              "outcome": "FAILURE",
                              "detail": f"{type(exc).__name__}: {exc}", "commit": None})
                break
            except subprocess.CalledProcessError as exc:
                condition = "LOOP_CONFLICT"
                turns.append({"step": step, "attempt": attempt,
                              "outcome": f"GIT_ERROR:{exc.returncode}", "commit": None})
                break
            finally:
                try:
                    prompt_file.unlink()
                except OSError:
                    pass
            turns.append({"step": step, "attempt": attempt,
                          "outcome": result["outcome"], "commit": result.get("commit")})
            outcome = result["outcome"]
            if outcome == "TURN_OK":
                continue  # advance; recompute from disk
            if outcome == "STOPPED":
                condition = "STOPPED"
                break
            if outcome == "ABORTED":
                condition = "ABORTED"
                break
            if outcome in _HALT_OUTCOMES:
                condition = "HALTED"
                break
            condition = "LOOP_CONFLICT"
            break
      except subprocess.CalledProcessError:
        condition = "LOOP_CONFLICT"
      try:
        summary_conflict = _write_loop_evidence(root, artifact_dir, service,
                                                condition, turns)
        if summary_conflict and condition == "COMPLETE":
            condition = "LOOP_CONFLICT"  # a mandatory summary could not commit
      except subprocess.CalledProcessError:
        condition = "LOOP_CONFLICT"  # any git error in the summary is a conflict
    finally:
        loop_lock.__exit__(None, None, None)

    ok = condition == "COMPLETE"
    return {"ok": ok, "stop_condition": condition, "turns": turns, "count": len(turns)}


_EXC_TO_CONDITION = {
    "NOT_ACTIVE": "PLAN_NOT_EXECUTABLE", "CONFLICT": "LOOP_CONFLICT",
    "WORKTREE_DIRTY": "LOOP_DIRTY", "PROVENANCE": "LOOP_MISCONFIGURED",
    "STEP_MISMATCH": "LOOP_MISCONFIGURED", "ARTIFACT_OUTSIDE_REGENT": "LOOP_MISCONFIGURED",
    "STEP_ALREADY_DONE": "LOOP_MISCONFIGURED", "STOPPED": "STOPPED",
}


def _write_loop_evidence(root: Path, artifact_dir: Path, service: ActivityService,
                         condition: str, turns: list[dict]) -> None:
    slug = _slug(f"{condition}-{len(turns)}")
    artifact = artifact_dir / f"LOOP-{slug}.md"
    evidence = EvidenceSet(artifact, {})
    try:
        evidence.precheck()
    except _EvidenceConflict:  # never block on evidence naming
        artifact = artifact_dir / f"LOOP-{slug}-{len(list(artifact_dir.glob('LOOP-*')))}.md"
        evidence = EvidenceSet(artifact, {})
    body = "\n".join(
        f"- {t['step']} try{t['attempt']} → {t['outcome']}"
        + (f" ({t['commit'][:8]})" if t.get("commit") else "") for t in turns)
    evidence.write_main(header(condition, None, "loop", turns=len(turns)),
                        body or "(no turns)")
    # Summary commit through a PRIVATE index + HEAD CAS (never the shared index;
    # no accidentally-staged files). Fenced when a token exists (ACTIVE); a plain
    # CAS commit when SUSPENDED (no token) — both under the loop lock still held.
    import os as _os
    import tempfile as _tf
    from ..protocol.control import assert_turn_token, NotLockOwner
    control = service.store.load()
    activity = control.get("activity")
    token = (activity.get("turn") or {}).get("token") if activity else None
    rel = str(artifact.relative_to(root))
    base_sha = _git(root, "rev-parse", "HEAD").strip()
    index = Path(_tf.mktemp(prefix="regent-loop-index-"))
    env = dict(_os.environ, GIT_INDEX_FILE=str(index))
    try:
        _git(root, "read-tree", "HEAD", env=env)
        _git(root, "add", "--", rel, env=env)
        base_tree = _git(root, "rev-parse", "HEAD^{tree}").strip()
        tree = _git(root, "write-tree", env=env).strip()
        if tree == base_tree:
            return False
        msg = (f"loop(PLAN-005): {condition} summary ({len(turns)} turns)\n\n"
               f"Regent-Loop: {condition}")
        commit = _git(root, "commit-tree", tree, "-p", base_sha, "-m", msg,
                      env=env).strip()
        # Fencing + CAS in the SMALLEST window right before advancing HEAD.
        if token is not None:
            try:
                assert_turn_token(service.store.load(), token)
            except NotLockOwner:
                return True  # taken over — summary NOT committed (conflict)
        if _git(root, "rev-parse", "HEAD").strip() != base_sha:
            return True  # HEAD moved (raced with resume) — conflict
        _git(root, "update-ref", "-m", "regent loop summary", "HEAD", commit, base_sha,
             env=env)
        _git(root, "reset", "--mixed", "HEAD")
        return False
    finally:
        try:
            index.unlink()
        except OSError:
            pass
