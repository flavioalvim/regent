---
name: regent-stop
description: Safely stop/suspend the regent activity in progress (brainstorm round, plan deliberation, or build) so it can be resumed later with /regent. Use when the owner says /regent-stop, "para", "suspende", or asks to stop regent work.
---

# /regent-stop — safe stop of the current activity

> **Capability level: v1 (control-backed).** The stop channel is the durable
> stop-request in `.regent/control.json`; suspension is a CAS transition with a full
> resume payload. Still absent: daemon and real in-flight `--abort` — immediate
> interruption of a running step is the user's Esc, and this command normalizes state at
> the next message boundary.

## Steps

1. `regent status`. If `control` is `"uninitialized"` or `"corrupt"` → report (legacy v0
   hosts: fall back to the v0 file-driven suspension rules) and stop. If
   `control.activity` is null → report clean state, nothing to stop. If already
   `SUSPENDED` → report where it is suspended (checkpoint) and stop.
2. Record the durable request: `regent stop request` (mediator channel; a suspended
   activity answers `noop: true`). This alone already makes any running `/regent` flow
   suspend at its next boundary — if one is running, let it.
3. If YOU are normalizing (no flow running): persist any partial artifacts (they are
   evidence — never delete), then
   `regent activity suspend --checkpoint "<exact resume point>" --reason "<owner's
   reason — ask if not stated>" [--in-flight "<what was interrupted>"]
   --evidence <path> [--evidence <path>...]`.
4. Make an operational commit of ONLY regent-owned paths (`.regent/` including
   `control.json` and `protocol/audit.jsonl`, plus — in the regent repo only — `docs/`).
   Never commit host code from here: deliberate build-step commits belong to `/regent`
   (REQ-005). A failed commit does NOT prevent the suspension — report it and leave the
   commit pending.
5. Confirm to the owner: what was suspended, the exact checkpoint, and that `/regent`
   resumes it (`regent activity resume` returns the checkpoint and verifies evidence).

Error codes you may see: `NO_ACTIVITY` (nothing to stop), `NOT_ACTIVE` (already
suspended), `TOKEN_MISMATCH`/`LOCK_SUSPECT` (mediated recovery — see /regent §0),
`CORRUPT_CONTROL` (stop and report).
