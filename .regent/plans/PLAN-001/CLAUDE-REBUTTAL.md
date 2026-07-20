# PLAN-001 — Réplica do Claude às 7 objeções do advisor

**Aceito as 7.** O PLAN.md foi REVISADO EM PLACE (v2) incorporando tudo; esta réplica
registra o mapa objeção→correção:

1. **Lost update no "CAS"** — verdade: read→check→replace não é compare-and-swap. v2:
   toda mutação do control roda sob um **micro-mutex exclusivo de mutação** (mkdir-style,
   distinto do turn lock; nunca segurado durante aquisição do turn lock — ordem documentada),
   com checagem de versão dentro da seção crítica. Testes dirigidos multiprocesso com
   barreira: exatamente um escritor vence; stop-request concorrente com update do executor
   não perde campos.
2. **P-01/P-03 mal rastreados** — corrigido: **P-01** = `acquire` bem-sucedido deixa
   `.regent/` e o git **byte-idênticos** (só XDG muda); teste compara hash da árvore
   antes/depois. **P-03** (governança de paths por allowlist) é da fase de confinamento —
   alegação REMOVIDA e diferida explicitamente; a validação estrita de schema fica, sem o
   rótulo P-03.
3. **Fidelidade do lock imprecisa** — corrigido: a fonte usa `mkdir()` como mutex; o v2
   declara **reimplementação da invariante** (não reuso do algoritmo), mantém a primitiva
   mkdir provada + arquivo de owner interno, e define: token de propriedade (uuid),
   release/heartbeat só com token corrente, takeover só de lock suspeito (idade>threshold)
   com registro de auditoria completo (ator, motivo, owner anterior, idade, timestamps),
   proteção ABA via epoch da atividade + token no control, e tratamento do crash entre
   mkdir e gravação do owner (lock sem owner após grace = suspeito).
4. **Schema insuficiente** — v2 traz o schema COMPLETO com tipos, nulabilidade e
   invariantes: `activity: null` (ocioso), `epoch` (guarda ABA), `turn {owner, token,
   acquired_at}` obrigatório em ACTIVE, `suspension` obrigatória em SUSPENDED,
   `stop_request` vinculado a `{activity_id, activity_epoch, turn_token}` (decide obsoleto
   sem ambiguidade), `last_concluded` (ciclo de vida/limpeza).
5. **STEP-03 superprometia** — reduzido a **representação e transições do protocolo de
   stop** (gravar vinculado, descartar obsoleto com auditoria, transição SUSPENDED com
   payload, idempotência dessas transições). A sequência canônica completa, `--abort` e
   `CANCELLED` ficam EXPLICITAMENTE para a fase de condução; o v2 não alega REQ-004 §3–4
   integral.
6. **Auditoria e durabilidade** — v2: registros de takeover/descarte em
   **`.regent/protocol/audit.jsonl`** (append-only, evidência compartilhável, REQ-001);
   publicação atômica SEPARADA de durabilidade (fsync do arquivo E do diretório); limpeza
   de temporários; teste de fault injection (morte antes do replace → arquivo íntegro).
7. **Gates não fail-closed** — v2: gate de empacotamento vira script versionado
   (`scripts/gate-package.sh`, `set -euo pipefail`, venv dedicado `.venv-dev` criado pelo
   próprio script, build + twine check com exit code preservado); cada etapa NOMEIA seus
   testes dirigidos; a façade lista símbolos e exceções exportados nominalmente.

Riscos do v2 ampliados com os dominantes apontados: lost update, crash consistency,
ABA/fencing, skew de relógio/heartbeat, identidade do projeto no XDG, integração entre os
dois locks.
