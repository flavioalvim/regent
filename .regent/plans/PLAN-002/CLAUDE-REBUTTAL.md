# PLAN-002 — Réplica do Claude às 10 objeções do advisor

**Aceito as 10.** O PLAN.md foi REESCRITO (v2). Mapa objeção→correção:

1. **Upgrade v0→v1 impossível pelo init** → v2 STEP-03: manifesto de versões
   (`templates/MANIFEST.json` com sha256 de TODAS as versões conhecidas de cada skill);
   conteúdo cujo hash casa com versão conhecida = upgrade atômico; conteúdo desconhecido =
   conflito preservado. Teste real v0→v1.
2. **Operações compostas sem camada de aplicação** → v2 STEP-01: módulo `activity.py`
   (application service) com ordenação canônica por operação, **tabela de divergência
   control×lock×token com recuperação idempotente por linha**, e testes de crash em cada
   fronteira (test hooks). `resume` INCREMENTA epoch (alinhado ao PLAN-001).
3. **Takeover sem comando** → `regent activity takeover --reason` (mediado, auditado,
   rotaciona o control via `takeover(control_store=)`); matriz de reconciliação
   control×lock no plano.
4. **Token/P-01 contraditórios** → corrigido: token autoritativo de fencing =
   `control.activity.turn.token`; XDG `turn.json` = CÓPIA local de conveniência do CLI.
   **Emenda ao P-01 RETIRADA** — `acquire()` segue tocando só XDG; quem muta o control é a
   operação composta `activity start` (declarada como tal).
5. **Mutex dentro de `.regent/` viola REQ-001 §3** → v2 STEP-01: local do lock file do
   ControlStore vira parâmetro; o produto o coloca no state dir XDG (errata declarada do
   PLAN-001); teste afirma ausência de `*.lock` sob `.regent/` após operações.
6. **Coreografia de commits do control.json** → v2 define (emenda declarada ao REQ-005
   §3): a pré-condição de worktree limpo EXCETUA `control.json` + `audit.jsonl`
   (mutações operacionais legítimas); eles são staged no commit que fecha a fronteira
   corrente (commit de etapa ou operacional); stop externo durante etapa → suspensão em
   fronteira com commit operacional separado do deliberado.
7. **Matriz control×arquivos incompleta** → v2 enumera TODAS as combinações com desfecho
   default-deny; `SUSPENSION.md` DEIXA DE EXISTIR em hosts v1 (checkpoint só no control —
   fonte única); hosts legados PT sem control permanecem file-driven até upgrade.
8. **Sequência de stop subespecificada** → v2: `/regent` DEVE rodar `stop check` +
   `heartbeat` em fronteiras nomeadas (antes de cada artefato de rodada/plano; entre fases
   de etapa de build); a suspensão segue a ordem canônica do REQ-004 §4 implementada na
   camada de aplicação (evidência→checkpoint→SUSPENDED→release, idempotente);
   `stop request` com atividade SUSPENDED = no-op normalizado com aviso.
9. **Contrato JSON/erros inimplementável** → v2 traz: envelope de erro
   `{"error": <code>, "detail"}` com CATÁLOGO de códigos, códigos de saída fixos, stdout
   SEMPRE JSON puro (inclusive erro de argparse, exit 64), stderr só para dica humana,
   descoberta de root (cwd↑ até `.regent` ou `--project`), XDG =
   `$XDG_STATE_HOME/regent/<sha256(root)[:16]>`, schema de `status`, matriz
   comando×capacidade (REQ-003 §6) e efeito de control corrupto no doctor (exit ≠0).
10. **Gates só de caminho feliz** → v2 lista testes dirigidos de: fault injection por
    fronteira composta, takeover via CLI, `start` concorrente duplo, cada linha da matriz
    control×arquivos, upgrade v0→v1, init re-executado sobre control evoluído (no-op),
    pureza JSON em erro de uso, stop honrado em fronteira, e exceção de worktree limpo.
