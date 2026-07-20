---
name: regent-stop
description: Safely stop/suspend the regent activity in progress (brainstorm round, planning, implementation) so it can be resumed later with /regent. Use when the owner says /regent-stop, "para o brainstorm", "suspende a rodada", or asks to stop regent work.
---

# /regent-stop — safe stop of the current activity

> **Capability level: v0 (file-driven).** There is no daemon, lock or in-flight abort yet:
> stopping means recording a durable suspension marker at the next message boundary. Do not
> claim atomic cancellation — immediate interruption of a running step is the user's Esc,
> not this command.

## Steps

1. Detect the open round: `docs/brainstorm/rodadas/RODADA-NNN/` without `DECISAO.md`.
   - Nothing open → report that the state is clean (nothing to stop) and stop.
   - Ambiguous state → report the anomaly; do not modify anything.
2. Write `SUSPENSAO.md` in the open round with: timestamp, reason given by the owner (ask if
   not stated), which artifact/step was pending (the resume checkpoint), and any partial
   output worth keeping (e.g. an advisor consultation already saved).
3. Persist everything already produced — never delete partial artifacts; they are evidence.
4. Commit ONLY regent-owned paths (`docs/`, `.regent/`, `.claude/` symlinks). A failed
   commit does NOT prevent the suspension — report it and leave the commit pending.
5. Confirm to the owner: what was suspended, where it will resume from (`/regent`).
