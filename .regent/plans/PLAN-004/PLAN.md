# PLAN-004 (v3) — Condução fase 2: o turno supervisionado com executor confinado

*v2 após ADVISOR-REVIEW-1 (7 objeções). v3 incorpora VERBATIM os 3 residuais do
ADVISOR-REVIEW-2 nos CONTRATOS: (1) vínculo rígido de --step ao plano aprovado + STEP
corrente + gate daquele STEP + criação normativa de build/STEP-NN.md; (2) ordem
GATED→VERIFIED com a prova cobrindo os efeitos do gate por RE-BASELINE (o gate escreve
seus efeitos e a verificação final atribui TUDO — envelope declara os paths de efeito do
gate); (3) fases com CHECKPOINT DURÁVEL no control + recuperação trailer→STEP→worktree +
testes de crash por fronteira. Mudança central herdada do v2: prova de atribuição no GIT;
HMAC = auditoria.*

## Objetivo

`regent turn run` executa UM turno de produção de um STEP de build com um `claude -p`
**confinado**: o agente só ESCREVE dentro do envelope (hook PreToolUse DENY — garantia
primária de confinamento), e quem verifica, roda gate, registra evidência e **commita é o
SUPERVISOR** por índice privado com prova git (garantia primária de atribuição). É COMO um
STEP do REQ-005 é executado por um agente, não um caminho paralelo.

## Modelo de confiança (explícito)

Single-host, agente SEMI-CONFIÁVEL. Assumimos que o agente PODE ler qualquer arquivo
(inclusive o segredo). Portanto:
- **Confinamento** = hook PreToolUse DENY (o agente não CONSEGUE escrever fora do
  envelope), reforçado por `--tools` restritivo e config isolada.
- **Atribuição** = GIT verificado pelo supervisor (baseline limpo → diff global == conjunto
  atribuído, blobs conferidos), NÃO o HMAC.
- **HMAC** = auditoria: detecta corrupção acidental e adulteração por TERCEIROS do log;
  declarado como tal, sem alegar anti-forja do agente.

## Escopo

**Dentro:** `src/regent/conduction/{confine,hookscript,turnlog,turn}.py` + `regent turn
run`; o hook standalone; testes exercitando o HOOK REAL + `fake-claude` (simula o agente
invocando o hook com payloads reais); e2e fake-claude; smoke opcional com claude real
(registrado, não-gate).

**Fora (fase 3):** daemon/loop, decisão de próximo turno, activation rules, `--abort`,
ensaio, publicação PyPI.

## Contratos normativos

### Confinamento (`confine.py`)
- Dir PRIVADO por turno (tmpdir do supervisor, FORA do repo): `settings.json` gerado com
  hooks Pre/PostToolUse apontando para a CÓPIA privada de `hookscript.py`. Env do lançamento
  MÍNIMO (allowlist: PATH, HOME, e os `REGENT_*`); imutável no turno.
- Launch: `claude -p <prompt> --setting-sources "" --settings <priv> --tools
  Read,Write,Edit,MultiEdit --permission-mode acceptEdits` (sem Bash; acceptEdits é lição
  empírica IMP-003 — o confinamento é o DENY do hook). stdin=DEVNULL; start_new_session;
  timeout mata o grupo. `--setting-sources ""` = NENHUMA config herdada (user/project/
  local/plugins/MCP).
- Segredo (`REGENT_TURN_SECRET`, 32B hex) e `REGENT_ENVELOPE`/`REGENT_EVENT_LOG` vão no
  env do hook via settings privado. NÃO alegamos que o agente não os vê (modelo de
  confiança acima).

### Hook (`hookscript.py`, standalone — semântica oficial do Claude Code)
- **PreToolUse** (recebe `tool_name`, `tool_input`, `tool_use_id`): Write/Edit/MultiEdit
  → allow SÓ se o real-path canônico (symlinks + `..` resolvidos) ∈ envelope; senão deny.
  Qualquer outra tool de escrita/execução = deny (defesa em profundidade). Read etc. =
  allow. Emite evento `pre` com `decision: allow|deny` correlacionado por `tool_use_id`.
- **PostToolUse** (após sucesso da escrita): emite evento `post` com `content_sha256` do
  arquivo resultante, correlacionado ao `tool_use_id`. (DENY não gera Post — por desenho.)
- Append ao log: 1 linha JSON canônica (sort_keys) sob **flock** (hooks concorrentes),
  com `seq` monotônico e `hmac = HMAC(secret, canonical_line_sem_hmac ‖ hmac_anterior)`.
- Falha FECHADA: erro interno → deny + evento `hook_error`.

### Verificação pós-turno (`turnlog.py`) — PROVA PELO GIT
1. **Cadeia HMAC** recomputada + **selo terminal** que o supervisor grava ao fim (ausência
   = log truncado/removido) → quebra = `TURN_TAMPERED`.
