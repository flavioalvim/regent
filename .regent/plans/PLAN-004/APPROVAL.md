# PLAN-004 — APPROVAL

status: APPROVED
actor: consensus (advisor residuals incorporated verbatim into the normative contracts in
  v3; owner mediating live)
date: 2026-07-21

## Registro

Trajeto: v1 → ADVISOR-REVIEW-1 (DISCORDA, 7 objeções — a #3 derrubou a premissa HMAC-como-
anti-forja) → CLAUDE-REBUTTAL + v2 (prova reancorada no GIT; HMAC→auditoria) →
ADVISOR-REVIEW-2 (DISCORDA residual em 3: vínculo rígido do --step ao plano/STEP corrente;
ordem GATED→VERIFIED cobrindo efeitos do gate; idempotência durável com testes de crash) →
**v3 incorpora os 3 nos contratos**. Precedente de consenso por incorporação verbatim:
PLAN-001/002/003. As duas consultas rodaram pelo próprio `regent advisor consult`
(dogfood da fase 1).

O build só inicia com ordem explícita do dono (REQ-005 §2). Candidatos a build: PLAN-004
(este, único sem build concluído).

## Plano aprovado

PLAN.md v3 — 4 etapas (hook+cadeia+selo; confinamento+prova git; turn run com commit por
índice privado; consolidação 0.6.0), ~35 testes dirigidos, hook real exercitado por
fake-claude, prova de atribuição pelo git (baseline+blob+índice privado+CAS de HEAD),
códigos novos declarados (TURN_VIOLATION, TURN_TAMPERED, TURN_FAILED).
