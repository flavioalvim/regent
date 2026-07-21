# PLAN-004 — Condução fase 2: o turno supervisionado com executor confinado

## Objetivo

`regent turn run` executa UM turno de produção com um `claude -p` **confinado** — o
mecanismo provado no LOTE-02 da IMP-003, reimplementado sobre a fundação do regent: o
agente só escreve dentro do **envelope** declarado (hook PreToolUse nega o resto), cada
evento é autenticado por **HMAC com segredo por turno** (o agente não consegue forjar o
log), e quem roda gate, registra evidência e **commita é o SUPERVISOR** — nunca o agente.

## Escopo

**Dentro:** `src/regent/conduction/{confine,hookscript,turnlog,turn}.py` + subcomando
`regent turn run`; o próprio hook (script standalone que o Claude Code invoca); testes com
`fake-claude` injetado (suíte determinística sem o claude real); e2e com fake-claude;
smoke manual opcional com claude real (registrado, não gate).

**Fora (fase 3):** daemon/loop contínuo, decisão automática de próximo turno, activation
rules, `--abort`, ensaio, publicação PyPI.

## Contratos normativos

### Composição do confinamento (`confine.py`)
- Diretório PRIVADO por turno (tmpdir do supervisor, fora do repo): `settings.json`
  gerado (hooks PreToolUse+PostToolUse apontando para a CÓPIA privada do hook script,
  com env `REGENT_TURN_SECRET` (32 bytes hex por turno), `REGENT_ENVELOPE` (JSON de
  paths) e `REGENT_EVENT_LOG` (path privado do log)); imutável durante o turno.
- Lançamento: `claude -p <prompt> --settings <private-settings> --permission-mode
  acceptEdits` **sem Bash** na lista de tools (lição empírica IMP-003/LOTE-02:
  acceptEdits é obrigatório — o confinamento é o DENY do hook; dontAsk nega tudo).
  stdin=DEVNULL; start_new_session; timeout mata o grupo (runner do PLAN-003).
- O prompt do turno recebe o envelope e a tarefa; o agente NUNCA recebe o segredo por
  argumento (só via env do hook — o processo do claude não o vê).

### O hook (`hookscript.py` — standalone, copiado para o dir privado)
- PreToolUse: permite Write/Edit/MultiEdit SOMENTE em paths cujo real-path (após resolver
  symlinks/`..`) esteja DENTRO do envelope; qualquer outra ferramenta de
  escrita/execução (Bash incluso, defesa em profundidade) = DENY. Decisões não-write
  (Read etc.) = allow.
- PostToolUse: apenda ao event log UMA linha JSON
  `{seq, tool, path, decision, content_sha256, hmac}` onde `hmac =
  HMAC(secret, seq‖tool‖path‖decision‖content_sha256‖hmac_anterior)` — CADEIA (remoção/
  reordenação/injeção detectáveis).
- O hook falha FECHADO: qualquer erro interno → DENY + evento `hook_error`.

### Verificação pós-turno (`turnlog.py`)
- Recomputa a cadeia HMAC do log com o segredo do turno: quebra em qualquer elo =
  `TURN_TAMPERED`.
- `git status --porcelain` do repo: todo path alterado DEVE (a) estar no envelope E (b)
  ter evento `allow` correspondente no log; senão `TURN_VIOLATION`. Exceção: os
  exceptuados operacionais (`control.json`/`audit.jsonl`) seguem a coreografia do
  PLAN-002 (atribuibilidade via `regent control explain`).
- Nada é "consertado" automaticamente: violação = falha fail-closed com relatório; o
  worktree fica para o mediador decidir (default-deny, P-03 na prática).

### `regent turn run`
`regent turn run --prompt-file P --envelope <path> [--envelope ...] --gate-command C
--declared-in <plan> --artifact-dir DIR --linkage L [--timeout 1800] [--claude-bin B]`
- Pré-condições: atividade `build` ACTIVE com token corrente (camada de aplicação;
  heartbeat no início e entre TODAS as fases); `stop check` entre fases — stop presente =
  suspensão canônica com checkpoint da fase.
- Sequência: compose → launch → verify (turnlog) → gate (`run_gate` do PLAN-003) →
  evidência `DIR/TURN-<linkage-slug>.md` (header: `outcome: TURN_OK|TURN_VIOLATION|
  TURN_TAMPERED|GATE_RED|TIMEOUT|FAILURE`, exit do claude, resumo de eventos, paths
  tocados, digest do log; corpo: log de eventos íntegro) — conjunto atômico do PLAN-003
  (evidência nunca sobrescrita, órfãos limpos) → **commit do SUPERVISOR**: stage
  arquivo-a-arquivo SÓ (envelope tocado com evento allow) + artefatos do turno +
  exceptuados atribuíveis; trailer `Regent-Turn: <linkage>`; agente jamais commita.
