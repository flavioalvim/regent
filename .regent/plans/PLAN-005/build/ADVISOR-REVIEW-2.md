---
outcome: SUCCESS
exit_code: 0
timestamp: 2026-07-21T03:15:48+00:00
linkage: PLAN-005/build
verdict: REPROVADO
---

## Achados bloqueantes

1. **Recuperação de abort ainda perde estado.** Em [turn.py](/home/flavio/projetos/regent/src/regent/conduction/turn.py:123), `recover_turn`:

   - não valida se o `.claimed` pertence à atividade/epoch/token atuais;
   - engole qualquer falha de suspensão;
   - apaga todos os `.claimed` mesmo assim;
   - retorna `ABORT_RECONCILED` ainda que a atividade permaneça ACTIVE ou o lock não tenha sido liberado.

   Além disso, o caminho normal limpa `.claimed` em [turn.py](/home/flavio/projetos/regent/src/regent/conduction/turn.py:300) antes da criação do resumo pelo loop. Um crash nesse intervalo deixa a atividade SUSPENDED, sem marcador recuperável e sem mecanismo para completar `SUMMARY`. A máquina durável `CLAIMED→…→SUMMARY` descrita no plano não foi implementada.

2. **Fencing do resumo ainda permite commit após takeover.** Em [loop.py](/home/flavio/projetos/regent/src/regent/conduction/loop.py:229), o token é verificado antes de `commit-tree`; o `update-ref` ocorre somente depois, em [loop.py](/home/flavio/projetos/regent/src/regent/conduction/loop.py:240). Um takeover nesse intervalo não move necessariamente HEAD, portanto o CAS pode aceitar um commit produzido sob token já revogado. Ademais, token divergente ou HEAD movido são silenciosamente ignorados, permitindo que o loop reporte `COMPLETE` sem o resumo obrigatório.

3. **Mapa exceção→condição permanece incompleto.** Em [loop.py](/home/flavio/projetos/regent/src/regent/conduction/loop.py:152), todo `OSError` de `run_turn`, inclusive falha de spawn, vira `LOOP_CONFLICT`, contrariando o contrato `spawn→HALTED/FAILURE`. Erros Git anteriores ao `try` (`_committed_steps`) e erros Git/op-commit em `_write_loop_evidence` escapam sem conversão para `LOOP_CONFLICT` e, pela CLI, sem JSON contratual. `--max-turns < 1 → USAGE` foi corrigido corretamente.

O bloqueio 1 original — abort atingir o turno seguinte — foi fechado: request e claim exigem o mesmo nonce não nulo em [abort.py](/home/flavio/projetos/regent/src/regent/conduction/abort.py:30) e [abort.py](/home/flavio/projetos/regent/src/regent/conduction/abort.py:80). Índice privado, CAS e permanência dentro do loop lock também existem, mas não compensam a janela de fencing acima.

Os artefatos registram 206 testes verdes 3×, package gate 0.7.0 e e2e de dois STEPs até COMPLETE. A reexecução independente contou 206 testes, mas o sandbox sem diretório temporário gravável impediu 199 de iniciarem; isso não fundamenta a reprovação. Itens de fase 4 foram desconsiderados.

REPROVADO