---
outcome: SUCCESS
exit_code: 0
timestamp: 2026-07-21T01:57:30+00:00
linkage: PLAN-004/build
verdict: null
---

Resultado: há falhas reais que invalidam os contratos centrais do PLAN v3.

1. **ALTA — atribuição dos efeitos do gate é fail-open.** Não existe o RE-BASELINE agente→gate. Qualquer mudança sem evento `post` dentro de `gate_envelope` é automaticamente aceita como efeito do gate, mesmo que tenha ocorrido antes dele ([turnlog.py:157](/home/flavio/projetos/regent/src/regent/conduction/turnlog.py:157)). Além disso, `gate_envelope` não precisa ser subconjunto do envelope principal ([turn.py:61](/home/flavio/projetos/regent/src/regent/conduction/turn.py:61)). Isso permite atribuição falsa e commit de arquivos fora do envelope do agente.

2. **ALTA — o diretório inteiro de artefatos escapa da prova global.** `artifact_dir` é acrescentado como raiz recursivamente isenta ([turn.py:131](/home/flavio/projetos/regent/src/regent/conduction/turn.py:131), [turnlog.py:143](/home/flavio/projetos/regent/src/regent/conduction/turnlog.py:143)). Assim, uma escrita escapada em `artifact_dir/payload` não produz violação, embora não tenha `post`. A isenção deveria cobrir somente artefatos específicos produzidos pelo supervisor.

3. **ALTA — todo `TURN_OK` deixa evidência do gate fora do commit.** `GATE-STEP-NN.md` é criado ([turn.py:120](/home/flavio/projetos/regent/src/regent/conduction/turn.py:120)), mas o commit inclui apenas arquivos atribuídos, STEP e TURN ([turn.py:162](/home/flavio/projetos/regent/src/regent/conduction/turn.py:162)). O arquivo não é ignorado e a próxima execução falha em `WORKTREE_DIRTY`. Adicionalmente, o checkout ainda usa `GIT_INDEX_FILE` privado, portanto não atualiza o índice normal após mover HEAD ([turn.py:215](/home/flavio/projetos/regent/src/regent/conduction/turn.py:215), [turn.py:228](/home/flavio/projetos/regent/src/regent/conduction/turn.py:228)).

4. **ALTA — as pré-condições REQ-005 não estão rigidamente implementadas.**

   - “STEP corrente” não é calculado; apenas se verifica que o nome aparece em qualquer lugar do texto e que um arquivo no `artifact_dir` escolhido não existe ([turn.py:43](/home/flavio/projetos/regent/src/regent/conduction/turn.py:43), [turn.py:77](/home/flavio/projetos/regent/src/regent/conduction/turn.py:77)).
   - `declared_in` não é vinculado ao `PLAN-NNN/PLAN.md` da atividade.
   - O gate não é extraído do STEP: qualquer substring existente no plano, como `:`, passa como comando declarado ([turn.py:79](/home/flavio/projetos/regent/src/regent/conduction/turn.py:79)).
   - O teste de `.regent/` usa prefixo textual; `.regent-evil/` passa ([turn.py:74](/home/flavio/projetos/regent/src/regent/conduction/turn.py:74)).

5. **ALTA — executor com falha pode ser commitado como sucesso.** Fora timeout, `result.exit_code` não participa da decisão. Um agente que escreva, gere eventos válidos e termine com código 1 recebe `TURN_OK` se o gate ficar verde ([turn.py:111](/home/flavio/projetos/regent/src/regent/conduction/turn.py:111), [turn.py:136](/home/flavio/projetos/regent/src/regent/conduction/turn.py:136)).

6. **ALTA — checkpoint, stop e recuperação v3 não foram implementados.** Apesar do docstring, o código apenas chama heartbeat; não persiste COMPOSED/LAUNCHED/GATED/VERIFIED, não executa `stop_check` e não contém recuperação trailer→STEP→worktree ([turn.py:89](/home/flavio/projetos/regent/src/regent/conduction/turn.py:89)). O keepalive termina antes do gate ([turn.py:106](/home/flavio/projetos/regent/src/regent/conduction/turn.py:106)); o gate pode durar 1800 s sem heartbeat. É exatamente o residual normativo que motivou o PLAN v3, não fase 3.

7. **ALTA — fencing e CAS não cobrem todos os commits.** O token é conferido antes de staging/`commit-tree`, não imediatamente antes do `update-ref`, deixando janela de takeover ([turn.py:210](/home/flavio/projetos/regent/src/regent/conduction/turn.py:210)). Commits operacionais usam índice normal, sem CAS de HEAD e sem fencing ([turn.py:237](/home/flavio/projetos/regent/src/regent/conduction/turn.py:237)). Também há TOCTOU entre verificação dos blobs e posterior `git add`.

8. **MÉDIA — prova Git não confere todos os atributos prometidos.** Deleção com qualquer `post` é aceita antes até de conferir envelope ou digest ([turnlog.py:145](/home/flavio/projetos/regent/src/regent/conduction/turnlog.py:145)); modo/tipo não são verificados; e `posts` é indexado somente por path, descartando correlação com `tool_use_id` e `pre` permitido ([turnlog.py:124](/home/flavio/projetos/regent/src/regent/conduction/turnlog.py:124)). Um `chmod` após o `post`, mantendo os bytes, passa.

9. **MÉDIA — hook standalone não é fail-closed para payload/tool desconhecido.** Apenas três ferramentas de execução são negadas; todo outro nome — inclusive PreToolUse malformado ou futura ferramenta de escrita/execução — retorna allow silencioso ([hookscript.py:109](/home/flavio/projetos/regent/src/regent/conduction/hookscript.py:109), [hookscript.py:137](/home/flavio/projetos/regent/src/regent/conduction/hookscript.py:137)).

Os 168 testes verdes 3×, gate-package 0.6.0 e o e2e registrado não contradizem esses contraexemplos. Em particular, [test_turn.py](/home/flavio/projetos/regent/tests/test_turn.py:98) tem somente sete testes e não exercita STEP corrente, gate por STEP, índice pós-commit, CAS/fencing, saída não zero, checkpoint, recuperação ou re-baseline do gate. O STEP produzido também omite gate outcome, turno/linkage e demais campos normativos ([turn.py:198](/home/flavio/projetos/regent/src/regent/conduction/turn.py:198)).

REPROVADO