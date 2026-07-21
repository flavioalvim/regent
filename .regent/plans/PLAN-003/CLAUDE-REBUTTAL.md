# PLAN-003 — Réplica do Claude às 5 objeções do advisor

**Aceito as 5.** PLAN.md revisado (v2):

1. **Proveniência do comando de gate:** `gate run` ganha `--declared-in <artifact>`
   OBRIGATÓRIO — o comando literal deve constar verbatim no artefato de plano/etapa
   referenciado; ausência = erro `PROVENANCE` (código novo declarado). A propriedade
   deixa de depender de disciplina.
2. **`--expect-verdict` fail-closed:** com a flag EXPLÍCITA, resposta sem casamento =
   `ADVISOR_FAILED` (exit 3), artefato persistido com `verdict: null` e
   `outcome: SUCCESS` porém comando falho (o conselho existe, o VEREDICTO exigido não).
   Sem a flag, o default extrai informativamente e `verdict: null` é permitido.
3. **Saída integral:** o artefato SEMPRE representa a íntegra: ≤200 KiB inline; acima,
   header+cauda no artefato + íntegra em `<artifact>-FULL.log` (ambos atômicos, ambos
   evidência; truncagem declarada com tamanho total).
4. **Timeout mata o GRUPO:** subprocessos lançados com `start_new_session=True`; timeout
   → `killpg(SIGKILL)`; teste de integração real (bash que dispara filho `sleep` — após
   TIMEOUT o filho não existe).
5. **Par atômico:** o PAR (artefato + PROMPT copy [+ FULL.log]) tem contrato único:
   pré-existência de QUALQUER um = `CONFLICT` antes de tudo; cópia do prompt primeiro,
   artefato por último; todo desfecho terminal (SUCCESS/TIMEOUT/FAILURE) deixa o par
   COMPLETO; falha antes do terminal remove a cópia órfã.

Testes correspondentes adicionados às etapas.
