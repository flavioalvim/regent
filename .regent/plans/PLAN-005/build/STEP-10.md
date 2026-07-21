# PLAN-005 / STEP-10 — Correção da 6ª revisão (abort durante o gate)

step_base_sha: dcbbeb0 (commit do STEP-09)
files_touched: src/regent/conduction/{gate,turn}.py, tests/test_abort.py

## Mapa achado→correção

- **Achado único (abort durante o gate reivindicado mas ignorado):** `run_gate` agora
  aceita e ENCAMINHA `cancel` ao runner (um gate demorado é morto); após o gate,
  `if cancel.is_set()` → o turno vira ABORTED (op-commit fencido da evidência, suspende
  via app layer liberando o lock, limpa o marcador do abort deste turno) — nunca produz
  TURN_OK/commit de STEP quando o abort foi honrado no gate. Teste dirigido novo
  `test_abort_during_gate_is_honored`: abort emitido no gate → ABORTED + SUSPENDED + lock
  livre + marcador limpo + STEP não commitado.

## Gates

PYTHONPATH=src python3 -m unittest discover -s tests → Ran 212 tests — OK (3 execuções)
bash scripts/gate-package.sh → 0.7.0 PASSED.
