# PLAN-006 (v2) — Condução fase 4:

*v2 após ADVISOR-REVIEW-1 (6 objeções incorporadas — ver CLAUDE-REBUTTAL.md). Mudanças:
arm-token com arm_id+token+config-do-loop (crash-safe, CAS por arm_id); guard por turno no
run_loop (revalida o arm; DISARMED); arm com pré-condições duras; e COMPLETE do loop =
STEPS_COMPLETE (a revisão final + CONCLUSION + conclude ficam com o MEDIADOR, não o daemon).*

## Condução fase 4: ensaio, ativação e daemon supervisor

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
- `regent arm --plan PLAN-NNN --prompt-template <p> --envelope <e> [--envelope ...]
  [--gate-envelope ...] --declared-in <PLAN.md> --artifact-dir <build> [--max-turns N=20]
  [--timeout 900]` grava o arm-token ATÔMICO (tmp+fsync+rename+fsync do dir) no XDG:
  `{arm_id(uuid4), plan_id, activity_epoch, turn_token, armed_at, config:{prompt_template,
  envelope, gate_envelope, declared_in, artifact_dir, max_turns, timeout}}`. **Pré-condições
  DURAS:** exige atividade `build` ACTIVE cujo id == o plano, `APPROVAL.md` APPROVED, SEM
  `build/CONCLUSION.md`, workspace verdict executável e token CORRENTE (vincula a esse
  token). Sem atividade correspondente = erro (NUNCA autoriza atividade futura). Config
  validada (paths canônicos, gate por step). Outro plano já armado = `ALREADY_ARMED`.
- `regent disarm [--arm-id ID]` remove o arm-token por CAS de arm_id (um daemon antigo com
  arm_id A NUNCA apaga um rearm B); sem --arm-id remove o corrente; idempotente.
- Leitura do arm-token VALIDA arm_id+plan+epoch+token; obsoleto (takeover trocou o token, ou
  epoch mudou) = ignorado + auditado (nunca sobrevive a um ciclo/takeover).
- Armar é do DONO. O daemon LÊ; nunca arma.

### `regent daemon run` (foreground supervisor)
`regent daemon run [--poll 5] [--claude-bin B] [--once]` — LÊ toda a config do loop do
arm-token (não recebe args de loop). Loop:
- **Não age sem arm-token VÁLIDO** (arm_id+plan+epoch+token casando) para uma `build` ACTIVE
  APPROVED, sem CONCLUSION.md, workspace executável: senão → `IDLE` (aguarda; ou sai `--once`).
- Com condições satisfeitas: dirige o build via `run_loop` (config do arm), passando um
  `guard` que REVALIDA o arm ANTES de cada turno (arm_id/plan/epoch/token/APPROVED/
  não-concluído); guard falho (desarme, takeover, sinal) → o loop PARA com `DISARMED` (o
  turno em voo termina ou é abortado pela via de abort; o guard só barra INICIAR o próximo).
  Ao retornar:
  - `COMPLETE` (nenhum STEP pendente) → **DESARMA** e reporta `STEPS_COMPLETE`. O daemon
    NÃO faz a revisão final, NÃO cria CONCLUSION.md, NÃO conclui a atividade — isso é DECISÃO
    MEDIADA do dono (/regent). "STEPs feitos" ≠ "build aceito".
  - `STOPPED`/`ABORTED`/`DISARMED` → atividade SUSPENDED/parada; **DESARMA** e reporta.
  - `HALTED`/`MAX_TURNS`/`LOOP_*`/`PLAN_NOT_EXECUTABLE` → **DESARMA** e reporta. Nunca
    re-tenta sozinho.
- Entre ciclos: desarme → para; stop-request → honra e para; SIGINT/SIGTERM → desarma e sai.
- `--once`: um ciclo e sai.
- stdout: linha JSON por transição (`IDLE`/`RUNNING`/`STEPS_COMPLETE`/`HALTED`/...); exit 0
  se STEPS_COMPLETE ou IDLE-por-desarme; ≠0 em falha terminal.

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
  `test_daemon_respects_stop_request`, `test_daemon_reports_steps_complete_not_accepted`,
  `test_daemon_guard_disarm_stops_between_turns`,
  `test_arm_refuses_without_matching_active_build`,
  `test_arm_token_stale_after_takeover_ignored`,
  `test_disarm_cas_old_id_does_not_remove_rearm`.
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
