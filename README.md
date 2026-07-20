# regent

Autonomous conduction and mediated adversarial deliberation between AI agents, pluggable
into any project.

**regent** governs turns between agents (Claude, Codex, human mediators) under a frozen
protocol: atomic turn mutex, CAS-versioned state, deliberation rounds with versioned
acceptances, and a conduction daemon that executes production batches with a confined agent,
test gates and evidence proof.

Extracted from the tool proven end-to-end in the ArtNFT project (IMP-003: first product
batch fully conducted by the daemon, deliberated, accepted and deployed to production).

- Requirements: [`docs/PRD.md`](docs/PRD.md)
- Extraction scope and decisions: [`docs/ESCOPO.md`](docs/ESCOPO.md) (PT-BR, pre-rename)
- Deliberation rounds: [`docs/brainstorm/`](docs/brainstorm/) (mediator's language, PT-BR)
- Status: **pre-extraction** (scope closed 2026-07-20; code not yet migrated)

## Install

```bash
pip install <path-to-this-repo>   # package: regent-cli; CLI: regent (not on PyPI yet)
cd <your-project>
regent init                        # seeds .regent/ + .claude/skills symlinks (atomic, idempotent)
regent doctor                      # checks executor (claude) and advisor (codex) CLIs
```

Then open a Claude Code session in the project — `/regent` and `/regent-stop` are available
(`/regent brainstorm "<question>"` opens the first round). v0 capability is file-driven
(rounds under `.regent/brainstorm/rodadas/`); the advisor requires the `codex` CLI.

Development: `PYTHONPATH=src python3 -m unittest discover -s tests`; packaging gate:
`bash scripts/gate-package.sh`. Canonical skill content lives in `src/regent/templates/`
(ships inside the wheel); the repo's own `.regent/skills/` symlinks into it (dogfood
without duplication).

## Protocol layer

`regent.protocol` (PLAN-001) is the transactional foundation the conduction daemon will
drive: `ControlStore` (control.json with a real CAS — every mutation runs inside a
kernel-flock critical section, atomic AND durable publication with file+directory fsync),
`TurnLock` (executor-only turn ownership by uuid4 token; the whole lifecycle —
acquire/heartbeat/release/takeover — is serialized under a flock; takeover is graced,
audited, and rotates the control turn token BEFORE the new lock exists, aborting on
divergence), stop-request representation (`record_stop_request` /
`read_valid_stop_request` / `suspend_activity`, with activity/epoch/turn-token staleness
fencing) and `AuditLog` (flock-serialized, fsynced JSONL under
`.regent/protocol/audit.jsonl`). Dormant until the conduction phase wires it to the
skills; the v0 skills remain file-driven.

MIT License © 2026 Flavio Alvim.
