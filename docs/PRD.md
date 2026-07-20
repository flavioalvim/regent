# regent — Product Requirements Document

**regent** conducts autonomous work and mediated adversarial deliberation between AI agents
(Claude, Codex, human mediators), pluggable into any host project. Extracted from the tool
proven end-to-end in the ArtNFT project (IMP-003: first product batch fully conducted by the
daemon, deliberated, accepted and deployed to production).

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

## Requirement log

| REQ | Title | Round | Status |
|---|---|---|---|
| REQ-001 | Host footprint under `.regent/` | RODADA-001 | Accepted (consensus + owner) |
| REQ-002 | Three-layer language policy | RODADA-001 | Accepted (consensus + owner) |
