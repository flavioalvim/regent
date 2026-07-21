# PLAN-005 / STEP-11 — Correção da 7ª revisão (abort na janela verify/evidência)

step_base_sha: 472271b (commit do STEP-10)
files_touched: src/regent/conduction/turn.py, tests/test_abort.py

## Mapa achado→correção

- **Achado único (abort na janela verify/attribute/evidence após o gate):** checagem FINAL
  de `cancel` imediatamente antes da escrita da evidência — um abort reivindicado durante
  verify_chain/attribute_changes/escrita da evidência sobrescreve o outcome para ABORTED
  (a evidência registra ABORTED e o handler ABORTED do COMMITTED suspende sem commitar).
  Fecha a última janela em que um abort honrado podia resultar em STEP commitado. Teste
  `test_abort_after_gate_during_verify_is_honored`: abort pós-gate → ABORTED + SUSPENDED +
  STEP não commitado.

## Gates

PYTHONPATH=src python3 -m unittest discover -s tests → Ran 213 tests — OK (3 execuções)
bash scripts/gate-package.sh → 0.7.0 PASSED.
