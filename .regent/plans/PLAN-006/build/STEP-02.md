# PLAN-006 / STEP-02 — Daemon supervisor (`run_daemon`)

**Base:** b8b145b8911f2c4cd4d97eb96263e3ec852af426 (STEP-01)
**Escopo entregue:** `run_daemon` em `src/regent/conduction/supervisor.py`.

## O que foi implementado
`run_daemon(service, poll=5, claude_bin, once=False, runner=None, on_state=None)`
— supervisor em PRIMEIRO PLANO:
- **Nunca age sem arm-token VÁLIDO** (`read_arm` valida arm_id+plan+epoch+token
  contra a atividade CORRENTE). Sem arm → `IDLE` (aguarda; ou sai com `--once`).
- Armado + sem stop-request: dirige o build via `run_loop` passando um `guard`
  que REVALIDA o arm ANTES de cada turno; guard falho (desarme/takeover/sinal) →
  o loop retorna `DISARMED` (o guard só barra INICIAR o próximo turno; o turno em
  voo termina pela via normal/abort).
- Mapeamento terminal:
  - loop `COMPLETE` → **DESARMA** e reporta `STEPS_COMPLETE` (NÃO faz revisão
    final, NÃO cria CONCLUSION.md, NÃO conclui a atividade — decisão MEDIADA).
  - `STOPPED`/`ABORTED`/`DISARMED`/`HALTED`/`MAX_TURNS`/`LOOP_*`/
    `PLAN_NOT_EXECUTABLE` → **DESARMA** e reporta. Nunca re-tenta sozinho.
- stop-request entre ciclos → honra, desarma, `STOPPED` (antes de qualquer turno).
- SIGINT/SIGTERM → desarma e sai `SIGNALLED` (handlers restaurados no finally).
- Toda condição terminal DESARMA (impede "ressuscitar" trabalho concluído/falho).

## Testes (verdes)
`test_daemon_idle_without_arm`, `test_daemon_once_single_cycle`,
`test_daemon_never_acts_on_unarmed_plan`, `test_daemon_drives_armed_plan_to_complete`,
`test_daemon_reports_steps_complete_not_accepted`, `test_daemon_disarms_after_complete`,
`test_daemon_disarms_on_halted`, `test_daemon_disarms_on_stopped`,
`test_daemon_respects_stop_request`, `test_daemon_guard_disarm_stops_between_turns`,
`test_daemon_stops_on_disarm_between_cycles`,
`test_arm_token_stale_after_takeover_ignored`, `test_disarm_cas_old_id_does_not_remove_rearm`.

## Gate
`PYTHONPATH=src python3 -m unittest discover -s tests` → 234 OK.
