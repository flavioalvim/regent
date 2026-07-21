# PLAN-006 — respostas ao ADVISOR-REVIEW-5 (REPROVADO)

2 bloqueadores + 1 alto. #1 e #3 são defeitos claros (corrigidos). #2 pede
linearização total guard→lançamento — mitigada ao limite prático; o resíduo é a
fronteira DECLARADA no PLAN (turno em voo = via de abort), que exige a divisão
spawn/wait do runner, escopo da FASE 5.

## #1 (BLOQUEADOR) — IDLE/ok=true contornava a barreira de durabilidade
- Novo `_confirm_absent_durable(service)`: sob o lock, se um token está presente
  (rearm concorrente) → "present" (re-avalia, nunca apaga); se ausente → roda o
  `fsync` do diretório (barreira) → "durable", ou "failed" (re-tenta transitório).
- O ramo IDLE (`armed is None`) agora passa por ele: "present" → re-loop;
  "failed" → `DISARM_FAILED`; "durable" → IDLE. Nenhum IDLE limpo é reportado
  sobre uma remoção não-durável, SEM clobber de rearm.
- Testes: `test_daemon_idle_disarm_failed_when_absence_not_durable`.

## #3 (ALTO) — read_arm não validava o esquema (KeyError fora do handler)
- `_raw_arm` retorna None para JSON não-dicionário. `_well_formed` exige
  {arm_id, plan_id, activity_epoch, turn_token, config(dict)}. `read_arm` só
  considera BOUND um token bem-formado; malformado → descartado, nunca retornado.
  Fecha o `armed["config"]` KeyError que matava o daemon sem terminal controlado.
- Testes: `test_read_arm_rejects_malformed_token`, `test_daemon_idle_on_malformed_token`.

## #2 (BLOQUEADOR) — TOCTOU guard→lançamento: MITIGADO + fronteira declarada
- `run_turn` ganhou `launch_precondition` — verificado IMEDIATAMENTE antes do
  spawn do agente, sem I/O entre a checagem e o `Popen`. O loop passa o `guard`
  do arm como precondition; falha → suspende (libera o turn lock) e levanta
  `TurnError("DISARMED")` → o loop mapeia para a condição DISARMED → o daemon
  desarma e reporta. É o ponto mais tardio em que se pode recusar INICIAR.
- **Resíduo declarado:** a linearização TOTAL (segurar um lock across
  checagem+spawn) exige separar o `spawn` do `wait` no runner — senão o lock
  ficaria retido por todo o turno, bloqueando o próprio desarme. Isso é a
  arquitetura do daemon em BACKGROUND, declarada FORA DE ESCOPO no PLAN-006
  (FASE 5). O PLAN já estabelece: "o turno em voo termina ou é abortado pela via
  de abort; o guard só barra INICIAR o próximo" — e o revisor ACEITOU essa
  fronteira nas rodadas 2, 3 e 4. A janela remanescente é de microssegundos sem
  I/O interposto. **Decisão de aceitar o resíduo como ressalva de FASE 5 é do
  DONO (mediada).**
- Teste: `test_launch_precondition_false_suspends_without_launching` (precondition
  False → suspende, NUNCA lança o agente).

## Gates
Suíte completa 259 OK; `bash scripts/gate-package.sh` → 0.8.0 + twine --strict OK.
