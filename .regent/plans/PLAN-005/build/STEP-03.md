# PLAN-005 / STEP-03 — CLI regent loop run|abort

step_base_sha: 3930693 (commit do STEP-02)
files_touched: src/regent/activity_cli.py (subcomandos loop run|abort + 10 códigos novos),
  tests/test_loop_cli.py (novo, 2)

- `regent loop run` sobre run_loop: contrato JSON, mapa condição→exit (COMPLETE=0;
  HALTED/ABORTED/MAX_TURNS/CONFLICT/DIRTY=3; STOPPED/PLAN_NOT_EXECUTABLE/MISCONFIGURED=2).
- `regent loop abort --reason`: grava o abort-request vinculado à atividade corrente;
  segundo abort pendente = ABORT_PENDING.

## Gate: Ran 204 tests — OK (com STEP-04)
