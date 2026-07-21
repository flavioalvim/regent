---
outcome: SUCCESS
exit_code: 0
timestamp: 2026-07-21T10:09:18+00:00
linkage: PLAN-006
verdict: REPROVADO
---

Foram encontrados bloqueios reais de segurança e recuperação.

1. **BLOQUEADOR — `disarm()` não implementa CAS atômico.** Em [supervisor.py:140](/home/flavio/projetos/regent/src/regent/conduction/supervisor.py:140), comparação e `unlink()` são operações separadas. A pode ler arm A; o dono desarma/rearma B; então A executa `unlink()` e apaga B. `read_arm()` possui a mesma corrida ao descartar token obsoleto em [supervisor.py:128](/home/flavio/projetos/regent/src/regent/conduction/supervisor.py:128). Além disso, o `unlink` não faz `fsync` do diretório, podendo ressuscitar o token após falha de energia. O teste é apenas sequencial — e está duplicado/sobrescrito em [test_supervisor.py:111](/home/flavio/projetos/regent/tests/test_supervisor.py:111) e [test_supervisor.py:133](/home/flavio/projetos/regent/tests/test_supervisor.py:133).

2. **BLOQUEADOR — daemon pode iniciar turno após `CONCLUSION.md`.** `read_arm()` valida somente plan/epoch/token; o guard em [supervisor.py:202](/home/flavio/projetos/regent/src/regent/conduction/supervisor.py:202) apenas repete isso. `run_loop()` revalida atividade e aprovação, mas nunca a ausência de `CONCLUSION.md`. Logo, se a conclusão for criada após o arm — inclusive num crash entre gravar a conclusão e `activity conclude` — o daemon ainda pode lançar o próximo turno. Viola diretamente o cerne normativo.

3. **BLOQUEADOR — existe TOCTOU entre guard e lançamento.** Em [loop.py:127](/home/flavio/projetos/regent/src/regent/conduction/loop.py:127), o guard retorna; depois são preparados step/prompt e somente em [loop.py:140](/home/flavio/projetos/regent/src/regent/conduction/loop.py:140) começa `run_turn`. Um desarme concluído nessa janela não é observado, pois `run_turn` cerca pelo token da atividade, não pelo arm-token. Portanto um turno pode começar depois de `disarm` retornar.

4. **ALTO — `arm()` não valida a configuração normativa.** Em [supervisor.py:81](/home/flavio/projetos/regent/src/regent/conduction/supervisor.py:81), a configuração é persistida opacamente: não há paths canônicos, plano declarado canônico, gates por step nem existência do template. Exemplo concreto: template inexistente arma com sucesso; [loop.py:96](/home/flavio/projetos/regent/src/regent/conduction/loop.py:96) levanta `OSError`; `run_daemon()` só captura `LoopError`, portanto sai deixando o token armado. Um `declared_in` não canônico e vazio ainda pode produzir `STEPS_COMPLETE` sem alcançar as validações de `run_turn`.

5. **MÉDIO — exit codes e streaming divergem do contrato.** `_DAEMON_EXIT` trata `SIGNALLED` como sucesso e `LOOP_MISCONFIGURED` como stop/precondição em [activity_cli.py:41](/home/flavio/projetos/regent/src/regent/activity_cli.py:41), embora sinal seja parada do dono e misconfiguração seja falha. A CLI também emite somente um JSON final contendo `transitions`, não uma linha JSON por transição. O teste cobre apenas `STOPPED`.

O cerne mediado está correto: `COMPLETE` vira `STEPS_COMPLETE`, desarma e não cria `CONCLUSION.md` nem chama `conclude`. A gravação positiva do token também usa tmp, `O_EXCL`, `fsync`, rename e `fsync` do diretório.

Não consegui repetir os testes neste ambiente: o sandbox read-only não disponibiliza diretório temporário gravável; os 27 testes dirigidos falharam no `setUp`, não na implementação. Considerei os gates verdes informados como evidência prévia.

REPROVADO