# PLAN-006 — Condução fase 4: ensaio, ativação e daemon supervisor

## Objetivo

Fecha a condução com o SUPERVISOR em três capacidades sobre a fundação do loop (PLAN-005):
1. **Ensaio** (`regent rehearse`): prevê os turnos que o loop faria (STEPs pendentes + seus
   gates) SEM lançar agentes nem tocar o repo — read-only.
2. **Ativação** (`regent arm`/`disarm`): um gate de segurança DURÁVEL — o daemon só age
   sobre um plano ARMADO pelo dono; nunca inicia trabalho autônomo sem armar.
3. **Daemon** (`regent daemon run`): loop supervisor em PRIMEIRO PLANO que, enquanto armado
   E o plano é executável, dirige o build aprovado até conclusão (via loop run), respeitando
   stop/abort/desarme; para em terminal e reporta.

## Escopo

**Dentro:** `src/regent/conduction/supervisor.py` + `regent rehearse|arm|disarm|daemon`;
arm-token durável no XDG (fora do repo); testes fake-claude. **Fora (fase 5, declarada):**
daemonização em BACKGROUND desanexada (detach/PID file/logs persistentes), regras de
ativação AUTOMÁTICA (armar sozinho), notificações, decisão de INICIAR um build sem plano
aprovado.

## Contratos normativos

### `regent rehearse` (read-only, sem efeitos)
`regent rehearse --plan PLAN-NNN --declared-in <PLAN.md canônico>` — imprime, SEM tocar o
repo nem lançar agente: STEPs declarados; quais já feitos (trailer commitado + arquivo em
HEAD, reusando a lógica do loop); os STEPs PENDENTES em ordem com seus gates declarados; a
próxima tentativa (tryK) de cada. Não exige atividade ACTIVE (é diagnóstico). stdout JSON
`{"plan": ..., "done": [...], "pending": [{"step", "gate", "next_attempt"}], "complete":
bool}`; exit 0 sempre (é leitura). Erros de leitura/parse = `USAGE`/`CORRUPT`.

### Ativação (`regent arm`/`disarm`) — gate de segurança durável
- `regent arm --plan PLAN-NNN [--max-turns N]` grava atomicamente (tmp+rename) o arm-token
  no XDG (`arm.token`): `{plan_id, armed_at, max_turns, activity_epoch}`. Um arm-token
  presente para outro plano = `ALREADY_ARMED` (desarme primeiro). Vincula ao epoch corrente
  da atividade build (se houver) para não sobreviver a um ciclo.
- `regent disarm` remove o arm-token (idempotente; sem token = no-op reportado).
- O arm-token NUNCA sobrevive silenciosamente a uma troca de plano/epoch: leitura valida o
  vínculo; obsoleto = ignorado + auditado.
- Armar é do DONO (mediador). O daemon LÊ; nunca arma.

### `regent daemon run` (foreground supervisor)
`regent daemon run [--poll 5] [--claude-bin B] [--once]` — loop:
- **Não age sem arm-token válido** para uma atividade `build` ACTIVE cujo plano == o armado,
  APPROVED, epoch casando: sem isso → estado `IDLE` (aguarda; ou sai com `--once`).
- Com condições satisfeitas: adquire o LOOP (herda o loop lock do PLAN-005 — o daemon é só
  outro processo que chama run_loop), dirige o build via `run_loop` com o `max_turns`
  armado. Ao retornar:
  - `COMPLETE` → **DESARMA automaticamente** (o trabalho acabou; segurança) e reporta
    `COMPLETED`.
  - `STOPPED`/`ABORTED` → a atividade ficou SUSPENDED; o daemon **DESARMA** (exige nova
    ordem do dono) e reporta a condição.
  - `HALTED`/`MAX_TURNS`/`LOOP_*`/`PLAN_NOT_EXECUTABLE` → **DESARMA** e reporta (mediador
    decide). Nunca re-tenta sozinho.
- Entre ciclos, checa: desarme (arm-token sumiu) → para; stop-request pendente → honra e
  para; SIGINT/SIGTERM → desarma e sai graciosamente (foreground).
- `--once`: um ciclo e sai (útil para teste e para orquestração externa).
- stdout: linha JSON por transição de estado (`IDLE`/`RUNNING`/`COMPLETED`/`HALTED`/...);
  exit 0 se terminou em COMPLETED ou IDLE-por-desarme; ≠0 em condição de falha terminal.

### Segurança declarada (o cerne da fase 4)
O daemon é AUTÔNOMO por turno mas NÃO por decisão de INICIAR: sem arm-token do dono, ele
nunca dirige. Qualquer condição não-COMPLETE desarma (o dono re-arma conscientemente). O
desarme automático pós-terminal impede o daemon de "ressuscitar" trabalho já concluído ou
falho. Arm-token vinculado ao epoch impede sobrevivência a um ciclo de atividade.

## Etapas

### STEP-01 — Ensaio (`supervisor.py` rehearse) + arm/disarm durável
- **Testes:** `test_rehearse_lists_pending_steps_and_gates`,
  `test_rehearse_is_read_only`, `test_rehearse_complete_plan`,
  `test_arm_writes_bound_token`, `test_arm_other_plan_is_already_armed`,
  `test_disarm_idempotent`, `test_arm_token_stale_epoch_ignored`.
- **Gate:** `PYTHONPATH=src python3 -m unittest discover -s tests`

### STEP-02 — Daemon supervisor (`supervisor.py` run_daemon)
- **Testes:** `test_daemon_idle_without_arm`, `test_daemon_drives_armed_plan_to_complete`,
  `test_daemon_disarms_after_complete`, `test_daemon_disarms_on_halted`,
  `test_daemon_disarms_on_stopped`, `test_daemon_stops_on_disarm_between_cycles`,
  `test_daemon_once_single_cycle`, `test_daemon_never_acts_on_unarmed_plan`,
  `test_daemon_respects_stop_request`.
- **Gate:** `PYTHONPATH=src python3 -m unittest discover -s tests`

### STEP-03 — CLI `regent rehearse|arm|disarm|daemon`
- **Testes:** `test_rehearse_cli_json`, `test_arm_disarm_cli`,
  `test_daemon_run_cli_once`, `test_daemon_exit_codes`.
- **Gate:** `PYTHONPATH=src python3 -m unittest discover -s tests`

### STEP-04 — Consolidação 0.8.0
Skill de build: rehearse (prever) + arm + daemon como o fluxo hands-off supervisionado
(anti-drift); e2e real fake-claude (arm → daemon --once dirige 2 STEPs → COMPLETE →
desarma); versão 0.8.0.
- **Testes:** `test_cli_version_reports_080`, anti-drift.
- **Gate:** `bash scripts/gate-package.sh`

## Riscos
1. Daemon age sem ordem → arm-token OBRIGATÓRIO + vínculo epoch; sem arm = IDLE.
2. Ressuscitar trabalho terminado → desarme automático em TODA condição terminal.
3. Loop dentro do daemon → herda loop lock (PLAN-005); `--once` para teste.
4. Sinais no foreground → SIGINT/SIGTERM desarmam e saem graciosamente.
5. arm-token órfão (troca de plano/epoch) → validado na leitura; obsoleto ignorado+auditado.

## Idioma
Código/CLI/artefatos em inglês (REQ-002); este PLAN.md em PT (mediador PT-BR).