2. **Diff global == conjunto atribuído:** baseline = HEAD limpo (pré-condição). Após o
   turno: para CADA path em `git status --porcelain`:
   - deve ∈ envelope (ou ser exceptuado operacional PLAN-002);
   - o `content_sha256` do blob no worktree deve casar o do último evento `post` daquele
     `tool_use_id`/path; tipo/modo/deleção conferidos;
   - nenhum path alterado sem evento `post` correspondente.
   Qualquer divergência = `TURN_VIOLATION`. Nada é consertado (default-deny; worktree fica
   para o mediador).
3. **Efeitos do gate:** o gate roda ANTES da verificação; o que o gate tocou é submetido à
   MESMA prova — path fora do envelope tocado pelo gate = violação (o envelope deve
   declarar os paths que o gate legitimamente altera, ex.: `dist/` no gate-package).

### `regent turn run`
`regent turn run --prompt-file P --envelope <path> [--envelope ...] --gate-command C
--declared-in <plan> --step <PLAN-NNN/STEP-NN> --artifact-dir <sob .regent/> --linkage L
[--timeout 900] [--claude-bin B]`
- **Pré-condições (vínculo REQ-005 rígido):** atividade `build` ACTIVE cujo `id` == o
  `PLAN-NNN` de `--step`; `--step` referencia um STEP EXISTENTE no `PLAN.md` do
  `--declared-in`, e é o STEP CORRENTE (o menor STEP-NN sem `build/STEP-NN.md`); o
  `--gate-command` DEVE ser o gate declarado DAQUELE STEP (não um gate qualquer do plano);
  token corrente; `--artifact-dir` sob `.regent/` (REQ-001) senão erro; **worktree limpo**
  exceto exceptuados. O turno PRODUZ `build/STEP-NN.md` (files touched, gate outcome,
  turno) como parte do commit — é assim que um STEP do REQ-005 nasce.
- **Fases** (checkpoint DURÁVEL no control por fase; heartbeat antes de cada; `stop check`
  entre elas → suspensão canônica com checkpoint da fase):
  COMPOSED → LAUNCHED (claude confinado; keep-alive em thread) → GATED (`run_gate` do
  PLAN-003 APÓS o agente; heartbeat antes) → VERIFIED → COMMITTED.
  **A prova cobre os efeitos do gate:** o envelope declara os paths que o gate
  legitimamente escreve (ex.: `dist/`); a verificação final roda DEPOIS do gate e atribui
  TODO o diff global — paths de agente exigem evento `post`; paths de efeito-de-gate são
  aceitos SÓ se ∈ envelope-de-gate declarado (subconjunto marcado do envelope), senão
  `TURN_VIOLATION`. Nada alterado escapa da prova nem é falsamente atribuído ao agente.
- **Commit do SUPERVISOR** (nunca o agente): índice PRIVADO (`GIT_INDEX_FILE`), stage
  arquivo-a-arquivo APENAS do conjunto atribuído (envelope ∩ eventos post ∩ diff) +
  artefatos do turno + exceptuados atribuíveis; **CAS de HEAD** (se HEAD mudou desde o
  baseline → aborta, `CONFLICT`); trailer `Regent-Step: PLAN-NNN/STEP-NN` +
  `Regent-Turn: <linkage>`.
- Evidência `--artifact-dir/TURN-<slug>.md` (conjunto atômico PLAN-003; header:
  `outcome: TURN_OK|TURN_VIOLATION|TURN_TAMPERED|GATE_RED|TIMEOUT|FAILURE`, claude_exit,
  resumo de eventos, paths atribuídos, digest do log; corpo: log íntegro). Persistida em
  TODO desfecho.
- stdout JSON `{"ok": bool, "outcome", "files_committed": [...], "artifact",
  "commit": sha|null}`; exit 0 SÓ com TURN_OK+GREEN. Códigos novos declarados:
  `TURN_VIOLATION`(3), `TURN_TAMPERED`(3), `TURN_FAILED`(3).
- **Gate RED / violação:** SEM commit de produto; evidência entra em commit OPERACIONAL;
  exit ≠0 (o chamador decide turno novo).

### Recuperação por fase (durável, idempotente)
Cada transição de fase grava o nome da fase no checkpoint da atividade (control, via a
camada de aplicação — reusa `suspend`/estado). Recuperação por inspeção, nesta ordem:
**trailer** (`git log --grep Regent-Turn:<linkage>` → COMMITTED, nada a fazer) →
**STEP file** (`build/STEP-NN.md` presente → turno concluído) → **worktree/log**
(log presente e íntegro → re-VERIFY+GATE+commit; log ausente/parcial → turno abortado,
worktree sujo reportado ao mediador, NUNCA commitado). Reexecutar agente NÃO é idempotente
por si — por isso um turno interrompido em LAUNCHED sem VERIFIED completo é DESCARTADO
(worktree revertido aos paths do envelope só com ordem do mediador), não retomado no meio
do agente. Testes de crash por fronteira (LAUNCHED/GATED/VERIFIED/pré-commit) validam.

