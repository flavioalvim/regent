---
outcome: SUCCESS
exit_code: 0
timestamp: 2026-07-20T22:09:51Z
linkage: PLAN-001/build
verdict: REPROVADO (4a revisao: TOCTOU da primitiva de mutex + rename-sobre-vazio + remocao nao-estrita)
---

## Achados

1. **BLOQUEANTE — o mutex dedicado ainda não garante exclusão durante recuperação concorrente.** A recuperação faz `recheck → rename` em operações separadas ([control.py](/home/flavio/projetos/regent/src/regent/protocol/control.py:418), [control.py](/home/flavio/projetos/regent/src/regent/protocol/control.py:423)). Interleaving alcançável:

   1. A e B julgam morta a instância D; B conclui o recheck e pausa.
   2. A remove D, adquire o mutex como instância A e inicia uma operação.
   3. B retoma e renomeia incondicionalmente o path canônico — agora pertencente a A.
   4. B percebe o token divergente e tenta restaurar A.
   5. Nesse intervalo, C publica seu staging no path livre; a restauração falha.
   6. A e C executam simultaneamente.

   No mutex de lifecycle isso quebra diretamente a nova serialização, pois `acquire/heartbeat/release/takeover/status` não chamam `verify_still_held()` antes de agir ([lock.py](/home/flavio/projetos/regent/src/regent/protocol/lock.py:81)). No mutex de control, a verificação imediatamente anterior ao `os.replace` também não é atômicamente acoplada a ele ([control.py](/home/flavio/projetos/regent/src/regent/protocol/control.py:320)): A pode ser deslocado depois da verificação, permitindo que A e C publiquem a mesma versão.

   Isso exige mutex órfão e três concorrentes, mas é uma falha real dentro dos cenários suportados de crash-recovery e concorrência multiprocesso — não mero refinamento teórico. A solução estrutural herdou a TOCTOU da primitiva usada como fundação.

2. **ALTA — `os.rename` não implementa aquisição “no-replace” para diretório vazio.** Em POSIX, renomear um diretório sobre outro diretório vazio pode substituir o destino. Assim, `_acquire_locked()` pode sobrescrever diretamente um `turn.lock.d` ownerless ([lock.py](/home/flavio/projetos/regent/src/regent/protocol/lock.py:138)), vencendo sem respeitar grace nem produzir auditoria de takeover. O mesmo ocorre com um mutex ownerless ([control.py](/home/flavio/projetos/regent/src/regent/protocol/control.py:367]), bypassando timeout e recuperação auditada. O próprio BUILD admite artefatos ownerless legados, portanto esse caminho é determinístico e alcançável. O teste existente apenas executa `status()` seguido de `takeover()`; não tenta `acquire()` contra o diretório ownerless ([test_lock.py](/home/flavio/projetos/regent/tests/test_lock.py:74)).

3. **ALTA — falha de remoção pode rotacionar o fence mesmo preservando o lock antigo.** `_remove_tree()` engole qualquer `OSError` e não informa se removeu o lock ([lock.py](/home/flavio/projetos/regent/src/regent/protocol/lock.py:207)). O takeover continua, rotaciona o control e somente depois tenta publicar o novo lock ([lock.py](/home/flavio/projetos/regent/src/regent/protocol/lock.py:111)). Se a remoção falhar por permissão, I/O ou conteúdo inesperado, a rotação pode ser confirmada e `_acquire_locked()` falhar, deixando owner físico antigo e token do control novo. É um caminho operacional de erro real; deveria falhar antes da rotação ou verificar que o path foi efetivamente removido.

As correções de epoch, `schema_version` booleano, ordem lifecycle→mutation e pré-população dos staging dirs estão corretas no fluxo nominal. Também confirmei `diff --check`, façade verde e `twine check --strict` dos dois artefatos. Os 37 testes registrados não cobrem recuperação concorrente do novo lifecycle mutex, aquisição contra ownerless nem falha parcial de remoção; por isso três execuções verdes não alcançam os achados acima.

REPROVADO