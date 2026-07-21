# PLAN-005 / STEP-05 — Correções da revisão final (4 bloqueios)

step_base_sha: 838dba4 (commit do STEP-03/04)
files_touched: src/regent/conduction/{abort,turn,loop}.py, tests/{test_abort,test_loop}.py

## Mapa achado→correção

- **1 (abort atinge o turno seguinte):** o abort-request captura o NONCE do turno EM VOO
  no momento da escrita; o claim exige `turn_nonce` presente E IGUAL ao nonce corrente
  (mesmo turno, não "qualquer"). Abort escrito entre turnos (nonce None) = no-op
  descartado; abort de A jamais mata B (teste `test_abort_bound_to_specific_turn_nonce`).
- **2 (máquina de abort não recuperável):** `.claimed` ÚNICO por id (nunca sobrescrito);
  o caminho ABORTED reconcilia (limpa o claimed) após suspender; `recover_turn` detecta
  `.claimed` + atividade ACTIVE e COMPLETA a suspensão idempotentemente
  (state ABORT_RECONCILED). Crash pós-claim/kill não deixa mais ACTIVE órfão.
- **3 (resumo do loop sem fencing/CAS):** evidência+commit agora DENTRO do loop lock;
  commit por ÍNDICE PRIVADO (GIT_INDEX_FILE, sem staged alheio) + CAS de HEAD +
  fencing de token quando ACTIVE (sem token quando SUSPENDED — as duas vias); staging só
  do path do resumo.
- **4 (mapa exceção→condição incompleto):** captura ampliada — EvidenceConflict→
  LOOP_CONFLICT, CalledProcessError/OSError→LOOP_CONFLICT (com JSON), NOT_ACTIVE/PROVENANCE/
  etc. mapeados; `--max-turns < 1` = USAGE (teste).

## Gates

PYTHONPATH=src python3 -m unittest discover -s tests → Ran 206 tests — OK (3 execuções)
bash scripts/gate-package.sh → 0.7.0 PASSED.
