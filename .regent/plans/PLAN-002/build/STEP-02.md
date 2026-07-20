# PLAN-002 / STEP-02 — Subcomandos CLI (status/activity/stop) com contrato JSON

step_base_sha: d0e0910 (commit do STEP-01)
files_touched:
  - src/regent/activity_cli.py (novo)
  - src/regent/cli.py (parser JSON-puro + wiring dos novos subcomandos)
  - tests/test_activity_cli.py (novo, 9 testes dirigidos)

## O que foi implementado

- `regent status` / `regent activity start|resume|suspend|conclude|heartbeat|takeover` /
  `regent stop request|check` sobre a camada de aplicação (handlers NUNCA compõem
  primitivas — objeção 2 do plano respeitada).
- Contrato JSON do plano: stdout SEMPRE JSON puro (inclusive erro de argparse, via parser
  que levanta em vez de imprimir — exit 64); envelope `{"error": CODE, "detail": ...}`
  com o catálogo e exit codes normativos (0/2/3/4/5/64); schemas de sucesso conforme o
  plano; descoberta de root cwd↑ até `.regent/` ou `--project`; capabilities no status.
- Mapeamento exceção→código: domínio (ActivityError.code) + protocolo
  (ControlSchemaError→UNINITIALIZED|CORRUPT_CONTROL, VersionConflict→CONFLICT,
  NotLockOwner→TOKEN_MISMATCH, LockHeld/StaleLock→LOCK_*, MutationMutexBusy→BUSY,
  OSError→IO).

## Vermelho→verde (registro fiel)

1ª execução: 9/9 erros — bug REAL de contrato: `out=sys.stdout` como default era
resolvido no IMPORT, ignorando redirecionamento do chamador (a saída vazava para o
stdout original). Corrigido na fonte (`out=None` → resolve `sys.stdout` na chamada);
re-run 9/9 verdes.

## Gate (PYTHONPATH=src python3 -m unittest discover -s tests)

```
Ran 67 tests — OK (3 execuções)
```