### Fencing de token e timeout
Timeout default do turno = **900s** (< `stale_after` 1800s da fase 1); heartbeats
keep-alive em thread durante launch e gate para o token NUNCA virar suspect a meio-turno;
o commit reverifica o token (fencing) antes de gravar.

### Injeção para testes
`fake-claude` = script que simula o AGENTE: recebe `--settings`, lê o hook configurado e o
INVOCA com payloads PreToolUse/PostToolUse reais (JSON) para cada "escrita" que tenta —
exercitando o HOOK VERDADEIRO. Cenários: escrita no envelope (allow+post), fora do
envelope (deny, sem escrita), Bash (deny), symlink/`..` escape (deny), cadeia íntegra,
adulteração (edição/remoção/injeção/reordenação/remoção-do-último), hook_error.

## Etapas

### STEP-01 — Hook + cadeia + selo (`hookscript.py`, `turnlog.py`)
- **Testes:** `test_hook_allows_envelope_write`, `test_hook_denies_outside_envelope`,
  `test_hook_denies_symlink_and_dotdot_escape`, `test_hook_denies_bash_and_exec_tools`,
  `test_hook_error_fails_closed`, `test_pre_post_correlated_by_tool_use_id`,
  `test_chain_verifies_clean_log_with_terminal_seal`,
  `test_chain_detects_{edit,removal,injection,reorder,last_event_removal}`,
  `test_missing_terminal_seal_is_tampered`, `test_concurrent_append_flock_serialized`.
- **Gate:** `PYTHONPATH=src python3 -m unittest discover -s tests`

### STEP-02 — Confinamento + prova git (`confine.py`, verificação de diff em `turnlog.py`)
- **Testes:** `test_compose_isolated_settings_sources_empty`,
  `test_claude_argv_tools_restrictive_no_bash`, `test_permission_mode_acceptedits_forced`,
  `test_env_is_minimal_allowlist`, `test_compose_cleanup_on_failure`,
  `test_diff_equals_attributed_set_ok`, `test_unlogged_change_is_violation`,
  `test_blob_sha_mismatch_is_violation`, `test_gate_touching_outside_envelope_violation`,
  `test_operational_exemptions_pass`.
- **Gate:** `PYTHONPATH=src python3 -m unittest discover -s tests`

### STEP-03 — `regent turn run` (orquestração + commit por índice privado)
- **Testes:** `test_turn_ok_commits_attributed_set_with_step_and_turn_trailers`,
  `test_supervisor_commit_uses_private_index_and_head_cas`,
  `test_turn_violation_fails_closed_no_product_commit`, `test_turn_tampered_detected`,
  `test_gate_red_no_product_commit_evidence_operational`,
  `test_stop_between_phases_suspends_with_phase_checkpoint`,
  `test_requires_active_build_activity_and_token`, `test_artifact_dir_must_be_under_regent`,
  `test_step_must_be_current_and_belong_to_declared_plan`,
  `test_gate_command_must_match_step_gate`, `test_produces_step_nn_md`,
  `test_head_moved_since_baseline_conflicts`, `test_timeout_kills_claude_group`,
  `test_keepalive_heartbeat_prevents_suspect`,
  `test_recovery_committed_turn_is_noop`, `test_recovery_launched_without_verify_discarded`,
  `test_crash_before_commit_recovered_by_inspection`.
- **Gate:** `PYTHONPATH=src python3 -m unittest discover -s tests`

### STEP-04 — Consolidação 0.6.0
Skill de build do `/regent`: o turno mecanizado como opção prescrita (anti-drift); e2e
fake-claude completo (TURN_OK + violação + tampered) registrado; smoke com claude real
REGISTRADO se disponível (não-gate); versão 0.6.0.
- **Testes:** `test_cli_version_reports_060`, anti-drift atualizado.
- **Gate:** `bash scripts/gate-package.sh`

## Riscos
1. Formato de hook do Claude Code muda → hook lê o payload documentado e falha FECHADO em
   formato desconhecido (deny); smoke real registrado.
2. Fake-claude diverge do real → o fake invoca o HOOK verdadeiro; o contrato testado é o
   do hook.
3. Escapes de path → real-path canônico antes do teste de envelope (teste dedicado).
4. Config herdada → `--setting-sources ""` + env mínimo + `--tools` restritivo (testado).
5. Commit contaminado → prova git (baseline global + blob conferido + índice privado + CAS
   de HEAD); o HMAC é só auditoria.
6. Token suspect a meio-turno → timeout 900 < stale 1800 + heartbeats keep-alive.

## Idioma
Código/CLI/artefatos em inglês (REQ-002); este PLAN.md em PT (mediador PT-BR).
