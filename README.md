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

© Flavio Alvim. All rights reserved (license to be decided).
