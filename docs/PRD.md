# regent — Product Requirements Document

**regent** conducts autonomous work and mediated adversarial deliberation, pluggable into
any host project. It runs inside the **Claude Code CLI** (the execution runtime); **Codex**
participates strictly as an **advisor** (read-only consultations recorded as evidence); a
**human mediator** governs decisions. Extracted from the tool proven end-to-end in the
ArtNFT project (IMP-003: first product batch fully conducted by the daemon, deliberated,
accepted and deployed to production).

This PRD is the product's requirements record. Each requirement traces to a deliberation
round under `docs/brainstorm/rodadas/` (deliberation content is written in the mediator's
language, per REQ-002).

Status: **pre-extraction** — scope closed 2026-07-20 (`docs/ESCOPO.md`); requirements below
govern the extraction.

## Naming

Decided in RODADA-001 (owner-ratified): product name **regent**; GitHub repo
`flavioalvim/regent`; CLI and Python import `regent`; host directory `.regent/`; PyPI package
`regent-cli` (plain `regent` is taken; only relevant if/when published).

## Requirements

### REQ-001 — Host footprint: everything under `.regent/`

*Source: RODADA-001 (owner requirement + Codex objections 2–3 incorporated).*

1. Every regent system artifact in a host project lives under the `.regent/` directory —
   the single canonical root, making adoption (`regent init`), auditing and removal a
   single-prefix concern.
2. Outside `.regent/` only **managed integrations** may exist — fragments the agents' runtimes
   force into fixed paths (e.g. `.claude/skills/*` symlinks pointing into `.regent/skills/`,
   activation rules in `.claude/settings.local.json`, `.gitignore` entries). Each managed
   integration MUST have: delimited markers identifying regent-owned content, conflict
   detection against pre-existing host content, idempotent updates, and safe removal on
   unplug. No other regent content may live outside `.regent/`. For symlink integrations,
   the ownership marker is the link target pointing inside `.regent/` (detectable and safely
   removable); textual fragments require delimited markers. *(Clarified in RODADA-003.)*
3. Persistence rule: every **persistent, shareable artifact** lives in `.regent/` — including
   audit ledgers and evidence tuples (auditable evidence is product value, cf. P-11). The XDG
   state directory (`regent/<slug>`) holds only **disposable local operational state** (process
   locks, caches). Objective criterion: if losing the file compromises auditability or resuming
   the work from another machine, it belongs in `.regent/`.
4. Sketch (to be detailed in its own round): `.regent/config.*`, `.regent/control.json` (CAS),
   `.regent/scope/`, `.regent/imps/<IMP>/`, `.regent/rounds/`, `.regent/skills/`.

### REQ-002 — Language policy: three layers

*Source: RODADA-001 (owner requirement + Codex objection 4; partial revocation of the
"product docs in PT-BR" scope decision, owner-ratified).*

1. **System and product layer — English, always:** code, `.regent/` file and directory names,
   structured keys/states/values (e.g. `control.json` `state: BATCH_FROZEN`), skill names,
   templates, CLI messages, and the product's own documentation (this PRD included).
2. **Deliberation layer — the mediator's language:** free text of rounds, replies, opinions
   and decisions mediated by a human. Configurable; PT-BR for this product's own rounds.
3. **Hosted-project layer — the host's native language:** content about the project under
   review or construction, declared in `.regent/config` (e.g. `native_language: pt-BR`).
4. Mixed files follow the layer of each part: structured fields always English; free-text
   bodies follow their layer's language.

### REQ-003 — Agent roles and execution runtime

*Source: RODADA-002 (owner requirement; Codex objections 1–6 incorporated across two
opinions; residuals 3 and 5 conceded and defined by Claude).*

1. **Roles.** **Executor** — holds the work turn, writes to the host repo, runs the
   conduction. **Advisor** — consulted by the executor or mediator; always read-only; never
   holds a turn; never writes to the host repo or regent artifacts (the advisor CLI's own
   internal state outside the repo is out of scope). **Mediator** — the human who governs
   decisions and state transitions without holding work turns.
2. **V1 bindings are mandatory, not configurable.** Executor = Claude Code CLI; Advisor =
   Codex CLI. Any Codex→Claude control flow is prohibited by requirement. The
   executor/advisor roles exist as internal extension seams only — no v1 configuration
   surface accepts a different executor.
3. **What migrates.** The unidirectional headless consult adapter migrates (invocation MUST
   enforce `--sandbox read-only` and `--ask-for-approval never`). The Codex turn-holding
   path does not migrate (turn-entry scripts, symmetric skills, dual agent identity in the
   turn lock).
