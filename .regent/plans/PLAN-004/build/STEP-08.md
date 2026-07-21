# PLAN-004 / STEP-08 — Correções da 4ª revisão (cluster de stop/suspensão)

step_base_sha: 46e0424 (commit do STEP-07)
files_touched: src/regent/conduction/turn.py, tests/test_turn.py

## Mapa achado→correção

- **1 (stop_check não em toda fronteira):** helper único `_boundary(phase)`
  (heartbeat+stop_check+suspend+raise) em COMPOSED, LAUNCHED e GATED; MAIS um stop_check
  IMEDIATAMENTE antes do COMMITTING — um stop chegado durante verify/atribuição/evidência
  agora SUSPENDE em vez de commitar o produto (teste dirigido novo prova: work/out.txt
  NÃO commitado, atividade SUSPENDED).
- **2 (STOPPED não garante suspensão):** `_stopped_suspend` não engole mais — token
  tomado por takeover → TurnError CONFLICT (a atividade não é mais nossa para suspender;
  mediador reconcilia); caso normal suspende de fato.
- **3 (ordem do checkpoint pós-gate):** stop_check ANTES de \_set_phase("VERIFIED") — um
  crash na janela nunca deixa checkpoint VERIFIED sem verificação feita.
- Ressalva de teste do STEP-07 fechada: gate forjado exige EXATAMENTE TURN_VIOLATION.

## Gates

PYTHONPATH=src python3 -m unittest discover -s tests → Ran 182 tests — OK (3 execuções)
bash scripts/gate-package.sh → 0.6.0 PASSED.
