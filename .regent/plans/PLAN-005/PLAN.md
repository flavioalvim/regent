# PLAN-005 — Condução fase 3: o loop de turnos + --abort real

## Objetivo

`regent loop run` encadeia turnos supervisionados (PLAN-004) sobre um plano de build
aprovado, sem intervenção turno-a-turno: decide o STEP corrente, executa o turno, e itera
até uma condição de parada terminal (todos os STEPs feitos / violação / gate-red / stop /
cap de turnos / abort). Cada turno permanece a unidade auditável provada; o loop é apenas o
DRIVER determinístico em cima dela. Inclui `--abort`: cancelamento cooperativo do turno em
voo (mata o grupo do agente, registra evidência, suspende), fechando a lacuna declarada da
fase 2.

## Escopo

**Dentro:** `src/regent/conduction/loop.py` + `regent loop run`; sinalização de abort
(arquivo de controle no XDG lido pela thread keep-alive do turno) + `regent loop abort`;
decisão de próximo STEP a partir do PLAN.md + build/STEP-NN.md; política de parada; testes
com fake-claude (loop de N STEPs, parada por cada condição, abort).

**Fora (fase 4, declarada):** daemonização em background contínua (desanexar processo,
supervisão persistente), regras de ativação automática, ensaio opt-in, decisão de INICIAR
um build sem ordem, notificações; publicação PyPI é decisão do dono.

## Contratos normativos

### `regent loop run`
`regent loop run --plan PLAN-NNN --prompt-template <path> --envelope <path> [...]
--declared-in <PLAN.md> --artifact-dir <build canônico> [--max-turns N=20]
[--gate-envelope ...] [--timeout 900] [--claude-bin B]`
- **Pré-condições:** atividade `build` ACTIVE cujo id == `--plan`; token corrente;
  worktree limpo exceto exceptuados; `--declared-in`/`--artifact-dir` = os canônicos do
  plano (herda as checagens do PLAN-004).
- **Iteração:** enquanto houver STEP corrente (menor STEP-NN declarado sem `build/STEP-NN.md`)
  E turnos < max_turns E sem abort/stop: monta o prompt do turno do template (com o STEP e
  o gate daquele STEP extraídos do PLAN.md), roda `run_turn` (PLAN-004) com linkage
  `PLAN-NNN/STEP-NN`; a decisão do próximo STEP é RECOMPUTADA do disco a cada volta (o STEP
  file recém-commitado avança o estado — fonte única).
- **Parada terminal (fail-closed):**
  - `TURN_OK` → avança; se não há mais STEP corrente → `COMPLETE` (todos os STEPs feitos).
  - `GATE_RED`/`TURN_VIOLATION`/`TURN_TAMPERED`/`FAILURE`/`TIMEOUT` → PARA no primeiro
    (`HALTED`, com o outcome e o STEP); nunca "tenta de novo" sozinho (retry é decisão do
    dono/mediador — YAGNI de auto-retry).
  - `STOPPED` (stop-request honrado pelo turno) → `STOPPED` (a atividade já ficou SUSPENDED).
  - abort sinalizado → o turno em voo é cancelado → `ABORTED`.
  - cap atingido → `MAX_TURNS`.
- **Idempotência/recuperação:** o loop não tem estado próprio além do disco (STEP files +
  control + commits com trailer). Reexecutar `loop run` após uma parada continua do STEP
  corrente. Um turno interrompido a meio deixa o worktree para o mediador (recover_turn do
  PLAN-004); o loop NÃO retoma mid-agent.
- **Evidência:** cada turno já persiste seu artefato. O loop grava
  `build/LOOP-<slug>.md` (conjunto atômico PLAN-003) com: turnos executados (STEP, outcome,
  commit), condição de parada, contagem; commit OPERACIONAL do resumo (fencido).
- stdout JSON `{"ok": bool, "stop_condition": ..., "turns": [{step, outcome, commit}],
  "count": int}`; exit 0 SÓ com `COMPLETE`. Códigos novos: `LOOP_HALTED`(3),
  `LOOP_ABORTED`(3), `LOOP_MAX_TURNS`(3), `LOOP_STOPPED`(2).

