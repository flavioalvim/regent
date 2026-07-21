---
outcome: SUCCESS
exit_code: 0
timestamp: 2026-07-21T10:20:10+00:00
linkage: PLAN-006
verdict: REPROVADO
---

Resultado: 3 correções fechadas, 2 apenas parcialmente. Há falhas reais de segurança/recuperação; portanto, reprovo.

1. **BLOQUEADOR — remoção não é comprovadamente durável e pode reportar sucesso sem remover.** `_unlink_durable()` engloba tanto `unlink()` quanto `fsync()` em um `except OSError: pass` ([supervisor.py](/home/flavio/projetos/regent/src/regent/conduction/supervisor.py:77)). Assim:

   - falha de `unlink()` deixa o token armado, mas `disarm()` retorna `{"disarmed": true}` ([supervisor.py](/home/flavio/projetos/regent/src/regent/conduction/supervisor.py:224));
   - falha do `fsync` é ocultada, logo não se pode afirmar ausência de ressurreição após crash;
   - `run_daemon()` ignora o resultado de `disarm()`, inclusive no caminho `FAILED` ([supervisor.py](/home/flavio/projetos/regent/src/regent/conduction/supervisor.py:300)).

   O flock e o CAS por `arm_id` estão corretos e não encontrei reentrância/deadlock: `arm`, descarte e `disarm` usam o mesmo lock, sem `read_arm()` dentro de seção já armada. Porém o achado #1 não está totalmente fechado, e a promessa do #4 de “falha inesperada nunca deixa armado” também não é garantida.

2. **ALTO — o guard tardio não revalida `APPROVED`.** `run_loop()` verifica aprovação bem antes de calcular commits, preparar e escrever o prompt ([loop.py](/home/flavio/projetos/regent/src/regent/conduction/loop.py:114)). O guard imediatamente anterior ao lançamento verifica sinal, conclusão e binding do arm, mas não a aprovação ([supervisor.py](/home/flavio/projetos/regent/src/regent/conduction/supervisor.py:278)). Se `APPROVAL.md` for revogado após a primeira verificação, o turno ainda inicia, contrariando o contrato do plano de revalidar `APPROVED` no guard.

3. **ALTO — a configuração validada não é canonizada/persistida canonicamente.** `prompt_template`, `declared_in` e `artifact_dir` são resolvidos relativamente ao CWD durante a validação, mas o objeto original é gravado no token ([supervisor.py](/home/flavio/projetos/regent/src/regent/conduction/supervisor.py:107), [supervisor.py](/home/flavio/projetos/regent/src/regent/conduction/supervisor.py:174)). Depois:

   - template e `declared_in` são novamente interpretados relativamente ao CWD do daemon;
   - `artifact_dir` relativo é interpretado relativamente à raiz do projeto ([loop.py](/home/flavio/projetos/regent/src/regent/conduction/loop.py:92)).

   Portanto, uma configuração pode passar no `arm` e falhar ou apontar para outro lugar quando o daemon for iniciado de outro diretório. Isso não cumpre “paths canônicos” e deixa o #4 parcialmente aberto.

4. **ALTO — regressão introduzida pelo streaming:** exceção no callback de transição pode deixar o token armado. `emit("RUNNING")` chama `on_state` antes do `try` que protege `run_loop` ([supervisor.py](/home/flavio/projetos/regent/src/regent/conduction/supervisor.py:250), [supervisor.py](/home/flavio/projetos/regent/src/regent/conduction/supervisor.py:273)). Na CLI, esse callback escreve em stdout ([activity_cli.py](/home/flavio/projetos/regent/src/regent/activity_cli.py:343)); um `BrokenPipeError`/erro de saída escapa sem desarmar.

Confirmações positivas:

- #2: `CONCLUSION.md` faz o guard retornar `False`; nenhum turno começa.
- #3: o guard está imediatamente antes de `run_turn`, e falha produz `DISARMED`.
- #4: template/arquivo do plano/STEPs com gate/artifact/envelope possuem validação inicial, e exceções de `run_loop` são convertidas em `FAILED`.
- #5: `SIGNALLED→2`, `LOOP_MISCONFIGURED→3` e `FAILED→3`; há uma linha JSON por transição e objeto final.
- `ALREADY_ARMED` para outro plano é verificado antes da validação, sob o lock.
- O teste `test_read_arm_discard_keeps_rearmed_token` não simula a corrida alegada: ele invalida o token novo e confirma sua remoção. Logo, não prova o interleaving A→B, embora a implementação do CAS esteja correta por inspeção.
- Tentei os 34 testes direcionados; todos pararam no `setUp` porque o sandbox não oferece diretório temporário gravável. Não contradiz os gates verdes informados.

REPROVADO