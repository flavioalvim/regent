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

Planned usage (v1):

```bash
pip install regent-cli     # import/CLI name: regent (private repo for now)
regent init                # seeds .regent/ + managed integrations in the host project
```

Manual installation today (v0 — exactly what `regent init` will automate):

```bash
cd <your-project>
cp -r <path-to-regent-repo>/.regent .          # 1. copy the .regent/ folder (note the dot)
mkdir -p .claude/skills                         # 2. link the commands so Claude Code finds them
ln -s ../../.regent/skills/regent .claude/skills/regent
ln -s ../../.regent/skills/regent-stop .claude/skills/regent-stop
```

Then open a Claude Code session in the project — `/regent` and `/regent-stop` are available.
v0 capability is file-driven (brainstorm rounds under `.regent/brainstorm/rodadas/`); the
advisor requires the `codex` CLI installed.

© Flavio Alvim. All rights reserved (license to be decided).
