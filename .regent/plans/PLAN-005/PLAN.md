# PLAN-005 (v2) — Condução fase 3: o loop de turnos + --abort real

*v2 após ADVISOR-REVIEW-1 (8 objeções incorporadas — ver CLAUDE-REBUTTAL.md). Mudanças
arquiteturais: runner CANCELÁVEL (abort implementável), loop lock (exclusão de processos),
avanço por STEP COMMITADO+trailer, identidade de tentativa (retry), abort-request vinculado,
e roteamento da suspensão pela camada de aplicação (libera o turn lock — emenda declarada ao
caminho de stop do PLAN-004).*

## Objetivo

`regent loop run` encadeia turnos supervisionados (PLAN-004) sobre um plano de build
aprovado até uma condição terminal. Cada turno permanece a unidade auditável; o loop é o
driver determinístico. Inclui `--abort` real (cancelamento imediato do turno em voo).

## Contratos normativos

### Runner cancelável (emenda a `process.py`)
`SubprocessRunner.run(argv, *, cwd, timeout, env=None, cancel=None)`: se `cancel` (um
`threading.Event`) for setado, mata o GRUPO (killpg SIGKILL) e retorna `RunResult` com
`aborted=True` (distinto de `timed_out`). Implementação por POLL (~0.5s) em vez de
`communicate` bloqueante, para checar `cancel` e o timeout na mesma malha.

### abort-request (`loop.py` sinal; XDG, fora do repo)
`regent loop abort --reason R` grava atomicamente (tmp+rename) `abort.request` =
`{id, activity_id, activity_epoch, turn_token, requested_at, reason}` no state dir. Leitura
VALIDA o vínculo (activity_id/epoch/turn_token correntes); obsoleto = descarte auditado;
honra único (rename para `.claimed`). Abort sem turno em voo = no-op registrado.

### Integração na keep-alive do turno (emenda a `turn.py`)
A thread keep-alive passa a: (a) heartbeat; (b) checar o abort-request vinculado a cada
~1s; ao detectá-lo, setar o `cancel` do runner. O turno, ao ver `result.aborted`, define
`outcome=ABORTED`, persiste evidência e SUSPENDE **pela camada de aplicação**
(`service.suspend`, que libera o turn lock — corrige o gap do PLAN-004 em que a suspensão do
protocolo não liberava o lock; o caminho STOPPED também passa a rotear por `service.suspend`).

### `regent loop run`
`regent loop run --plan PLAN-NNN --prompt-template <path> --envelope <path> [...]
--declared-in <PLAN.md canônico> --artifact-dir <build canônico> [--max-turns N=20]
[--gate-envelope ...] [--timeout 900] [--claude-bin B]`
- **Loop lock:** flock em XDG `loop.lock` — segundo `loop run` no mesmo repo = `LOOP_BUSY`.
- **Pré-condições, REVALIDADAS A CADA TURNO:** atividade `build` ACTIVE cujo id == `--plan`;
  `APPROVAL.md` com `status: APPROVED` (senão `PLAN_NOT_EXECUTABLE`); token corrente;
  worktree limpo exceto exceptuados; declared_in/artifact_dir canônicos (herda PLAN-004).
- **STEP corrente:** o menor STEP-NN declarado no PLAN.md SEM commit contendo o trailer
  `Regent-Step: PLAN-NNN/STEP-NN` (git log --grep). STEP file forjado/não-commitado NÃO
  avança. Sem STEP corrente → `COMPLETE`.
- **Tentativa:** para o STEP corrente, K = nº de artefatos `TURN-*` já presentes desse STEP
  + 1; o turno roda com linkage `PLAN-NNN/STEP-NN` e `attempt=K` (run_turn sufixa os nomes
  TURN/GATE com `-tryK` → sem EvidenceConflict ao re-rodar após HALTED).
- **Iteração:** monta o prompt do template (placeholders `{step}`/`{gate}`/`{plan}`
  substituídos pelo STEP corrente e seu gate declarado), roda `run_turn`, mapeia o desfecho.
- **Mapa desfecho→condição (fail-closed, sem auto-retry):**
  `TURN_OK` → avança (recomputa do disco); sem mais STEP → `COMPLETE`.
  `GATE_RED|TURN_VIOLATION|TURN_TAMPERED|FAILURE|TIMEOUT` → `HALTED` (para no 1º).
  `STOPPED` → `STOPPED` (atividade já SUSPENDED). abort honrado → `ABORTED`.
  exceções: NOT_ACTIVE→`PLAN_NOT_EXECUTABLE`; CONFLICT→`LOOP_CONFLICT`;
  WORKTREE_DIRTY→`LOOP_DIRTY`; PROVENANCE/STEP_MISMATCH→`LOOP_MISCONFIGURED`. cap→`MAX_TURNS`.
