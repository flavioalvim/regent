# PLAN-006 / STEP-03 — CLI `regent rehearse|arm|disarm|daemon`

**Base:** cda30f3bbcd5f29dcf2776ef4aa3d2d93485feab (STEP-02)
**Escopo entregue:** parsers + dispatch em `src/regent/activity_cli.py`.

## O que foi implementado
- `regent rehearse --plan --declared-in` — imprime o JSON do ensaio; sempre exit 0
  (read-only).
- `regent arm --plan --prompt-template --envelope [--envelope ...] [--gate-envelope
  ...] --declared-in --artifact-dir [--max-turns 20] [--timeout 900]` — monta o
  `config` do loop e grava o arm-token; `{ok, arm_id, ...}` exit 0.
  `SupervisorError` (`NOT_EXECUTABLE`/`ALREADY_ARMED`/`ALREADY_CONCLUDED`) → `_fail`
  com exit 2.
- `regent disarm [--arm-id ID]` — CAS por arm_id; `{disarmed, ...}` exit 0.
- `regent daemon run [--poll 5] [--claude-bin B] [--once]` — roda o supervisor em
  primeiro plano; exit por `_DAEMON_EXIT` (STEPS_COMPLETE/IDLE/SIGNALLED→0;
  STOPPED/DISARMED/PLAN_NOT_EXECUTABLE→2; HALTED/ABORTED/MAX_TURNS/LOOP_*→3).
- `_EXIT_BY_CODE` estendido com os códigos do supervisor.

## Testes (verdes)
`test_rehearse_cli_json`, `test_arm_disarm_cli`,
`test_arm_other_plan_already_armed_exit_code`, `test_daemon_run_cli_once`,
`test_daemon_exit_codes` (armado + stop-request → STOPPED exit 2, sem lançar agente).

## Gate
`PYTHONPATH=src python3 -m unittest discover -s tests` → 239 OK.
