# RODADA-004 — Resposta do Claude

**Proposta: `plan` e `build` v0 file-driven, espelhando o funil provado na IMP-003**
(plano deliberado → aprovação → execução por etapas com gates → revisão adversarial → aceite),
sem daemon/confinamento/lock (que chegam com a extração). Estrutura:

## `/regent plan "<objetivo>"` — planejar é deliberar um artefato

Cria `.regent/plans/PLAN-NNN/` com:
- `REQUEST.md` — o objetivo do dono, verbatim.
- `PLAN.md` — o plano do Claude: objetivo, escopo dentro/fora, **etapas numeradas cada uma com
  critério de aceitação e comando de gate** (teste executável), riscos. Conteúdo na língua
  nativa do host (camada 3 do REQ-002); nomes de arquivo em inglês (camada 1).
- `ADVISOR-REVIEW-1.md` — parecer do Codex (mesma invocação read-only; veredicto
  CONCORDA/DISCORDA), com um ciclo de réplica (`CLAUDE-REBUTTAL.md` + `ADVISOR-REVIEW-2.md`).
- `APPROVAL.md` — aprovação do plano: consenso, ou arbitragem do dono. **Sem APPROVAL.md o
  plano não é executável.**

## `/regent build` — executa um plano APROVADO, etapa a etapa

- Pré-condição dura: exatamente um plano com `APPROVAL.md` e sem `build/CONCLUSION.md`.
  Sem plano aprovado → erro (nunca constrói sem plano; nunca escolhe entre dois).
- Por etapa: implementar → rodar o comando de gate da etapa → registrar
  `build/STEP-NN.md` (o que mudou, saída do gate, hash do commit) → **commit da etapa**.
- **Exceção explícita à política de commit do brainstorm:** build escreve código do PROJETO
  HOST — é a função dele. O commit da etapa inclui os paths do host tocados pela etapa +
  os artefatos regent da etapa. Gate vermelho = etapa NÃO commita; corrige ou suspende.
- Fim: `build/ADVISOR-REVIEW.md` — Codex revisa o diff integral do build (veredicto com
  achados) → `build/CONCLUSION.md` com o aceite do dono (ou registro do veredicto + pendências).

## Estado e retomada (estende o passo 1 do /regent)

- Atividades abertas: brainstorm = ROUND sem DECISION; **planning** = PLAN-NNN sem APPROVAL.md;
  **building** = plano aprovado com `build/` iniciado e sem CONCLUSION.md.
- Plano aprovado e não iniciado NÃO é "aberto" (aguarda ordem `/regent build` do dono).
- `>1` atividade aberta (em qualquer combinação) = ambiguidade → erro. `/regent` seco retoma
  a única aberta; `/regent-stop` grava `SUSPENSION.md` nela (checkpoint = última etapa completa).

## Alinhamento de nomes com o REQ-002 (correção de dívida)

Os artefatos v0 atuais usam nomes PT (`RODADA/PERGUNTA/DECISAO`) — inconsistente com o
REQ-002 §1 (nomes de arquivo do sistema = inglês). Proposta: **em projetos host, TODOS os
modos usam nomes ingleses** (`rounds/ROUND-NNN/{QUESTION,CLAUDE-RESPONSE,ADVISOR-OPINION-N,
CLAUDE-REBUTTAL,DECISION,SUSPENSION}.md`); o `docs/brainstorm/` do repo regent fica como
legado dogfood com nomes PT (a skill já o trata como localização especial). Conteúdo continua
na língua do mediador/host.

## Honestidade v0 (mesma disciplina do brainstorm)

Sem lock, sem daemon, sem confinamento: build roda na sessão, interrupção imediata = Esc,
suspensão entre etapas via `/regent-stop`. A skill declara isso. Gates são os declarados no
plano — a skill NUNCA marca etapa como verde sem rodar o gate e mostrar a saída.

## Execução proposta (se houver concordância)

1. Atualizar as templates das skills (`/regent` com modos plan/build + nomes EN no host;
   `/regent-stop` cobrindo as 3 atividades).
2. REQ-005 no PRD (modos plan/build v0 + migração de nomes).
3. Versão 0.2.0 do pacote (mudança de comportamento), testes, commit.
