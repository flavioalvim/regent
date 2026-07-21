# PLAN-004 / STEP-03 — regent turn run (orquestração + commit do supervisor)

step_base_sha: d78bdc0 (commit do STEP-02)
files_touched:
  - src/regent/conduction/turn.py (novo — o orquestrador)
  - src/regent/conduction/process.py (param env no runner)
  - src/regent/activity_cli.py (subcomando turn run + 8 códigos novos)
  - tests/test_turn.py (novo, 7 testes com fake-claude exercitando o hook real)

## O que foi implementado

- `run_turn`: pré-condições REQ-005 rígidas (build ACTIVE cujo id==plan do --step; STEP
  existente no plano; gate declarado; artifact-dir sob .regent; worktree limpo exceto
  exceptuados; STEP-NN.md ausente). Fases COMPOSED→LAUNCHED (claude confinado, keep-alive
  heartbeat em thread)→GATED (run_gate APÓS o agente)→VERIFIED (verify_chain +
  attribute_changes)→COMMITTED. Prova cobre efeitos do gate (gate_envelope) e isenta o
  artifact-dir do supervisor.
- Commit do SUPERVISOR por ÍNDICE PRIVADO (GIT_INDEX_FILE): read-tree HEAD, add só do
  conjunto atribuído + STEP file + artefato, write-tree, commit-tree, update-ref com CAS
  de HEAD (base_sha) — se HEAD moveu, aborta CONFLICT; fencing do token antes. Trailers
  Regent-Step + Regent-Turn. Agente jamais commita.
- Desfechos: TURN_OK+GREEN→commit de produto; violação/tampered/gate-red→SEM produto,
  evidência em commit operacional. Códigos TURN_VIOLATION/TURN_TAMPERED/TURN_FAILED etc.

## Vermelho→verde (fiel)

2 correções: fake-runner tratava a chamada do gate (bash) como o claude → passou a rodar
bash de verdade; e o artifact-dir do supervisor (GATE-*.md) aparecia como mudança não
atribuída → isento na prova (é evidência do supervisor, não escrita do agente).

## Gate (PYTHONPATH=src python3 -m unittest discover -s tests)

Ran 168 tests — OK (3 execuções). Cobre TURN_OK com trailers + STEP file + índice privado;
violação de envelope (arquivo escapado NÃO commitado); gate red (sem produto); pré-condições.
