---
outcome: SUCCESS
exit_code: 0
timestamp: 2026-07-20T23:35:33Z
linkage: PLAN-002/build
verdict: REPROVADO (2 BLOQUEANTES, 3 ALTAS, 3 MEDIAS)
---

Há dois bloqueantes de correção; os gates verdes não exercitam essas janelas.

1. **BLOQUEANTE — `start`/`resume` não são operações compostas serializadas.**  
   `_recover()` libera qualquer lock quando o control está idle/SUSPENDED ([activity.py](/home/flavio/projetos/regent/src/regent/activity.py:278)), mas o mutex de lifecycle é mantido apenas durante cada primitiva. Interleaving possível:

   - A adquire token A antes do CAS.
   - B observa idle + held(A) e libera A como “row 8”.
   - A publica `ACTIVE(A)`.
   - B adquire B, perde o `start`, libera B.
   - Estado final: `ACTIVE(A)` com lock `free`.

   Em `resume`, o callback ainda sobrescreve incondicionalmente qualquer transição concorrente ([activity.py](/home/flavio/projetos/regent/src/regent/activity.py:132)). O teste concorrente aceita qualquer `Exception` como recusa e não verifica `control_token == lock_token` ao final ([test_activity.py](/home/flavio/projetos/regent/tests/test_activity.py:37), [test_activity.py](/home/flavio/projetos/regent/tests/test_activity.py:216)). É necessário serializar `recover→acquire→CAS→turn.json` como uma unidade ou introduzir estado transitório durável.

2. **BLOQUEANTE — a atribuibilidade default-deny não foi implementada de fato.**  
   `explain_control_diff()` considera explicada qualquer alteração de `stop_request`, inclusive remoção/substituição arbitrária, ignora `schema_version` e não recebe nem valida o diff de `audit.jsonl` ([activity.py](/home/flavio/projetos/regent/src/regent/activity.py:361)). Executei o helper puro: alteração de schema mais `stop_request` forjado resultou em `unexplained: []`. Além disso, ele só é usado nos testes; nenhum fluxo de produção ou comando o chama. A skill também não prescreve os snapshots de `control.version` inicial/final exigidos pelo PLAN ([SKILL.md](/home/flavio/projetos/regent/src/regent/templates/skills/regent/SKILL.md:68)). O teste cobre apenas stop legítimo versus troca da atividade ([test_choreography.py](/home/flavio/projetos/regent/tests/test_choreography.py:48)).

3. **ALTA — falhas de release e limpeza são convertidas em sucesso.**  
   `suspend` e `conclude` usam `_release_quietly`; `NotLockOwner`, `StaleLock` e `OSError` são engolidos ([activity.py](/home/flavio/projetos/regent/src/regent/activity.py:323)). `_clear_local_token()` também ignora todo `OSError` ([activity.py](/home/flavio/projetos/regent/src/regent/activity.py:346)). Assim, o CLI pode retornar exit 0 embora o lock continue held ou `turn.json` não tenha sido removido. A alegação no comentário de que a próxima recuperação “surfacing” o erro é falsa: ela usa novamente os mesmos helpers silenciosos.

4. **ALTA — upgrade não é atômico e pode seguir symlink para fora do host.**  
   Skills conhecidas são sobrescritas diretamente com `write_text`, sem tempfile+replace ou journal ([initcmd.py](/home/flavio/projetos/regent/src/regent/initcmd.py:127)). Crash durante ou entre escritas deixa estado parcial. O rollback é best-effort e silencia falhas ([initcmd.py](/home/flavio/projetos/regent/src/regent/initcmd.py:174)). Além disso, `_existing_state()` aceita symlink no lugar de arquivo porque `is_file()` o segue; se o alvo tiver hash legado conhecido, o upgrade sobrescreve o alvo externo ([initcmd.py](/home/flavio/projetos/regent/src/regent/initcmd.py:84)). O teste cobre somente uma exceção capturada posterior, não crash, symlink ou falha do próprio rollback.

5. **ALTA — `takeover` aceita atividade idle ou SUSPENDED.**  
   A camada carrega a atividade, mas não valida seu estado antes de chamar `TurnLock.takeover()` ([activity.py](/home/flavio/projetos/regent/src/regent/activity.py:201)). Com control idle + lock free, o comando retorna sucesso, cria lock e `turn.json`, mas não cria atividade. Isso fabrica imediatamente uma linha 8 e contradiz o propósito mediado de recuperar somente `ACTIVE+free/suspect`.

6. **MÉDIA — contrato JSON fechado foi ampliado/quebrado fora do catálogo.**  
   Existe o código não normativo `ACTIVITY` ([activity_cli.py](/home/flavio/projetos/regent/src/regent/activity_cli.py:22)), usado para tipo inválido e ID divergente no resume. `CONFLICT` acrescenta `reason`; o fallback de `TOKEN_MISMATCH` devolve `control_token: null` e campo `reason`; `IO.path` pode ser null ([activity_cli.py](/home/flavio/projetos/regent/src/regent/activity_cli.py:119)). Isso viola os detalhes exatos do PLAN. A extensão `workspace` está ao menos declarada no STEP-04; estas outras não.

7. **MÉDIA — as skills pedem dados que o CLI não fornece.**  
   `regent-stop` exige reportar o checkpoint de uma atividade já suspensa ([regent-stop/SKILL.md](/home/flavio/projetos/regent/src/regent/templates/skills/regent-stop/SKILL.md:16)), mas `status` reduz a atividade a `{type,id,epoch,state}` ([activity.py](/home/flavio/projetos/regent/src/regent/activity.py:428)). Similarmente, `/regent` manda usar o motivo “from request”, mas `stop request` não aceita nem persiste motivo. Um stop vindo de outra sessão perde essa informação.

8. **MÉDIA — legado PT não implementa a corrupção “dois esquemas presentes”.**  
   O scanner considera somente diretórios ainda abertos ([activity.py](/home/flavio/projetos/regent/src/regent/activity.py:254)). Portanto, `rounds/` e `rodadas/` simultaneamente não são necessariamente classificados como corrupção, contrariando REQ-005 §8. O teste legado cobre apenas um diretório PT aberto ([test_skills_v1.py](/home/flavio/projetos/regent/tests/test_skills_v1.py:145)).

Confirmei como corretos por inspeção: versão 0.4.0, hashes atuais presentes no manifesto, lock de mutação da aplicação no XDG, incremento de epoch no resume e presença das branches nominais da tabela. O sandbox desta consulta é estritamente somente leitura e não disponibilizou diretório temporário, portanto tratei as execuções 3×/gate-package/e2e como evidência registrada, sem rerodá-las.

REPROVADO