- **Estado por condição:** COMPLETE/HALTED/MAX_TURNS → atividade ACTIVE com token (mediador
  decide). STOPPED/ABORTED → SUSPENDED sem token.
- **Evidência:** `build/LOOP-<slug>.md` (conjunto atômico PLAN-003): turnos (STEP, attempt,
  outcome, commit), condição de parada, contagem. Op-commit do resumo — COM fencing se há
  token (ACTIVE), SEM fencing se SUSPENDED (as duas vias declaradas).
- **Recuperação:** loop SEM estado próprio (disco = verdade: STEP commits + control +
  loop lock efêmero). Reexecutar continua do STEP corrente; turno mid-agent nunca retomado.
- stdout JSON `{"ok": bool, "stop_condition": ..., "turns": [{step, attempt, outcome,
  commit}], "count": int}`; exit 0 SÓ com `COMPLETE`. Códigos: `LOOP_HALTED`(3),
  `LOOP_ABORTED`(3), `LOOP_MAX_TURNS`(3), `LOOP_STOPPED`(2), `LOOP_BUSY`(3),
  `PLAN_NOT_EXECUTABLE`(2), `LOOP_CONFLICT`(3), `LOOP_DIRTY`(3), `LOOP_MISCONFIGURED`(2).

## Escopo
**Dentro:** `src/regent/conduction/loop.py` + `regent loop run|abort`; emendas a
process.py (cancel) e turn.py (attempt, abort na keepalive, suspensão via app layer);
testes fake-claude. **Fora (fase 4):** daemon background contínuo, ativação automática,
ensaio, decisão de iniciar build sem ordem, notificações.

## Etapas

### STEP-01 — Runner cancelável + abort-request + integração na keep-alive
- **Testes:** `test_runner_cancel_kills_group` (poll, filho morto, aborted=True),
  `test_abort_request_atomic_and_bound`, `test_abort_stale_binding_discarded`,
  `test_abort_claimed_once`, `test_keepalive_detects_abort_sets_cancel`,
  `test_turn_aborted_suspends_via_app_layer_releasing_lock`,
  `test_stop_path_also_releases_lock` (regressão da emenda ao PLAN-004).
- **Gate:** `PYTHONPATH=src python3 -m unittest discover -s tests`

### STEP-02 — run_turn attempt + driver do loop (`loop.py`)
- **Testes:** `test_run_turn_attempt_suffixes_artifacts`,
  `test_loop_runs_all_steps_to_complete`, `test_loop_current_step_needs_committed_trailer`,
  `test_loop_forged_stepfile_does_not_advance`, `test_loop_retry_after_halt_new_attempt`,
  `test_loop_halts_on_gate_red`, `test_loop_halts_on_violation`,
  `test_loop_stops_on_stop_request`, `test_loop_aborts_on_abort_request`,
  `test_loop_respects_max_turns`, `test_loop_revalidates_approval_each_turn`,
  `test_loop_lock_excludes_second_run`.
- **Gate:** `PYTHONPATH=src python3 -m unittest discover -s tests`

### STEP-03 — CLI `regent loop run|abort` + evidência + mapa de estados
- **Testes:** `test_loop_run_cli_json_and_exit_codes`, `test_loop_abort_cli`,
  `test_loop_evidence_committed` (fencido/não-fencido conforme estado),
  `test_exception_to_condition_map`.
- **Gate:** `PYTHONPATH=src python3 -m unittest discover -s tests`

### STEP-04 — Consolidação 0.7.0
Skill de build: o loop como forma de executar um plano inteiro (anti-drift); e2e real
fake-claude (2 STEPs→COMPLETE; abort a meio→ABORTED+SUSPENDED); versão 0.7.0.
- **Testes:** `test_cli_version_reports_070`, anti-drift.
- **Gate:** `bash scripts/gate-package.sh`

## Riscos
1. Loop infinito → cap duro + avanço só por STEP commitado (não-avanço PARA, não repete).
2. Corrida abort × fronteira → abort vinculado+claim único no XDG, checado na keepalive
   (~1s) e honrado uma vez com evidência.
3. Recuperação → loop sem-estado; turno mid-agent nunca retomado (recover_turn).
4. Auto-retry indevido → proibido; retry manual = novo `loop run` (nova tentativa).
5. Token perdido no meio → cada turno fencia; takeover entre turnos → NOT_ACTIVE/CONFLICT
   para o loop.
6. Dois loops → loop lock (flock) exclui processos.

## Idioma
Código/CLI/artefatos em inglês (REQ-002); este PLAN.md em PT (mediador PT-BR).
