---
outcome: SUCCESS
exit_code: 0
timestamp: 2026-07-21T02:27:19+00:00
linkage: PLAN-004/build
verdict: REPROVADO
---

Há bloqueio real remanescente no residual 1:

1. **ALTA — ainda não há `stop_check` em toda fronteira.** O último check ocorre antes da verificação ([turn.py:234](/home/flavio/projetos/regent/src/regent/conduction/turn.py:234)). Um stop solicitado durante `verify_chain`, atribuição ou escrita da evidência segue para `COMMITTING` e commit sem nova consulta ([turn.py:243](/home/flavio/projetos/regent/src/regent/conduction/turn.py:243), [turn.py:257](/home/flavio/projetos/regent/src/regent/conduction/turn.py:257), [turn.py:269](/home/flavio/projetos/regent/src/regent/conduction/turn.py:269)). O pedido não invalida o token, portanto o fencing não impede o commit.

2. **ALTA — `STOPPED` não garante suspensão.** `_stopped_suspend` engole qualquer exceção de `suspend_activity` e o chamador lança `STOPPED` mesmo assim ([turn.py:91](/home/flavio/projetos/regent/src/regent/conduction/turn.py:91)). Em corrida com takeover/conclusão, ou falha de controle/I/O, a atividade pode permanecer `ACTIVE`. Isso contradiz inclusive o comentário de que token perdido “surfaces as its own error”.

3. **MÉDIA — ordem do checkpoint pós-gate está invertida.** `VERIFIED` é persistido antes do stop pós-gate ([turn.py:233](/home/flavio/projetos/regent/src/regent/conduction/turn.py:233)); um crash nessa janela deixa checkpoint `VERIFIED` sem verificação realizada. O contrato dizia stop pós-GATE antes de VERIFIED.

Os residuais 2–4 fecharam diretamente no código: conflito de gate não é isento nem commitado; deleção/symlink são rejeitados sem dereferência; e o build exige igualdade canônica mais contenção sob o root real. Como ressalva de teste, o caso de gate forjado deveria exigir exatamente `TURN_VIOLATION`, não aceitar também `GATE_RED`.

A tentativa local dirigida não executou porque este ambiente de revisão não oferece diretório temporário gravável; isso não contradiz os gates 181×3, package e e2e informados.

REPROVADO