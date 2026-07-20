# RODADA-004 — DECISÃO (2026-07-20)

**Resultado: APROVADO por consenso.** Trajeto: proposta do Claude (plan/build v0 file-driven
espelhando o funil da IMP-003) → Codex DISCORDA (8 objeções: hash circular, contradição com
REQ-004 §6, atribuição de mudanças, ciclo de vida dos planos, estados do CONCLUSION, tupla de
evidência, fases de retomada, compatibilidade PT→EN) → réplica aceita as 8 com soluções
concretas → Codex **CONCORDA** ("resolve as oito objeções em nível normativo suficiente").
Sem arbitragem do dono.

## O que ficou decidido (REQ-005 no PRD)

- **`/regent plan "<objetivo>"`**: delibera `PLAN-NNN/` (REQUEST → PLAN com etapas+critérios+
  gates executáveis → revisão do advisor com 1 ciclo de réplica → APPROVAL com
  `status: APPROVED|REJECTED|CANCELLED` + ator). Sem APPROVED, não executa.
- **`/regent build [PLAN-NNN]`**: executa plano aprovado etapa a etapa — BASELINE com base
  SHA; worktree limpo obrigatório por etapa; gate rodado de verdade (vermelho nunca avança);
  STEP-NN sem hash (vínculo = trailer `Regent-Step: PLAN-NNN/STEP-NN`); staging explícito só
  do atribuível; 4 fases de retomada idempotentes; revisão final do advisor sobre
  `BASE-SHA..HEAD`; CONCLUSION com `status: ACCEPTED|ACCEPTED-WITH-RESERVATIONS|REJECTED` +
  ator; correção pós-revisão invalida a revisão.
- **Emenda ao REQ-004 §6**: commits operacionais (só paths regent) ≠ commits deliberados de
  etapa de build (host paths atribuíveis + artefatos da etapa).
- **Tupla de evidência** (REQ-003 §5) em TODA consulta, todos os modos: `*-PROMPT.md` +
  cabeçalho estruturado (outcome/exit_code/timestamp/linkage); fail-closed.
- **Nomes EN em hosts novos** para todos os modos (`rounds/ROUND-NNN/QUESTION.md`…); hosts
  legados PT continuam no esquema deles (por localização fixa); ambos = corrupção
  default-deny; dogfood `docs/brainstorm/` inalterado.

## Execução

- Templates das skills reescritas (`/regent` com modos plan/build; `/regent-stop` cobrindo
  as 3 atividades com checkpoint de fase).
- `regent init` passa a semear `brainstorm/rounds/` + `plans/` (esquema EN).
- REQ-005 no PRD + emenda anotada no REQ-004 §6; versão **0.2.0**.
