---
name: regent-stop
description: Safely stop/suspend the regent activity in progress (brainstorm round, plan deliberation, or build) so it can be resumed later with /regent. Use when the owner says /regent-stop, "para", "suspende", or asks to stop regent work.
---

# /regent-stop — safe stop of the current activity

> **Capability level: v0 (file-driven).** There is no daemon, lock or in-flight abort yet:
> stopping means recording a durable suspension marker at the next message boundary. Do not
> claim atomic cancellation — immediate interruption of a running step is the user's Esc,
> not this command.

## Steps

1. Locate the state roots and the single open activity exactly as `/regent` does (its
   sections 0–1: brainstorm round without DECISION, plan without APPROVAL, or build without
   CONCLUSION; legacy PT scheme respected; ambiguity = report and stop, touch nothing).
   Nothing open → report that the state is clean (nothing to stop) and stop.
2. Write `SUSPENSION.md` (legacy hosts: `SUSPENSAO.md`) inside the open activity dir with:
   timestamp, reason given by the owner (ask if not stated), and the resume checkpoint —
   for brainstorm/plan: which artifact was pending; for build: the current step and its
   phase (IMPLEMENTING / GATE-RED / GATE-GREEN-UNCOMMITTED / COMMITTED) plus any in-flight
   consultation outcome.
3. Persist everything already produced — never delete partial artifacts; they are evidence.
   A build step in IMPLEMENTING phase keeps its uncommitted worktree changes untouched;
   record in SUSPENSION.md that the worktree is intentionally dirty.
4. Make an operational commit of ONLY regent-owned paths (`.regent/`, the `.claude/` symlink
   integrations, and — in the regent repo only — `docs/`). Never commit host code from here:
   deliberate build-step commits belong to `/regent` (REQ-005). A failed commit does NOT
   prevent the suspension — report it and leave the commit pending.
5. Confirm to the owner: what was suspended, at which checkpoint, and that `/regent`
   resumes it.