### `--abort` real (`regent loop abort` + sinal lido no turno)
- `regent loop abort --reason R` grava um **abort-request durável** no XDG state
  (`abort.request`: {id, requested_at, reason}) — canal fora do repo, como o turn lock.
- A thread keep-alive do turno (PLAN-004) passa a checar o abort-request a cada heartbeat;
  ao detectá-lo, sinaliza o cancelamento: mata o grupo do processo do agente (killpg,
  reusando o runner), o turno registra evidência `outcome: ABORTED` e SUSPENDE a atividade
  (canônico); o loop retorna `ABORTED`. O abort-request é consumido (removido) ao ser
  honrado. Abort sem turno em voo = no-op registrado.
- Distinção declarada: **stop** = gracioso, em fronteira, entre turnos/sub-passos;
  **abort** = imediato, mata o agente em voo. Ambos suspendem a atividade (retomável).

### Prompt template
Texto com placeholders `{step}` e `{gate}` (e opcionalmente `{plan}`); o loop os
substitui pelo STEP corrente e seu gate declarado. Sem template válido = erro.

## Etapas

### STEP-01 — abort durável + integração na keep-alive do turno (`loop.py` sinal; turn.py)
- **Testes:** `test_abort_request_written_and_read`, `test_abort_consumed_when_honored`,
  `test_keepalive_detects_abort_and_kills_group` (turno em voo com filho sleep morto),
  `test_turn_abort_outcome_suspends_activity`, `test_abort_without_turn_is_noop`.
- **Gate:** `PYTHONPATH=src python3 -m unittest discover -s tests`

### STEP-02 — driver do loop (`loop.py` run_loop)
- **Testes:** `test_loop_runs_all_steps_to_complete` (fake-claude, 3 STEPs),
  `test_loop_recomputes_current_step_from_disk`, `test_loop_halts_on_gate_red`,
  `test_loop_halts_on_violation`, `test_loop_stops_on_stop_request`,
  `test_loop_respects_max_turns`, `test_loop_aborts_on_abort_request`,
  `test_loop_requires_active_build_and_canonical_paths`,
  `test_loop_resumes_from_current_step_after_halt`.
- **Gate:** `PYTHONPATH=src python3 -m unittest discover -s tests`

### STEP-03 — CLI `regent loop run|abort` + evidência do loop
- **Testes:** `test_loop_run_cli_json_contract`, `test_loop_abort_cli`,
  `test_loop_evidence_committed_operationally`, `test_loop_exit_codes`.
- **Gate:** `PYTHONPATH=src python3 -m unittest discover -s tests`

### STEP-04 — Consolidação 0.7.0
Skill de build do `/regent`: o loop como forma de executar um plano inteiro (anti-drift);
e2e real com fake-claude (plano de 2 STEPs até COMPLETE; abort a meio); versão 0.7.0.
- **Testes:** `test_cli_version_reports_070`, anti-drift atualizado.
- **Gate:** `bash scripts/gate-package.sh`

## Riscos

1. **Loop infinito / não-avanço:** parada dura por `max_turns` + a decisão do próximo STEP
   é do DISCO (STEP file commitado avança); um STEP que não produz STEP file (turno
   não-OK) PARA o loop — nunca repete o mesmo STEP silenciosamente.
2. **Corrida abort × fronteira do turno:** o abort é durável no XDG e checado na keep-alive
   (thread) E nas fronteiras; honrado no máximo uma vez (consumido), com evidência.
3. **Recuperação:** o loop é sem-estado (disco é a verdade); reexecutar continua; turno
   mid-agent nunca é retomado (recover_turn).
4. **Auto-retry indevido:** proibido por desenho (parada em não-OK); retry = ordem do dono.
5. **Token perdido no meio do loop:** cada turno fencia no commit; um takeover entre turnos
   é detectado no próximo `run_turn` (NOT_ACTIVE/CONFLICT), parando o loop.

## Idioma
Código/CLI/artefatos em inglês (REQ-002); este PLAN.md em PT (mediador PT-BR).
