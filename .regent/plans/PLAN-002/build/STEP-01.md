# PLAN-002 / STEP-01 — Errata do lock file + camada de aplicação

step_base_sha: 736999a (commit do baseline)
files_touched:
  - src/regent/protocol/control.py (param `lock_file` — errata PLAN-001: produto põe o
    mutex de mutação no XDG; + schema: `suspension.evidence` lista de paths)
  - src/regent/protocol/stop.py (`suspend_activity(..., evidence=)`)
  - src/regent/activity.py (novo — application layer)
  - tests/test_activity.py (novo, 18 testes dirigidos)

## O que foi implementado

- `ActivityService`: operações compostas start/resume/suspend/conclude/heartbeat/
  takeover/stop_request/stop_check/status com as ORDENS CANÔNICAS do plano; toda entrada
  roda `_recover()` pela tabela normativa de 12 linhas (2/12: reescreve turn.json; 3/4:
  exige takeover mediado com mensagem exata; 5: TOKEN_MISMATCH; 6/8: release do lock
  órfão; 10/11: limpeza do token local). Corrida de `start` deduplicada pós-CAS (perdedor
  desfaz o próprio lock e recebe ACTIVITY_OPEN).
- Token: autoritativo no control; `turn.json` (XDG) é cópia de conveniência reparável.
- Epochs: start/resume = piso+1 (resume incrementa, PLAN-001); conclude grava
  `last_concluded.epoch` preservando o piso.
- `suspension.evidence[]` no schema (emenda aprovada no plano); `resume` reporta
  evidências ausentes.
- Exceções de domínio com `code` estável (catálogo do plano) para o CLI do STEP-02.
- Test hooks `_CRASH_POINTS` (os._exit em fronteiras nomeadas) p/ fault injection real
  em subprocesso.

## Gate (PYTHONPATH=src python3 -m unittest discover -s tests)

```
Ran 58 tests — OK (3 execuções)
```
18 novos: ciclo completo com epochs, linhas 2/3/4/5/6/8/10/11/12 da tabela, crash em
start:after_lock/after_cas, suspend:after_cas/before_token_cleanup, resume:after_lock,
conclude:after_cas, start concorrente duplo (um vence), takeover rotaciona control+local,
evidence paths, heartbeat, nenhum *.lock sob .regent/.

## Vermelho→verde (registro fiel)

1ª execução: 1 falha — asserção errada MINHA no teste (epoch inicial é 0 = piso(-1)+1,
não 1); corrigida a asserção, não o código.
