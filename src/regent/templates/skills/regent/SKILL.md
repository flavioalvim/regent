---
name: regent
description: Start or resume the regent activity in this repo (brainstorm round, planning, implementation). Single state-driven entry point — detects what is open and drives the next step. Use when the owner says /regent, "retome o brainstorm", "próxima rodada", or asks to continue regent work.
---

# /regent — start or resume the current activity

> **Capability level: v0 (file-driven).** State detection is based on round files only.
> There is no `control.json`, no turn lock, no daemon, no atomic abort and no structured
> checkpoint yet — those arrive with REQ-004's full implementation. Do not claim
> capabilities beyond this file.

## 0. Locate the rounds directory (deterministic, never guess)

- Host projects: `ROUNDS = .regent/brainstorm/rodadas/` (created on first use).
- The regent product repo itself keeps its own deliberation in `docs/brainstorm/rodadas/`
  (legacy dogfood location).
- Resolution: if `.regent/brainstorm/` exists use it; else if `docs/brainstorm/` exists use
  that; if BOTH exist, report the ambiguity and STOP; if neither, this is a fresh host —
  `ROUNDS = .regent/brainstorm/rodadas/`.

## 1. Detect state (never guess)

- Open round = a `ROUNDS/RODADA-NNN/` directory WITHOUT `DECISAO.md`.
- Suspended round = an open round containing `SUSPENSAO.md`.
- If the state is ambiguous or corrupted (two open rounds, missing PERGUNTA.md), REPORT the
  anomaly and STOP. Default-deny: never repair silently, never pick one arbitrarily.

## 2. Decide by command argument × state

- **No argument + exactly one open/suspended round** → resume it (step 3).
- **No argument + nothing open** → report the state (last closed round, PRD requirement log)
  and ask what to start. Never start anything implicitly.
- **`brainstorm "<question>"` + nothing open** → create the next `ROUNDS/RODADA-NNN/` with
  `PERGUNTA.md` (owner's question verbatim) and proceed to step 3.
- **`brainstorm ...` + a DIFFERENT round already open** → error explaining the open state.
  Never ignore the argument silently; never create a second activity.
- **`plan` / `build`** → not available at v0; say so explicitly and point to REQ-004.

## 3. Drive the round (the loop protocol is THIS section — self-contained)

Loop: owner asks → Claude responds → Codex (advisor) opines with an explicit
CONCORDA/DISCORDA verdict → if CONCORDA, Claude executes; if DISCORDA, one rebuttal cycle;
persistent divergence → the owner arbitrates. Round language: the mediator's (REQ-002).

Resume at the first missing artifact, in order:
1. `RESPOSTA-CLAUDE.md` — Claude's reasoned position + concrete proposal.
2. `OPINIAO-CODEX-1.md` — headless advisor consultation, saved verbatim:
   `codex --ask-for-approval never --sandbox read-only exec --cd <repo> -o <tmpfile> "<prompt>"`
   (prompt tells Codex which files to read and to end with a line containing only
   CONCORDA or DISCORDA).
3. If DISCORDA → `REPLICA-CLAUDE.md` then `OPINIAO-CODEX-2.md` (one rebuttal cycle max).
4. Persistent divergence → the owner arbitrates (they are mediating live).
5. `DECISAO.md` — what was decided, who closed it, what was executed. Then execute it and
   commit ONLY regent-owned paths (`.regent/`, the `.claude/` symlink integrations, and —
   in the regent repo only — `docs/`) — never unrelated host content. A failed commit does
   not undo the round; report it and leave it pending.

If resuming a suspended round, read `SUSPENSAO.md` first, delete it after resuming, and
continue from the recorded pending step.
