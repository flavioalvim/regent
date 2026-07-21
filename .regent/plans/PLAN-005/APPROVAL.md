# PLAN-005 — APPROVAL

status: APPROVED
actor: consensus (advisor residuals incorporated verbatim into the contracts in v3; owner
  mediating live)
date: 2026-07-21

## Registro

Trajeto: v1 → ADVISOR-REVIEW-1 (DISCORDA, 8 objeções — arquiteturais: runner não-cancelável,
sem exclusão entre loops, avanço falsificável) → CLAUDE-REBUTTAL + v2 → ADVISOR-REVIEW-2
(DISCORDA residual em 6, todos PRESCRITIVOS de completude: avanço não-falsificável por
trailer+arquivo em HEAD; tryK integrado ao linkage/trailer/recover; abort com nonce de
execução + O_EXCL; runner sem deadlock com drenagem; máquina de abort recuperável sob crash;
mapa exceção→condição completo + op-commit não-fencido com CAS) → **v3 incorpora os 6 nos
contratos (seção Emendas v3)**. Precedente de consenso por incorporação verbatim:
PLAN-001..004. As duas consultas rodaram pelo próprio `regent advisor consult` (dogfood).

Candidato a build: PLAN-005 (único sem build concluído). Só inicia com `/regent build`.

## Plano aprovado

PLAN.md v3 — 4 etapas (runner cancelável + abort-request + keepalive; run_turn attempt +
loop driver; CLI loop run|abort + evidência; consolidação 0.7.0), ~30 testes dirigidos,
runner cancelável sem deadlock, loop lock, avanço por trailer+arquivo, abort recuperável,
códigos novos declarados. Emenda declarada ao PLAN-004 (suspensão via app layer libera o
turn lock).