4. **Protocol consequence.** The mutex/CAS mechanism is preserved, but the actor model
   changes: the executor is the ONLY agent that can hold a turn; advisor consultations are
   evidence-recorded sub-steps of the executor's turn, not turns.
5. **Consultation semantics.** Terminal outcomes: `SUCCESS`, `TIMEOUT`, `FAILURE` (non-zero
   exit), `CANCELLED` (mediator abort). Invariants: (i) turn ownership is unchanged
   throughout a consultation; (ii) fail-closed — a non-`SUCCESS` outcome never advances a
   decision that requires advice; (iii) every outcome persists evidence under `.regent/`:
   full prompt, full response (or partial output on failure), exit code, timestamp, and
   turn/round linkage; (iv) resuming means issuing a NEW evidence-recorded consultation,
   never partially resuming one. The detailed state machine is specified in the protocol
   design round.
6. **`regent init` / `regent doctor` contract.** `init` = installation/seeding, atomic:
   exit 0 only on complete seeding; otherwise non-zero with safe rollback and no partial
   state; a missing agent CLI is a warning, not an init failure. `doctor` = capability
   diagnostics via safe non-interactive probes: exit 0 iff all capabilities are usable;
   structured per-capability report. A command requiring an unavailable capability fails
   with an explicit error naming the capability and pointing to `doctor`. The
   command×capability matrix is fixed in the CLI interface round.
7. **Acceptance criteria (tests).** (a) the advisor can never acquire a turn; (b) no code
   path triggers Claude from the Codex environment; (c) a consultation that cannot persist
   its evidence fails; (d) a failed `init` leaves no partial state.

### REQ-004 — Activity control commands: `/regent` and `/regent-stop`

*Source: RODADA-003 (owner requirement; Codex objections 1–7 incorporated).*

1. **Two commands only.** Activity state is singular, so the control pair operates on it;
   activities (brainstorm, planning, implementation) are arguments/modes, not commands.
   Both are Claude Code skills whose canonical content lives in `.regent/skills/` and is
   installed into `.claude/skills/` as managed symlink integrations by `regent init`
   (REQ-001 §2); English (REQ-002); executor-side only — stopping never depends on the
   advisor (REQ-003).
2. **`/regent` — state-driven single entry.** Reads the control state and resumes the open
   activity. Precedence rules (normative): one active activity at a time; bare `/regent`
   resumes only when exactly one activity is open/suspended, otherwise reports state and
   options — it never starts anything implicitly; `/regent <mode>` with a divergent open
   activity fails with an error explaining the state — it never silently ignores the
   argument nor creates a second activity; with no initialized control it errors pointing
   to `regent init`. Ambiguous/corrupted state → report and stop (default-deny).
3. **`/regent-stop` — durable stop-request, not inter-skill interruption.** The stop channel
   is a durable stop-request in the control (CAS): a detached daemon honors it at the next
   boundary (`--abort` additionally kills the in-flight advisor consultation, recording
   `CANCELLED` per REQ-003 §5); in an interactive session, immediate interruption is Claude
   Code's own (user Esc) and `/regent-stop` normalizes state at the next message boundary;
   writing the stop-request from another session/terminal is equally valid.
4. **Canonical stop sequence** (each step idempotent; on crash, resume re-executes from the
   first incomplete step): (1) record turn-linked stop-request via CAS; (2) end/cancel the
   in-flight sub-step; (3) persist evidence; (4) write resume checkpoint; (5) transition
   activity → `SUSPENDED` via CAS; (6) release lock; (7) confirm. Stale stop-requests are
   discarded on read, with a record. Orphan-lock recovery belongs to the protocol layer
   (staleness detection), not to the skill.
5. **State model.** `SUSPENDED` MUST carry: previous activity, substate/checkpoint, owning
   turn, in-flight operation (if any), and reason. Consultation outcomes (REQ-003 §5) are
   sub-step attributes; activity states belong to the control — the two axes never mix.
6. **Commit policy.** Durable evidence persistence under `.regent/` is the requirement;
   git commit is a distinct, non-blocking step covering ONLY regent-owned paths (`.regent/`
   + marked integrations), never unrelated host content. A failed commit never prevents
   suspension; it is reported and left pending. *(Amended by REQ-005 §5: this rule governs
   **operational commits** — brainstorm, suspension, control artifacts. Deliberate build-step
   commits are a distinct category defined there.)*
