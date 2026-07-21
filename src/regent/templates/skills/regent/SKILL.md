---
name: regent
description: Start or resume the regent activity in this repo — brainstorm (adversarial deliberation round), plan (deliberated plan with steps and gates) or build (execute an approved plan step by step). Control-backed, state-driven single entry point. Use when the owner says /regent, "retome", "próxima rodada", or asks to continue regent work.
---

# /regent — start or resume the current activity

> **Capability level: v1 (control-backed).** Activity STATE lives in
> `.regent/control.json` (transactional CAS + executor turn lock), driven through the
> `regent` CLI; content artifacts (round/plan files) stay on disk. Still absent (future
> phases): conduction daemon, confined execution, real `--abort`. Do not claim them.

## 0. Read the state — `regent status`

Run `regent status` (pure JSON). Decide from it:
- `control: "uninitialized"` → if `.regent/brainstorm/rodadas/` has PT-named artifacts,
  this is a LEGACY v0 host: keep operating file-driven (v0 rules) and tell the owner to
  run `regent init` to upgrade. Otherwise: error — point to `regent init`.
- `control: "corrupt"` → report and STOP (`regent doctor` shows it too). Touch nothing.
- `workspace.verdict` is the executable control×files matrix. Only `OK`, `SUSPENDED_OK`
  and `IDLE_CLEAN` proceed. Anything else (`ORPHAN_NO_DIR`, `ORPHAN_WITH_OTHER_OPEN`,
  `SUSPENDED_ORPHAN`, `TYPE_MISMATCH`, `SECOND_ARTIFACT`, `TERMINAL_EXISTS`,
  `MULTIPLE_OPEN`, `LEGACY_OPEN_ARTIFACT`, `MULTIPLE_SCHEMES`) → report the verdict and
  ASK THE MEDIATOR.
  Never adopt, repair or delete silently.
- `lock` problems surface as error codes when you act: `LOCK_SUSPECT` (or an ACTIVE
  control with a free lock) → the recovery is MEDIATED: ask the owner, then
  `regent activity takeover --reason "<why>"`. `TOKEN_MISMATCH` → stop and ask.

## 1. Decide by command argument × state (REQ-004 §2, over `status`)

- **Bare `/regent`** + `activity.state == "SUSPENDED"` → resume (section 2). + `activity
  == null` and nothing open → report state and ask; NEVER start implicitly. + `activity
  ACTIVE` → continue it (section 3).
- **`brainstorm "<question>"` / `plan "<goal>"`** + idle → create the next `ROUND-NNN/`
  (with `QUESTION.md`) or `PLAN-NNN/` (with `REQUEST.md`), owner's words verbatim, then
  `regent activity start --type brainstorm|plan --id <DIR-NAME>` and drive it.
- **`build [PLAN-NNN]`** + idle → candidate = APPROVED plan without concluded build;
  exactly one → `regent activity start --type build --id PLAN-NNN`; several → demand the
  explicit id; none → error.
- **Any mode argument while a DIFFERENT activity is open** → error explaining the state
  (`ACTIVITY_OPEN`). Never ignore the argument silently; never create a second activity.

## 2. Resume

`regent activity resume` returns the recorded `checkpoint` (and `missing_evidence` — if
non-empty, report it before continuing). Continue exactly at that checkpoint.

## 3. Drive the activity — with stop/heartbeat boundaries

At EVERY named boundary — before producing each round/plan artifact, and between the
phases of each build step (implement → gate → record → commit) — run:
`regent stop check` and `regent activity heartbeat`.
If `stop_requested` is true (the request carries `reason` — use it): finish ONLY the
current sub-step's evidence, then
`regent activity suspend --checkpoint "<exact resume point>" --reason "<from request>"
[--in-flight "<what was running>"] --evidence <path> [--evidence <path>...]` and confirm
to the owner. The checkpoint string must be precise enough for section 2 to resume from.

**Brainstorm round** (content flow unchanged): `QUESTION.md` → `CLAUDE-RESPONSE.md` →
`ADVISOR-OPINION-1.md` (advisor consultation, evidence tuple per REQ-003 §5) → if
DISCORDA one rebuttal cycle → `DECISION.md`, execute it, then
`regent activity conclude --status DECIDED` + operational commit (regent-owned paths).

**Plan** : `REQUEST.md` → `PLAN.md` (numbered steps, each with acceptance criterion and
executable gate) → advisor review (+1 rebuttal cycle) → `APPROVAL.md`
(`status: APPROVED|REJECTED|CANCELLED` + actor) → `regent activity conclude --status
<approval status>` + operational commit.

**Build** — two ways to execute a step. **Confined (preferred when the step is bounded to
files):** `regent turn run --prompt-file <task> --envelope <path> [--envelope ...]
--gate-command "<step gate>" --declared-in <PLAN.md> --step PLAN-NNN/STEP-NN
--artifact-dir <build dir under .regent> --linkage PLAN-NNN/STEP-NN` — launches a confined
`claude -p` that may only write inside the envelope (hook denies the rest), then the
supervisor verifies (git-proven attribution), runs the gate, and commits with
`Regent-Step`/`Regent-Turn` trailers. The agent never commits; a violation/tamper/red gate
never produces a product commit. **Manual (this session, for exploratory steps):** baseline
→ per step: clean worktree
(the exempted operational files `control.json`/`audit.jsonl` may be dirty — they are
staged into the commit that closes the current boundary; record `control.version` from
`regent status` at step start, and BEFORE staging them run `regent control explain --since-version <o valor registrado>`:
exit 0 = explained operational churn, `UNATTRIBUTABLE` = the step commit MUST fail) →
implement → run the gate MECHANIZED:
`regent gate run --command "<gate from the plan>" --declared-in <PLAN.md path>
--artifact build/GATE-NN[-tryM].md --linkage PLAN-NNN/STEP-NN` (the command must appear
verbatim in the plan — `PROVENANCE` otherwise; `GATE_RED`/`TIMEOUT` never proceed and
never commit; a retry uses a NEW artifact name) →
`build/STEP-NN.md` → deliberate commit with trailer `Regent-Step: PLAN-NNN/STEP-NN` →
final advisor review over `BASE-SHA..HEAD` → `build/CONCLUSION.md` (status + actor) →
`regent activity conclude --status <conclusion status>`.

## 4. Advisor consultations (shared contract — REQ-003 §5, mechanized)

Write the full prompt to a file, then:
`regent advisor consult --prompt-file <path> --artifact <ARTIFACT>.md --linkage
<ROUND-NNN|PLAN-NNN[/STEP-NN]> [--expect-verdict "<regex>"]`
The command persists the whole evidence pair (structured header + byte-identical prompt
copy) on EVERY outcome, enforces the read-only sandbox, and is fail-closed: exit ≠0
(`ADVISOR_FAILED`, `ADVISOR_UNAVAILABLE`) never advances the activity; retry = a NEW
consultation with a NEW artifact name (evidence is never overwritten — `CONFLICT`).
Never invoke the codex CLI directly.

## 5. Error codes you will see (exact)

`UNINITIALIZED` → run `regent init`. `ACTIVITY_OPEN`/`NO_ACTIVITY`/`NOT_ACTIVE`/
`NOT_SUSPENDED` → the state disagrees with the request; report it. `LOCK_SUSPECT`/
`LOCK_HELD` → mediated takeover path. `TOKEN_MISMATCH` → fencing divergence; mediator
decides. `CONFLICT`/`BUSY` → retry once, then report. `CORRUPT_CONTROL` → stop, report.
