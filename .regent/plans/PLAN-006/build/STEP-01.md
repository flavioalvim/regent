# PLAN-006 / STEP-01 — Ensaio (rehearse) + arm/disarm durável

**Base:** 820f3d58262f27af665b6bf2c4dfdb596d7f1149 (build baseline 5659256)
**Escopo entregue:** `src/regent/conduction/supervisor.py` (rehearse + arm/disarm)
e o parâmetro `guard` no `run_loop` (infra do daemon, no-op quando `guard=None`).

## O que foi implementado
- `rehearse(root, plan_id, declared_in)` — read-only; reusa `_declared_steps`,
  `_committed_steps`, `_step_gate`, `_attempt_number` do loop. Retorna
  `{plan, done, pending:[{step,gate,next_attempt}], complete}`. Não toca o repo,
  não lança agente, não exige atividade ACTIVE (é diagnóstico).
- `arm(service, plan_id, config)` — grava o arm-token ATÔMICO (tmp+fsync+rename+
  fsync do dir, O_EXCL) no state-dir XDG. Pré-condições DURAS: build ACTIVE cujo
  id == plano, `APPROVAL.md` APPROVED, sem `build/CONCLUSION.md`, workspace
  verdict executável (OK/SUSPENDED_OK/IDLE_CLEAN), vincula ao token CORRENTE.
  Arm-token de OUTRO plano já em disco (leitura RAW, antes da validação de
  vínculo) → `ALREADY_ARMED` (o dono desarma explicitamente).
- `read_arm(service)` — retorna o token só se ainda vinculado à atividade
  CORRENTE (plan+epoch+token); takeover (token rotacionado) ou novo ciclo de
  atividade (epoch mudou) → descartado + auditado (`arm_token_discarded`).
- `disarm(service, arm_id=None)` — CAS por arm_id (daemon antigo com arm_id A
  nunca apaga um rearm B); sem arm_id remove o corrente; idempotente.

## Decisão de projeto (mais conservadora que o contrato)
O contrato previa `ALREADY_ARMED` para "outro plano armado". Como o vínculo do
arm-token à atividade ACTIVE torna isso irrecuperável via `read_arm` (descartaria
silenciosamente), a checagem passou a ler o arquivo RAW ANTES das pré-condições:
um arm-token remanescente exige desarme EXPLÍCITO, nunca é sobrescrito às cegas.

## Testes (verdes)
`test_rehearse_lists_pending_steps_and_gates`, `test_rehearse_is_read_only`,
`test_rehearse_complete_plan`, `test_arm_writes_bound_token`,
`test_arm_other_plan_is_already_armed`, `test_arm_refuses_without_matching_active_build`,
`test_arm_token_stale_epoch_ignored`, `test_disarm_idempotent`.

## Gate
`PYTHONPATH=src python3 -m unittest discover -s tests` → OK (suite completa verde).
