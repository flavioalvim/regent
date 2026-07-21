---
outcome: SUCCESS
exit_code: 0
timestamp: 2026-07-21T03:08:12+00:00
linkage: PLAN-005/build
verdict: REPROVADO
---

## Resultado

Há quatro bloqueios contratuais reais:

1. **Abort pode atingir o turno seguinte.** O request não contém o nonce do turno; vincula apenas atividade/epoch/token ([abort.py](/home/flavio/projetos/regent/src/regent/conduction/abort.py:30)). O claim apenas verifica se existe *algum* `turn.nonce` ([abort.py](/home/flavio/projetos/regent/src/regent/conduction/abort.py:69)). Assim, um abort entre turnos permanece pendente e será honrado quando o próximo turno criar seu nonce. O teste “sem turno” chama o claim manualmente, situação que não existe quando nenhuma keepalive está rodando.

2. **A máquina recuperável de abort da emenda v3 não foi implementada.** Após `abort.request → abort.claimed`, não existem checkpoints `CLAIMED→KILLED→EVIDENCE→SUSPENDED→RELEASED→SUMMARY`. `recover_turn` inspeciona somente trailer, STEP e worktree ([turn.py](/home/flavio/projetos/regent/src/regent/conduction/turn.py:106)). Crash após claim/kill deixa atividade ACTIVE e `.claimed` sem mecanismo de conclusão. Além disso, cada novo claim sobrescreve o mesmo `abort.claimed`, destruindo estado anterior.

3. **O resumo do loop não usa fencing nem CAS.** O loop lock é liberado antes da evidência ([loop.py](/home/flavio/projetos/regent/src/regent/conduction/loop.py:166)). Depois, o código usa o índice Git compartilhado e `git commit` comum; o token carregado não é utilizado e a checagem de HEAD é TOCTOU, não CAS ([loop.py](/home/flavio/projetos/regent/src/regent/conduction/loop.py:182)). Isso permite:

   - commit após takeover/resume;
   - dois loops concorrendo durante o resumo;
   - inclusão acidental de arquivos previamente staged, especialmente em condições terminais anteriores a `run_turn`;
   - perda da garantia não-fencida para atividade SUSPENDED.

4. **O mapa exceção→condição está incompleto operacionalmente.** Apenas `TurnError` é capturado ([loop.py](/home/flavio/projetos/regent/src/regent/conduction/loop.py:133)). Casos obrigatórios escapam ou recebem código errado:

   - `EvidenceConflict` não vira `LOOP_CONFLICT`;
   - falha de spawn vira `IO`, não `HALTED/FAILURE`;
   - `CalledProcessError` de Git pode escapar sem JSON;
   - falha de release/suspensão não vira `LOOP_CONFLICT`;
   - `--max-turns -1` é aceito e vira `MAX_TURNS`, não `USAGE`.

Runner cancelável, distinção abort/timeout, drenagem concorrente e liberação do turn lock nos caminhos STOPPED/ABORTED estão presentes. Os itens de fase 4 não influenciaram o veredito.

Os arquivos registram 204 testes verdes 3×, gate-package 0.7.0 e e2e COMPLETE. Tentei reexecutar as três suítes, mas o sandbox desta revisão não oferece diretório temporário gravável; portanto esses gates não puderam ser confirmados independentemente. Isso não é a causa da reprovação: os bloqueios acima são demonstráveis diretamente no código e não estão cobertos pelos testes atuais.

REPROVADO