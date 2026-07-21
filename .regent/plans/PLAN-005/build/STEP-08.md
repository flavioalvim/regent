# PLAN-005 / STEP-08 — Correções da 4ª revisão (vínculo completo, marcador específico)

step_base_sha: 1ddea8d (commit do STEP-07)
files_touched: src/regent/conduction/{abort,turn,loop}.py, tests/test_abort.py

## Mapa achado→correção

- **1 (vínculo de recuperação ignora token):** recover_turn agora compara também
  `turn_token` (além de activity_id/epoch) — um .claimed do executor ANTIGO não suspende
  a atividade já assumida por um novo executor após takeover (fencing do abort completo).
- **2 (crash até o resumo + clear_claimed genérico):** o caminho ABORTED faz op-commit
  FENCIDO da evidência TURN ANTES de suspender/limpar (registro durável do ABORTED mesmo
  com crash imediato); `clear_claimed` ganha filtro por vínculo (activity/epoch/token) e
  remove SÓ o marcador deste abort, nunca alheios.
- **3 (conflito booleano do resumo mascarado):** `summary_conflict=True` →
  LOOP_CONFLICT independentemente da condição anterior (não só COMPLETE), igual ao caminho
  de exceção.

## Gates

PYTHONPATH=src python3 -m unittest discover -s tests → Ran 209 tests — OK (3 execuções)
bash scripts/gate-package.sh → 0.7.0 PASSED.