- stdout JSON `{"ok": bool, "outcome", "files_committed": [...], "artifact", "commit":
  sha|null}`; exit 0 SÓ com TURN_OK+GREEN; códigos novos declarados: `TURN_VIOLATION`(3),
  `TURN_TAMPERED`(3), `TURN_FAILED`(3) — catálogo estendido.
- Gate RED: SEM commit de produto; evidência commitada em commit operacional; exit
  GATE_RED (o chamador decide re-tentar turno novo).

### Injeção para testes
Runner injetável (PLAN-003) + `fake-claude` (script sh que lê REGENT_* do settings
gerado?— NÃO: o fake simula o AGENTE: recebe --settings, executa "escritas" chamando o
hook real como o Claude Code faria: invoca o hook PreToolUse/PostToolUse com payloads
JSON reais). Os testes exercitam o HOOK VERDADEIRO (não um mock dele) em todos os
cenários: permitido, fora-do-envelope negado, Bash negado, cadeia HMAC íntegra,
adulteração detectada (linha editada/removida/injetada/reordenada), hook_error fail-closed.

## Etapas

### STEP-01 — Hook + cadeia autenticada (`hookscript.py`, `turnlog.py`)
- **Testes:** `test_hook_allows_envelope_write`, `test_hook_denies_outside_envelope`,
  `test_hook_denies_symlink_and_dotdot_escape`, `test_hook_denies_bash_and_exec_tools`,
  `test_hook_error_fails_closed`, `test_chain_verifies_clean_log`,
  `test_chain_detects_{edit,removal,injection,reorder}`, `test_verify_flags_unlogged_change`,
  `test_verify_respects_operational_exemptions`.
- **Gate:** `PYTHONPATH=src python3 -m unittest discover -s tests`

### STEP-02 — Composição do confinamento (`confine.py`)
- **Testes:** `test_compose_private_dir_immutable_settings`,
  `test_secret_only_in_hook_env_not_argv`, `test_claude_argv_has_no_bash_tool`,
  `test_permission_mode_acceptedits_forced`, `test_compose_cleanup_on_failure`.
- **Gate:** `PYTHONPATH=src python3 -m unittest discover -s tests`

### STEP-03 — `regent turn run` (orquestração + commit do supervisor)
- **Testes:** `test_turn_ok_commits_only_enveloped_files_with_trailer`,
  `test_turn_violation_fails_closed_no_product_commit`,
  `test_turn_tampered_detected`, `test_gate_red_no_product_commit_evidence_operational`,
  `test_stop_between_phases_suspends_with_phase_checkpoint`,
  `test_requires_active_build_activity_and_token`,
  `test_heartbeats_at_every_phase`, `test_timeout_kills_claude_group`.
- **Gate:** `PYTHONPATH=src python3 -m unittest discover -s tests`

### STEP-04 — Consolidação 0.6.0
Skills: seção de build do `/regent` ganha o turno mecanizado como opção prescrita
(anti-drift); e2e fake-claude completo (turno OK + violação) registrado; smoke manual
com claude real REGISTRADO se disponível (não-gate); versão 0.6.0.
- **Testes:** `test_cli_version_reports_060`, anti-drift atualizado.
- **Gate:** `bash scripts/gate-package.sh`

## Riscos

1. **Formato dos hooks do Claude Code muda entre versões** → o hook lê o payload JSON
   documentado e falha FECHADO em formato desconhecido (DENY); smoke manual registrado.
2. **Fake-claude divergir do real** → o fake invoca o HOOK verdadeiro com payloads reais;
   o contrato testado é o do hook, não o do claude.
3. **Escapes de path (symlink/../case)** → real-path canônico antes do teste de envelope
   (teste dedicado).
4. **Agente lendo o segredo** → segredo só no env DO HOOK (settings privado), nunca em
   argv/prompt; teste de composição garante.
5. **Commit contaminado** → staging arquivo-a-arquivo da interseção (envelope ∩ eventos
   allow ∩ git status) + coreografia dos exceptuados (PLAN-002).

## Idioma
Código/CLI/artefatos em inglês (REQ-002); este PLAN.md em PT (mediador PT-BR).
