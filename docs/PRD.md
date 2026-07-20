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
   unplug. No other regent content may live outside `.regent/`.
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

## Requirement log

| REQ | Title | Round | Status |
|---|---|---|---|
| REQ-001 | Host footprint under `.regent/` | RODADA-001 | Accepted (consensus + owner) |
| REQ-002 | Three-layer language policy | RODADA-001 | Accepted (consensus + owner) |
| REQ-003 | Agent roles and execution runtime | RODADA-002 | Accepted (consensus) |
