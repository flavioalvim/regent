# PLAN-004 — Réplica do Claude às 7 objeções do advisor

**Aceito as 7.** A objeção 3 é decisiva: se o agente tem `Read` irrestrito, ele lê o
`settings.json`/`/proc` e o segredo — logo HMAC NÃO prova anti-forja CONTRA O AGENTE. O
desenho v2 REANCORA a prova de atribuição no GIT (a prova de fato provada na IMP-003:
baseline global + blob git verificado + índice privado + CAS de HEAD), e rebaixa o HMAC a
auditoria/defense-in-depth. Mapa objeção→correção (tudo NOS contratos do v2):

1. **Subordinação ao REQ-005:** `regent turn run` NÃO é caminho paralelo — exige atividade
   `build` ACTIVE com um STEP corrente; produz o `build/STEP-NN.md` e commita com o
   trailer `Regent-Step: PLAN-NNN/STEP-NN` (o turno é COMO um STEP é executado, não um
   bypass); worktree limpo por etapa e fases recuperáveis reusam a coreografia do
   PLAN-002/REQ-005; `artifact-dir` DEVE estar sob `.regent/` (REQ-001) — senão erro.
2. **Isolamento de config efetivo:** `claude -p --setting-sources ""` (só o settings
   privado vale), ambiente MÍNIMO allowlisted, `--tools` explicitamente restritivo (só
   Read/Write/Edit/MultiEdit), sem herdar hooks/plugins/MCP.
3. **Modelo de confiança corrigido (o cerne):** a garantia PRIMÁRIA de confinamento é o
   hook PreToolUse DENY (o agente não CONSEGUE escrever fora do envelope); a garantia
   PRIMÁRIA de atribuição é o GIT verificado (não o HMAC). O agente é semi-confiável no
   modelo single-host; assumimos que ele PODE ler o segredo — por isso a prova não
   depende dele. HMAC = detecção de corrupção acidental/adulteração por terceiros
   (auditoria), declarado como tal, não como anti-forja do agente.
4. **Semântica real dos hooks:** PreToolUse decide allow/deny (o DENY confina; não há
   Post em deny); PostToolUse registra sucesso APÓS a escrita; eventos Pre(allow/deny) e
   Post(success/failure) SEPARADOS, correlacionados por `tool_use_id`. O contrato do hook
   segue a doc oficial, não a semântica inventada.
5. **Cadeia + terminação:** o log ganha um SELO TERMINAL esperado escrito pelo supervisor
   (ausência = truncagem/remoção do log inteiro detectada); serialização canônica
   (JSON sort_keys) e lock de append (flock, como o audit) para hooks concorrentes; seq
   monotônico verificado sem bifurcação.
6. **Prova de atribuição pelo GIT (substitui git×envelope×allow ingênuo):** baseline =
   `HEAD` global limpo (o próprio REQ-005); após o turno, o supervisor computa o DIFF
   GLOBAL (`git status --porcelain` + `git diff`) e exige que ele seja IGUAL ao conjunto
   atribuído: cada path alterado ∈ envelope, com `content_sha256` do blob CONFERIDO contra
   o evento, tipo/modo/deleção conferidos; QUALQUER byte fora disso = `TURN_VIOLATION`. O
   gate roda ANTES da verificação-final e da atribuição, e a verificação inclui o que o
   gate tocou (só é aceito se ∈ envelope declarado para efeitos colaterais do gate, senão
   viola); commit por ÍNDICE PRIVADO (GIT_INDEX_FILE) com CAS de HEAD (rejeita se HEAD
   mudou). Regressão à prova provada da IMP-003.
7. **Recuperação + fencing:** fases idempotentes nomeadas (COMPOSED/LAUNCHED/VERIFIED/
   GATED/COMMITTED) com recuperação por inspeção (log presente? diff atribuído? commit
   com trailer?); heartbeat ANTES de launch, ANTES do gate e ANTES do commit; timeout do
   turno < stale_after (default 900s, com heartbeats keep-alive durante launch/gate via
   thread) para o token nunca virar suspect a meio-turno.

Encaminhamento: PLAN v2 reescrito com estes contratos; peço re-opinião.
