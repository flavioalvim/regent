---
outcome: SUCCESS
exit_code: 0
timestamp: 2026-07-20T21:46:05Z
linkage: PLAN-001/build
verdict: REPROVADO (2 bloqueantes residuais de corrida + 5 achados)
---

A segunda revisão ainda encontra violações das invariantes centrais.

1. **BLOQUEANTE — o micro-mutex ainda admite dois CAS vencedores.** Há TOCTOU entre ler o token julgado e renomear o diretório ([control.py](/home/flavio/projetos/regent/src/regent/protocol/control.py:331)). Interleaving:

   1. R lê a instância obsoleta S.
   2. Outro recuperador remove S; W adquire uma instância nova e passa por `verify_still_held()`.
   3. R renomeia a instância de W, pois o rename não é condicionado ao token ([control.py](/home/flavio/projetos/regent/src/regent/protocol/control.py:354)).
   4. C adquire o path canônico vazio.
   5. R detecta o token divergente, mas não consegue restaurar W porque C ocupa o path.
   6. W continua publicando, pois a verificação já ocorreu. Ao sair, remove incondicionalmente o mutex canônico de C ([control.py](/home/flavio/projetos/regent/src/regent/protocol/control.py:322)).
   7. Se C já tiver passado pela verificação, também publica a mesma versão.

   Portanto, uma instância fresca e viva pode ser deslocada, `verify_still_held` não está acoplado à publicação, e `__exit__` pode apagar mutex alheio. O teste novo cobre somente um PID vivo já estabilizado, não esse ABA.

2. **BLOQUEANTE — `release`/`takeover` ainda abrem o lock para aquisição indevida.** `release` renomeia o lock antes de verificar o token ([lock.py](/home/flavio/projetos/regent/src/regent/protocol/lock.py:103)). Se for um holder antigo, um terceiro pode adquirir o path vazio antes da restauração; esta falha, o lock legítimo fica isolado no aside e o terceiro usurpa o turno. O teste é sequencial e não cobre esse intervalo ([test_lock.py](/home/flavio/projetos/regent/tests/test_lock.py:147)).

   O mesmo gap existe no takeover entre `rename` e `_acquire_with_token` ([lock.py](/home/flavio/projetos/regent/src/regent/protocol/lock.py:159)). Outro candidato pode observar `free`, adquirir pelo retorno antecipado e vencer sem rotacionar o control ([lock.py](/home/flavio/projetos/regent/src/regent/protocol/lock.py:145)). O teste de corrida continua descartando os tokens e verificando apenas `["lost", "won"]`, não o owner final ([test_lock.py](/home/flavio/projetos/regent/tests/test_lock.py:79)).

3. **ALTA — fencing takeover→control ainda possui janela e estado parcial após falha.** O novo lock é publicado e o antigo destruído antes da rotação do control ([lock.py](/home/flavio/projetos/regent/src/regent/protocol/lock.py:174)). Durante essa janela, operações com o token antigo continuam aceitas; crash ou erro em `store.mutate()` deixa lock e control permanentemente divergentes. A mutação também termina silenciosamente sem rotação quando o token anterior não coincide ([lock.py](/home/flavio/projetos/regent/src/regent/protocol/lock.py:185)).

4. **ALTA — epoch não é monotônico através do ciclo ocioso.** A verificação só compara epochs quando `current.activity` e `new.activity` são ambos não nulos ([control.py](/home/flavio/projetos/regent/src/regent/protocol/control.py:244)). A sequência epoch 10 → `activity=null` → mesma atividade com epoch 1 é aceita, reabrindo ABA.

5. **MÉDIA — append parcial perde a segurança concorrente.** O loop trata escrita parcial, mas cada `os.write` é uma operação `O_APPEND` separada ([audit.py](/home/flavio/projetos/regent/src/regent/protocol/audit.py:34)). Dois processos com writes parciais podem intercalar fragmentos e corromper ambas as linhas JSON. O teste concorrente usa writes normais pequenos e não injeta parcialidade. `fsync` de arquivo e diretório está correto.

6. **MÉDIA — no-op não é verdadeiro quando há corrida.** Os fast paths sequenciais são no-op, mas, se uma transição equivalente vencer entre o `load()` externo e o mutator, o callback retorna o body inalterado e `ControlStore.mutate()` ainda chama `cas_write`, incrementando versão e `updated_at` ([stop.py](/home/flavio/projetos/regent/src/regent/protocol/stop.py:39), [stop.py](/home/flavio/projetos/regent/src/regent/protocol/stop.py:107), [control.py](/home/flavio/projetos/regent/src/regent/protocol/control.py:227)). Os testes exercitam somente reaplicação sequencial. A exigência do token suspensor foi corrigida.

7. **MÉDIA — “tipos estritos” permanece incompleto.** `bool` é aceito como `int` para versão e epochs; timestamps sem timezone passam apesar do schema normativo exigir UTC; tokens e IDs declarados UUID4 são apenas strings não vazias ([control.py](/home/flavio/projetos/regent/src/regent/protocol/control.py:92)). Os conjuntos exatos de chaves e `turn.owner == "executor"` foram corrigidos.

Confirmados como corrigidos: heartbeat instance-bound via dir-fd; audit-intent antes das três ações; fsync do arquivo e diretório; `NotLockOwner` unificado; desvio de `MutationMutexBusy` declarado; evidência retroativa das etapas.

Os 36 testes foram descobertos, mas não pude requalificar as três execuções nem o gate-package: o sandbox somente-leitura não oferece diretório temporário gravável, causando 35 erros de infraestrutura no `setUp`. Isso não é achado do produto, mas também não fornece confirmação independente dos gates registrados.

REPROVADO