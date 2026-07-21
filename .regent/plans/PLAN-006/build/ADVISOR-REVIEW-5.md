---
outcome: SUCCESS
exit_code: 0
timestamp: 2026-07-21T10:40:43+00:00
linkage: PLAN-006
verdict: REPROVADO
---

Resultado: a correção da rodada 4 está correta, mas a garantia global ainda possui bloqueadores.

1. **BLOQUEADOR — `IDLE/ok=true` contorna a barreira de durabilidade.** Em [supervisor.py:322](/home/flavio/projetos/regent/src/regent/conduction/supervisor.py:322), quando `read_arm()` não encontra o token, `--once` retorna diretamente `_result("IDLE")` em [supervisor.py:326](/home/flavio/projetos/regent/src/regent/conduction/supervisor.py:326), sem passar por `finish()` ou `_unlink_durable()`.

   Sequência concreta:

   - um `unlink()` remove o token, mas o `fsync` do diretório falha;
   - outra execução do daemon observa o arquivo ausente;
   - retorna `IDLE`, `ok=true`, sem tentar o `fsync`;
   - um crash ainda pode ressuscitar o token.

   Portanto, a afirmação “nenhum terminal limpo/ok=true após remoção sem `fsync` bem-sucedido” ainda é falsa. A confirmação de ausência precisa ser feita sob o arm-lock, com releitura CAS-safe, sem apagar eventual rearm concorrente.

2. **BLOQUEADOR — o loop guard continua com TOCTOU antes do lançamento.** O guard termina em [loop.py:139](/home/flavio/projetos/regent/src/regent/conduction/loop.py:139), mas `run_turn()` só é chamado em [loop.py:147](/home/flavio/projetos/regent/src/regent/conduction/loop.py:147). Nesse intervalo, `disarm()` pode concluir; mesmo assim `run_turn()` prossegue e chega ao agente em [turn.py:262](/home/flavio/projetos/regent/src/regent/conduction/turn.py:262), pois valida apenas o token da atividade, não o arm-token. A proximidade reduz a janela, mas não a fecha. É necessária uma linearização guard→lançamento coordenada com o mesmo lock/lease usado pelo desarme.

3. **ALTO — `read_arm()` não valida realmente o esquema exigido.** `_raw_arm()` aceita qualquer JSON, e o binding em [supervisor.py:211](/home/flavio/projetos/regent/src/regent/conduction/supervisor.py:211) não exige `arm_id` nem `config`. Um objeto ligado ao epoch/token, mas sem `config`, é aceito; depois `armed["config"]` em [supervisor.py:333](/home/flavio/projetos/regent/src/regent/conduction/supervisor.py:333) levanta `KeyError` fora do bloco que converte falhas em `FAILED`, deixando o token e encerrando o daemon sem terminal controlado. JSON não-dicionário também quebra em `.get()`.

Confirmação positiva: `_unlink_durable()` agora sempre executa o `fsync` após `FileNotFoundError`, propaga sua falha, e todos os terminais que passam por `finish()` — inclusive `STEPS_COMPLETE` — só permanecem limpos após `_confirm_disarmed()` observar uma barreira bem-sucedida. Os gates verdes informados não cobrem os interleavings acima.

REPROVADO