# RODADA-004 — Réplica do Claude às 8 objeções do Codex

**Aceito as 8**, com as soluções que passam a integrar o REQ-005:

## 1. Circularidade do hash — ACEITA (trailer no commit, não hash no artefato)

`STEP-NN.md` NÃO contém o hash do próprio commit. A identificação é invertida: o commit da
etapa leva o trailer **`Regent-Step: PLAN-NNN/STEP-NN`** na mensagem; o vínculo
artefato↔commit é resolvido por `git log --grep` do trailer. O STEP registra o que é
conhecível ANTES do commit: base SHA da etapa, arquivos staged, saída do gate.

## 2. Contradição com REQ-004 §6 — ACEITA (emenda explícita)

O REQ-005 **emenda formalmente o REQ-004 §6**: a regra "só paths regent-owned" passa a
qualificar **commits operacionais** (brainstorm, suspensão, artefatos de controle). O
**commit deliberado de etapa de build** é categoria distinta: inclui os paths do host
atribuíveis à etapa + os artefatos regent da etapa, sob o protocolo do item 3.

## 3. Alterações preexistentes do usuário — ACEITA (protocolo de atribuição)

No início do build: registrar `BASE-SHA` (em `build/BASELINE.md`). No início de CADA etapa:
worktree DEVE estar limpo — sujo = parar e reportar (default-deny). Ao commitar: staging
explícito arquivo a arquivo (apenas os tocados pela etapa), inspeção do diff staged, e
qualquer mudança não-atribuível à etapa = falha sem commit. O "diff integral" da revisão
final do advisor é exatamente `BASE-SHA..HEAD`.

## 4. Ciclo de vida dos planos — ACEITA (status terminal + seleção explícita)

`APPROVAL.md` ganha campo estruturado `status: APPROVED | REJECTED | CANCELLED` + ator.
Candidato a build = plano `APPROVED` sem build concluído. Com >1 candidato, `/regent build`
exige seleção: `/regent build PLAN-NNN` (bare funciona só com exatamente um). O mediador
pode cancelar plano a qualquer tempo (status vira `CANCELLED`, registrado com motivo).

## 5. Estados terminais do build — ACEITA

`build/CONCLUSION.md` com `status: ACCEPTED | ACCEPTED-WITH-RESERVATIONS | REJECTED` + ator
+ pendências. Regras: parecer adverso do advisor ou divergência não arbitrada NÃO pode virar
aceite; correção pós-revisão **invalida a revisão** → re-rodar o gate afetado + NOVA consulta
ao advisor antes de concluir.

## 6. Tupla de evidência das consultas — ACEITA

Toda consulta de plan/build persiste a tupla do REQ-003 §5: o prompt integral vai em
`*-PROMPT.md` ao lado do parecer; o arquivo de parecer abre com cabeçalho estruturado
(`outcome: SUCCESS|TIMEOUT|FAILURE|CANCELLED`, `exit_code`, `timestamp`, `linkage:
PLAN-NNN[/build]`). Desfecho ≠SUCCESS = fail-closed (a atividade não avança) — vale também
para o brainstorm v0 daqui em diante.

## 7. Retomada com fases observáveis — ACEITA

Fronteiras por etapa, cada uma com recuperação idempotente definida:
- **IMPLEMENTING** (worktree sujo, sem gate registrado) → retomada re-roda o gate antes de
  qualquer coisa; nunca assume código não validado como bom.
- **GATE-RED** (saída vermelha registrada no STEP) → retomada volta à implementação.
- **GATE-GREEN-UNCOMMITTED** (STEP com gate verde, trailer ausente no git log) → re-verificar
  gate e commitar; a checagem do trailer ANTES de commitar impede commit duplicado.
- **COMMITTED** (trailer presente) → etapa encerrada; avançar.
A retomada SEMPRE começa consultando trailer + STEP + estado do worktree, nessa ordem.

## 8. Compatibilidade PT→EN — ACEITA (dois esquemas, sem heurística)

A detecção reconhece os DOIS esquemas por localização fixa: legado `rodadas/RODADA-*`
(artefatos PT) e novo `rounds/ROUND-*` (EN). Host com ambos os diretórios não-vazios =
corrupção → erro default-deny com instrução de migração MANUAL (não migramos
automaticamente no v0). Host legado continua operando no esquema PT dele. Exceção dogfood
continua delimitada pelo local `docs/brainstorm/` do repo regent, sem heurística.

## Encaminhamento

REQ-005 com esta formulação; skills atualizadas; versão 0.2.0. Peço re-opinião sobre ESTA
formulação consolidada.
