---
outcome: SUCCESS
exit_code: 0
timestamp: 2026-07-21T03:39:04+00:00
linkage: PLAN-005/build
verdict: REPROVADO
---

Há um bloqueio material e alcançável na fase 3: abort durante o gate é reivindicado, mas ignorado.

Sequência concreta:

1. A keepalive e o `turn.nonce` permanecem ativos durante o gate em [turn.py](/home/flavio/projetos/regent/src/regent/conduction/turn.py:242).
2. Um abort emitido nesse período é renomeado para `.claimed` e seta `cancel`.
3. Porém `run_gate` é chamado sem `cancel` em [turn.py](/home/flavio/projetos/regent/src/regent/conduction/turn.py:282), e o runner do gate também não o recebe em [gate.py](/home/flavio/projetos/regent/src/regent/conduction/gate.py:43).
4. Após o gate, `_boundary("GATED")` verifica apenas stop, não abort. O turno pode então produzir `TURN_OK`, commitar o STEP e continuar o loop.
5. Como o ramo `ABORTED` não é executado, o `.claimed` fica pendente e a atividade não é suspensa.

Isso viola diretamente o contrato de abort imediato durante o turno e o mapeamento “abort honrado → ABORTED/SUSPENDED”. O teste atual cobre apenas abort enquanto o agente está executando, não durante um gate demorado.

As duas correções do STEP-09 estão corretas: `.claimed` precede trailer/STEP, `suspension.owning_turn` é usado em `SUSPENDED`, e os clears de recovery estão filtrados. Os gates informados não detectam o caminho acima. Não é item de fase 4 nem a janela teórica fencing→`update-ref`.

REPROVADO