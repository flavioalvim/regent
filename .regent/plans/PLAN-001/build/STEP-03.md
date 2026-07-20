# PLAN-001 / STEP-03 — Stop-request: representação e transições

files_touched:
  - src/regent/protocol/stop.py (novo)
  - src/regent/protocol/control.py (property `audit` exposta — colaboração limpa)
  - tests/test_stop.py (novo, 6 testes dirigidos)

## O que foi implementado (escopo REDUZIDO conforme plano v3)

- `record_stop_request`: vincula a request à atividade corrente (`activity_id` +
  `activity_epoch` + `turn_token`); idempotente (request equivalente pendente é retornada,
  não duplicada); erro se não há atividade.
- `read_valid_stop_request`: regra normativa de obsolescência — stale sse id/epoch divergem
  OU `turn_token≠null` e diverge do token corrente (fencing pós-takeover); canal do
  mediador (`turn_token=null`) sobrevive a takeover. Stale = descarte via CAS + registro
  `stop_request_discarded` no audit.
- `suspend_activity`: ACTIVE→SUSPENDED exigindo o token do turno corrente e o payload
  completo do REQ-004 §5 (previous_state/checkpoint/owning_turn/in_flight/reason/at);
  consome a stop_request pendente; idempotente (re-aplicar no mesmo checkpoint = no-op
  False; checkpoint diferente = erro).
- Fora do escopo, como declarado: sequência canônica completa, `--abort`, `CANCELLED`
  (fase de condução).

## Gate (PYTHONPATH=src python3 -m unittest discover -s tests)

```
Ran 32 tests in 0.935s
OK
```
