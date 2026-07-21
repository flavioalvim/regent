# PLAN-005 / STEP-07 — Correções da 3ª revisão (2 residuais) + testes dos ramos

step_base_sha: 7701de6 (commit do STEP-06)
files_touched: src/regent/conduction/{turn,loop}.py, tests/{test_abort,test_loop}.py

## Mapa achado→correção

- **1 (recover apaga .claimed prematuramente no ramo SUSPENDED):** o ramo SUSPENDED agora
  exige marcador VINCULADO E lock FREE antes de limpar; senão retorna
  ABORT_RECOVERY_INCOMPLETE (bound, lock preso) ou ABORT_MARKER_UNBOUND — marcador
  preservado para o mediador. Fecha a fronteira de crash pós-CAS/pré-release.
- **2 (erro git no resumo só rebaixava COMPLETE):** QUALQUER CalledProcessError no resumo
  → LOOP_CONFLICT, independentemente da condição anterior (HALTED/STOPPED/ABORTED/MAX_TURNS
  inclusos), como manda o contrato "git errors → LOOP_CONFLICT".
- Testes novos dos ramos: recover reconcilia abort SUSPENDED (limpa, lock free);
  marcador não-vinculado é preservado (ABORT_MARKER_UNBOUND); falha de git no resumo →
  LOOP_CONFLICT (injeção).

## Gates

PYTHONPATH=src python3 -m unittest discover -s tests → Ran 209 tests — OK (3 execuções)
bash scripts/gate-package.sh → 0.7.0 PASSED.
