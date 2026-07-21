# PLAN-005 / STEP-06 — Correções da 2ª revisão (3 residuais)

step_base_sha: 30d76b0 (commit do STEP-05)
files_touched: src/regent/conduction/{turn,loop}.py

## Mapa achado→correção

- **1 (recover_turn perde estado):** valida o vínculo do .claimed com a atividade/epoch
  ATUAL; NÃO engole falha de suspensão (retorna ABORT_RECOVERY_FAILED); só limpa o
  marcador quando a atividade está de fato SUSPENDED E o lock livre; estados de retorno
  refletem a realidade (ABORT_RECONCILED / _FAILED / _INCOMPLETE / MARKER_UNBOUND).
- **2 (fencing do resumo pós-takeover):** re-checa o token IMEDIATAMENTE antes do
  update-ref (menor janela); token divergente OU HEAD movido → resumo NÃO commitado e a
  função RETORNA conflito → o loop REBAIXA COMPLETE→LOOP_CONFLICT (nunca reporta COMPLETE
  sem o resumo obrigatório).
- **3 (mapa de exceções):** OSError de run_turn (spawn/IO) → HALTED com outcome FAILURE
  (não LOOP_CONFLICT); CalledProcessError do git (incl. _committed_steps antes do try e
  _write_loop_evidence) capturado e mapeado a LOOP_CONFLICT com JSON — nada escapa sem
  contrato.

## Gates

PYTHONPATH=src python3 -m unittest discover -s tests → Ran 206 tests — OK (3 execuções)
bash scripts/gate-package.sh → 0.7.0 PASSED.
