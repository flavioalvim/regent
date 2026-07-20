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

Development: `PYTHONPATH=src python3 -m unittest discover -s tests`. Canonical skill content
lives in `src/regent/templates/` (ships inside the wheel); the repo's own `.regent/skills/`
symlinks into it (dogfood without duplication).

© Flavio Alvim. All rights reserved (license to be decided).
