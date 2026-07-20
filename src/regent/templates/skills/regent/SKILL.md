---
name: regent
description: Start or resume the regent activity in this repo — brainstorm (adversarial deliberation round), plan (deliberated plan with steps and gates) or build (execute an approved plan step by step). Single state-driven entry point. Use when the owner says /regent, "retome", "próxima rodada", or asks to continue regent work.
---

# /regent — start or resume the current activity

> **Capability level: v0 (file-driven).** State detection is based on files only. There is
> no `control.json`, no turn lock, no daemon, no confined execution and no atomic abort yet.
> Immediate interruption of a running step is the user's Esc; `/regent-stop` suspends at the
> next boundary. Do not claim capabilities beyond this file.

## 0. Locate the state roots (deterministic, never guess)

- Host projects, current scheme: `ROUNDS = .regent/brainstorm/rounds/` (dirs `ROUND-NNN/`,
  English artifact names) and `PLANS = .regent/plans/` (dirs `PLAN-NNN/`).
- Host projects, legacy scheme (pre-0.2 seeds): `.regent/brainstorm/rodadas/` with
  `RODADA-NNN/` and PT artifact names (PERGUNTA/RESPOSTA-CLAUDE/OPINIAO-CODEX-N/
  REPLICA-CLAUDE/DECISAO/SUSPENSAO). A legacy host keeps operating on its PT scheme for
  brainstorm; `plan`/`build` ALWAYS use the English `PLANS` scheme.
- If BOTH `rounds/` and `rodadas/` exist non-empty → corrupted state: report and STOP with
  manual migration instructions (default-deny; never auto-migrate).
- The regent product repo itself keeps its own deliberation in `docs/brainstorm/rodadas/`
  (dogfood location, PT names) — delimited by that fixed path only.

Artifact names below use the English scheme; on a legacy host map brainstorm names to PT.

## 1. Detect state (never guess)

Open activities (at most ONE may exist):
- **brainstorm**: a `ROUND-NNN/` without `DECISION.md`.
- **planning**: a `PLAN-NNN/` without `APPROVAL.md`.
- **building**: a plan whose `APPROVAL.md` has `status: APPROVED`, with `build/` started and
  no `build/CONCLUSION.md`.

An APPROVED plan with no `build/` is NOT open — it is a build candidate awaiting the owner's
explicit `/regent build`. More than one open activity, or otherwise ambiguous/corrupted
state → report and STOP. Never repair silently, never pick one arbitrarily.

## 2. Decide by command argument × state

- **Bare `/regent` + exactly one open activity** → resume it (sections 3–5).
- **Bare `/regent` + nothing open** → report state (last closed round/plan, build
  candidates) and ask what to start. Never start anything implicitly.
- **`brainstorm "<question>"` / `plan "<goal>"` + nothing open** → create the next
  `ROUND-NNN/` (with `QUESTION.md`) or `PLAN-NNN/` (with `REQUEST.md`), owner's words
  verbatim, and proceed.
- **`build`** → requires a build candidate: exactly one → start/resume it; more than one →
  demand explicit selection `/regent build PLAN-NNN`; none → error (never build without an
  APPROVED plan).
- **Any mode argument + a DIFFERENT open activity** → error explaining the state. Never
  ignore the argument silently; never create a second activity.

## 3. Brainstorm mode

Loop: owner asks → Claude responds → advisor opines (explicit CONCORDA/DISCORDA verdict) →
CONCORDA: Claude executes; DISCORDA: one rebuttal cycle; persistent divergence → the owner
arbitrates. Round content in the mediator's language (REQ-002).

Resume at the first missing artifact: `QUESTION.md` → `CLAUDE-RESPONSE.md` →
`ADVISOR-OPINION-1.md` → (if DISCORDA) `CLAUDE-REBUTTAL.md` → `ADVISOR-OPINION-2.md` →
`DECISION.md` (what was decided, who closed it, what was executed), then execute and make an
**operational commit** (regent-owned paths only). If resuming a suspended activity, read
`SUSPENSION.md` first, delete it after resuming.

## 4. Plan mode

A plan is a deliberated artifact, driven like a round:
1. `REQUEST.md` — the owner's goal, verbatim.
2. `PLAN.md` — goal, scope in/out, **numbered steps, each with an acceptance criterion and
   an executable gate command**, risks. Content in the host's native language.
3. `ADVISOR-REVIEW-1.md` — advisor verdict; one rebuttal cycle (`CLAUDE-REBUTTAL.md` +
   `ADVISOR-REVIEW-2.md`); persistent divergence → owner arbitrates.
4. `APPROVAL.md` — structured: `status: APPROVED | REJECTED | CANCELLED`, actor (consensus /
   owner), date. Without APPROVED status the plan is not executable. The owner may cancel a
   plan at any time (record status + reason).

## 5. Build mode — execute an APPROVED plan, step by step

**Baseline.** On build start write `build/BASELINE.md`: the base SHA (`git rev-parse HEAD`)
and the plan reference. The final review diff is exactly `BASE-SHA..HEAD`.

**Per step (in plan order):**
1. Worktree MUST be clean at step start; dirty → report and STOP (default-deny — never
   absorb pre-existing user changes).
2. Implement the step.
3. Run the step's gate command for real; record its output. Red gate → fix and re-run, or
   suspend; a red gate NEVER proceeds and NEVER commits.
4. Write `build/STEP-NN.md`: base SHA of the step, files touched, gate output. NO commit
   hash inside (it cannot know it — see trailer below).
5. Commit deliberately: stage file-by-file ONLY the paths attributable to the step (+ the
   step's regent artifacts), inspect the staged diff, fail without committing if anything
   unattributable is staged. Commit message ends with trailer `Regent-Step: PLAN-NNN/STEP-NN`
   — the artifact↔commit link is resolved via this trailer, never via a hash in the artifact.

**Resume phases** (check trailer in `git log`, then STEP file, then worktree — in that order):
- IMPLEMENTING (dirty worktree, no gate recorded) → re-run the gate before anything; never
  trust unvalidated code.
- GATE-RED (red output recorded) → back to implementation.
- GATE-GREEN-UNCOMMITTED (STEP written, trailer absent) → re-verify gate, then commit.
  Checking the trailer BEFORE committing prevents duplicate commits.
- COMMITTED (trailer present) → step closed; advance.

**Finish:** `build/ADVISOR-REVIEW.md` — advisor reviews the full `BASE-SHA..HEAD` diff
(verdict + findings). Then `build/CONCLUSION.md`, structured: `status: ACCEPTED |
ACCEPTED-WITH-RESERVATIONS | REJECTED`, actor, pending items. An adverse review or a
non-arbitrated divergence can NEVER become acceptance. Any post-review fix invalidates the
review: re-run the affected gate AND a new advisor consultation before concluding.

## 6. Advisor consultations (shared contract — REQ-003 §5)

Invocation (read-only, never writes, never holds the turn):
`codex --ask-for-approval never --sandbox read-only exec --cd <repo> -o <tmpfile> "<prompt>"`

Every consultation persists its full evidence tuple: the complete prompt in
`<ARTIFACT>-PROMPT.md` next to the response artifact, and the response artifact opening with
a structured header — `outcome: SUCCESS|TIMEOUT|FAILURE|CANCELLED`, `exit_code`,
`timestamp`, `linkage` (ROUND-NNN / PLAN-NNN[/build]). Fail-closed: a non-SUCCESS outcome
never advances the activity; retry means a NEW recorded consultation.
