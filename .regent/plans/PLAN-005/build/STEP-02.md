# PLAN-005 / STEP-02 — Driver do loop (run_turn attempt + loop.py)

step_base_sha: 587716a (commit do STEP-01)
files_touched:
  - src/regent/conduction/loop.py (novo — run_loop)
  - src/regent/conduction/turn.py (_step_gate com fronteira por CABEÇALHO)
  - tests/test_loop.py (novo, 9)

## O que foi implementado

- run_loop: loop lock (flock — 2º run = LOOP_BUSY); revalida atividade+APPROVAL a cada
  volta; STEP corrente = menor STEP-NN declarado SEM commit com trailer EXATO
  `Regent-Step: PLAN-NNN/STEP-NN` que tocou build/STEP-NN.md E o arquivo existe em HEAD
  (não-falsificável); K = max(tryN existentes)+1; roda run_turn com attempt e linkage
  .../tryK; mapa desfecho→condição completo; sem auto-retry; evidência LOOP-*.md com
  op-commit (CAS, fencido/não conforme estado).
- Correção real: a fronteira de bloco de step passou a ser o CABEÇALHO do próximo step
  (^#+...STEP-NN) — um gate cujo comando CONTÉM um nome de step (ex.: caminho
  work/STEP-01.out) não é mais truncado (bug pego pelo teste COMPLETE). Prompt do loop
  escrito FORA do repo (state dir) para não sujar o worktree (bug pego pelo teste).

## Gate (PYTHONPATH=src python3 -m unittest discover -s tests)

Ran 202 tests — OK (3 execuções). Cobre COMPLETE (2 STEPs), HALT (violação/gate-red),
MAX_TURNS, retry nova-tentativa, revalidação de APPROVAL, loop lock, avanço só por trailer.