7. **v0 (file-driven) dogfood.** Until extraction lands, the two skills operate at a
   declared reduced capability level: state = brainstorm round files (open round = round dir
   without `DECISAO.md`), stop = `SUSPENSAO.md` marker + commit, no daemon/lock/abort. The
   skills MUST state their capability level and never claim semantics that do not exist yet.

### REQ-005 — `plan` and `build` modes (v0 file-driven)

*Source: RODADA-004 (owner requirement; Codex objections 1–8 incorporated).*

1. **Plan mode.** `/regent plan "<goal>"` creates `.regent/plans/PLAN-NNN/` and deliberates
   a plan like a round: `REQUEST.md` (owner's goal verbatim) → `PLAN.md` (goal, scope in/out,
   numbered steps each with an acceptance criterion and an executable gate command, risks;
   content in the host's native language) → advisor review with one rebuttal cycle →
   `APPROVAL.md` with structured `status: APPROVED | REJECTED | CANCELLED` + actor. Without
   APPROVED status a plan is not executable; the owner may cancel a plan at any time.
2. **Build candidacy and selection.** A build candidate is an APPROVED plan without a
   concluded build. Bare `/regent build` works only with exactly one candidate; more than
   one demands explicit `/regent build PLAN-NNN`; none is an error. An approved-but-unstarted
   plan is NOT an open activity (it awaits the owner's explicit build order).
3. **Build step protocol.** `build/BASELINE.md` records the base SHA on build start; per
   step: clean-worktree precondition (dirty = stop, default-deny — never absorb pre-existing
   user changes) → implement → run the step's gate for real (red gate never proceeds and
   never commits) → write `build/STEP-NN.md` (step base SHA, files touched, gate output — no
   commit hash: the artifact↔commit link is the commit-message trailer
   `Regent-Step: PLAN-NNN/STEP-NN`, avoiding hash circularity) → deliberate commit with
   file-by-file staging of only step-attributable paths, staged-diff inspection, and failure
   without commit on anything unattributable.
4. **Resume phases.** Observable per-step phases with idempotent recovery — IMPLEMENTING
   (re-run gate before trusting anything), GATE-RED (back to implementation),
   GATE-GREEN-UNCOMMITTED (re-verify gate, then commit; trailer check before committing
   prevents duplicates), COMMITTED (advance). Recovery always consults trailer → STEP file →
   worktree, in that order.
5. **Commit categories (amends REQ-004 §6).** Operational commits (brainstorm, suspension,
   control artifacts) cover only regent-owned paths. **Deliberate build-step commits** are a
   distinct category: they include host paths attributable to the step plus the step's
   regent artifacts, under the §3 attribution protocol.
6. **Build conclusion.** Final advisor review over exactly `BASE-SHA..HEAD`, then
   `build/CONCLUSION.md` with structured `status: ACCEPTED | ACCEPTED-WITH-RESERVATIONS |
   REJECTED` + actor + pending items. An adverse review or non-arbitrated divergence can
   never become acceptance; any post-review fix invalidates the review (re-run affected gate
   + new advisor consultation before concluding).
7. **Consultation evidence (applies to all modes).** Every advisor consultation persists the
   REQ-003 §5 tuple: full prompt in a `*-PROMPT.md` sibling, response artifact opening with
   a structured header (`outcome`, `exit_code`, `timestamp`, `linkage`). Fail-closed on
   non-SUCCESS outcomes.
8. **Artifact naming (REQ-002 alignment).** New hosts use English artifact names for all
   modes (`rounds/ROUND-NNN/QUESTION.md`, `DECISION.md`, …). Legacy hosts (pre-0.2 PT-named
   seeds) keep operating on their PT scheme for brainstorm, recognized by fixed location;
   `plan`/`build` always use the English scheme. Both schemes present and non-empty in one
   host = corrupted state (default-deny, manual migration instructions; never auto-migrate).
   The regent repo's own `docs/brainstorm/` remains the location-delimited dogfood exception.

## Requirement log

| REQ | Title | Round | Status |
|---|---|---|---|
| REQ-001 | Host footprint under `.regent/` | RODADA-001 | Accepted (consensus + owner) |
| REQ-002 | Three-layer language policy | RODADA-001 | Accepted (consensus + owner) |
| REQ-003 | Agent roles and execution runtime | RODADA-002 | Accepted (consensus) |
| REQ-004 | Activity control commands `/regent`, `/regent-stop` | RODADA-003 | Accepted (consensus) |
| REQ-005 | `plan` and `build` modes (v0 file-driven) | RODADA-004 | Accepted (consensus) |
