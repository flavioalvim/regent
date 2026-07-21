# PLAN-005 / STEP-09 — Correções da 5ª revisão (precedência + token pós-suspensão)

step_base_sha: cb80af5 (commit do STEP-08)
files_touched: src/regent/conduction/turn.py, tests/test_abort.py

## Mapa achado→correção

- **1 (op-commit ABORTED confunde recover como COMMITTED):** `recover_turn` agora checa
  `.claimed` NÃO-reconciliado ANTES de qualquer trailer/STEP — um crash após o op-commit
  do ABORTED (que carrega Regent-Turn) mas antes de suspender resulta em suspensão, não em
  COMMITTED (teste `test_recover_claimed_takes_precedence_over_trailer`).
- **2 (token pós-SUSPENDED):** o vínculo lê o token de `suspension.owning_turn` quando
  SUSPENDED (suspend zera turn e preserva o token lá) — reconcilia corretamente após a
  transição (teste `test_recover_reconciles_suspended_via_owning_turn`); ambos os ramos
  de clear passam o FILTRO de vínculo (nunca apagam marcador alheio).

## Gates

PYTHONPATH=src python3 -m unittest discover -s tests → Ran 211 tests — OK (3 execuções)
bash scripts/gate-package.sh → 0.7.0 PASSED.
