---
outcome: SUCCESS
exit_code: 0
timestamp: 2026-07-21T00:06:26Z
linkage: PLAN-002/build
verdict: APROVADO COM RESSALVAS
---

Os dois achados materiais estão fechados.

- `explain_control_diff`: descarte exige transição `obj→null` e `request_id` correspondente; evento desacoplado vira `unmatched`; versão exige igualdade exata com a contagem ([activity.py](/home/flavio/projetos/regent/src/regent/activity.py:454)).
- `init`: guarda ancestral cobre também symlinks de integração, journal usa escrita atômica com `O_EXCL|O_NOFOLLOW`, e falhas de limpeza não resultam mais em falsa mensagem de rollback completo ([initcmd.py](/home/flavio/projetos/regent/src/regent/initcmd.py:120)).
- Os três testes dirigidos cobrem descarte casado/inventado, delta inexato e `.claude/skills` escapando ([test_step06_fixes.py](/home/flavio/projetos/regent/tests/test_step06_fixes.py:161)).

Resta apenas um detalhe diagnóstico baixo: se `journal.unlink()` funcionar, mas `.regent.rmdir()` falhar, o `except` comum registra incorretamente o caminho do journal como não restaurado ([initcmd.py](/home/flavio/projetos/regent/src/regent/initcmd.py:180)). Ainda informa rollback incompleto, portanto não é bloqueante.

Foram descobertos 109 testes, mas o sandbox sem diretório temporário gravável impediu reexecutá-los integralmente. Os artefatos existentes 0.4.0 passaram `twine check --strict`, contêm as correções e `git diff --check` está limpo. Permanecem as ressalvas já aceitas.

APROVADO COM RESSALVAS