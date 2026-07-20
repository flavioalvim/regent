# PLAN-001 — APPROVAL

status: APPROVED
actor: consensus (advisor residuals incorporated verbatim in v3; owner mediating live)
date: 2026-07-20

## Registro

Trajeto: PLAN v1 → ADVISOR-REVIEW-1 (DISCORDA, 7 objeções) → CLAUDE-REBUTTAL + PLAN v2 →
ADVISOR-REVIEW-2 (DISCORDA residual em 3 pontos, todos PRESCRITIVOS: recuperação de
micro-mutex órfão; fencing do stop-request por turn_token com regra de obsolescência
completa; testes nomeados de takeover/ABA, crash-recovery e durabilidade do audit) →
**PLAN v3 incorpora os 3 verbatim** — não resta divergência de posição entre executor e
advisor sobre o conteúdo do plano.

Nota de governança: o ciclo de réplica do REQ-005 §1 (uma réplica) foi cumprido; os
residuais da segunda revisão foram adotados integralmente na formulação do advisor
(precedente: RODADA-002). O dono, mediando ao vivo, mantém o poder de veto natural: o
build só inicia com ordem explícita `/regent build` (REQ-005 §2).

## Plano aprovado

PLAN.md v3 — 4 etapas (control store transacional + audit; turn lock do executor;
stop-request representação/transições; façade + gate de pacote), 21 testes dirigidos
nomeados, gates fail-closed, versão alvo 0.3.0.
