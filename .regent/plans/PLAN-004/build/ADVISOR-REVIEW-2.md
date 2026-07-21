---
outcome: SUCCESS
exit_code: 0
timestamp: 2026-07-21T02:08:39+00:00
linkage: PLAN-004/build
verdict: REPROVADO
---

A segunda revisão ainda encontra violações reais dos contratos centrais.

1. **ALTA — checkpoint/stop/recuperação continuam não implementados conforme o PLAN.** `_set_phase` apenas sobrescreve `state_dir/turn.phase`, sem publicação atômica/fsync e fora do `control` ([turn.py:73](/home/flavio/projetos/regent/src/regent/conduction/turn.py:73)). O único `stop_check` ocorre antes do launch ([turn.py:137](/home/flavio/projetos/regent/src/regent/conduction/turn.py:137)); pedidos durante launch ou gate chegam até o commit. Além disso, `STOPPED` apenas lança exceção, sem suspensão canônica, e não existe recuperação `trailer → STEP → worktree`. O keepalive agora cobre launch e gate, mas isso fecha somente uma parte do achado 6.

2. **ALTA — o commit operacional ainda não tem fencing+CAS adequado.** O token é conferido apenas antes do staging ([turn.py:280](/home/flavio/projetos/regent/src/regent/conduction/turn.py:280)); depois disso são executados `git add` e `git commit` sem nova conferência, índice privado ou `update-ref <new> <old>` ([turn.py:284](/home/flavio/projetos/regent/src/regent/conduction/turn.py:284)). Um takeover entre as linhas 281 e 288 permite ao dono antigo publicar o commit. O caminho `TURN_OK` recebeu CAS; o operacional não.

3. **ALTA — gates com saída truncada quebram atribuição e deixam o worktree sujo.** `run_gate` cria também `GATE-STEP-NN.md-FULL.log` quando a saída excede 200 KiB ([gate.py:35](/home/flavio/projetos/regent/src/regent/conduction/gate.py:35), [gate.py:57](/home/flavio/projetos/regent/src/regent/conduction/gate.py:57)). `run_turn` isenta e commita somente o arquivo `.md` ([turn.py:170](/home/flavio/projetos/regent/src/regent/conduction/turn.py:170), [turn.py:205](/home/flavio/projetos/regent/src/regent/conduction/turn.py:205), [turn.py:210](/home/flavio/projetos/regent/src/regent/conduction/turn.py:210)). O sidecar vira mudança sem `post`, normalmente fora de `gate_envelope`, produzindo `TURN_VIOLATION`; no commit operacional ele permanece fora do commit.

4. **ALTA — “STEP corrente” pode ser contornado escolhendo outro `artifact_dir`.** O diretório precisa apenas estar em qualquer lugar sob `.regent` ([turn.py:106](/home/flavio/projetos/regent/src/regent/conduction/turn.py:106)), e `_current_step` procura `STEP-NN.md` nesse diretório fornecido ([turn.py:54](/home/flavio/projetos/regent/src/regent/conduction/turn.py:54)). Assim, mesmo existindo o STEP no `PLAN-NNN/build`, passar um diretório alternativo vazio sob `.regent` faz o STEP parecer corrente. O vínculo de `declared_in`, o gate por bloco e o containment por realpath foram corrigidos.

5. **MÉDIA — modo/tipo continuam fora da prova Git.** A correlação `pre ALLOW + (path, tool_use_id)` e o envelope de deleção foram corrigidos, mas a verificação ainda compara apenas SHA-256 do conteúdo ([turnlog.py:167](/home/flavio/projetos/regent/src/regent/conduction/turnlog.py:167)). Um `chmod` posterior ao `post`, preservando bytes, continua aceito, contrariando explicitamente o contrato de modo/tipo.

6. **MÉDIA — o hook não nega todo payload malformado.** Tools desconhecidas agora são negadas, mas uma tool allowlisted como `Read` com `tool_input` de tipo inválido passa diretamente ([hookscript.py:92](/home/flavio/projetos/regent/src/regent/conduction/hookscript.py:92), [hookscript.py:114](/home/flavio/projetos/regent/src/regent/conduction/hookscript.py:114)). Também não há teste novo cobrindo payload malformado/default-deny.

Os itens 1 e 5 foram fechados; 2, 3, 4, 6, 7, 8 e 9 ficaram apenas parcialmente fechados. Não pude revalidar os gates neste sandbox somente-leitura: os 172 testes foram descobertos, mas 167 abortaram porque `tempfile` não encontrou diretório gravável. O registro versionado declara 172 verdes 3× e gate-package 0.6.0, mas isso não cobre os contraexemplos acima.

REPROVADO