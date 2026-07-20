---
outcome: SUCCESS
exit_code: 0
timestamp: 2026-07-20T22:00:32Z
linkage: PLAN-001/build
verdict: REPROVADO (3a revisao: 2 bloqueantes de janela + epoch floor + bool)
---

Ainda restam falhas reais de correção nos cenários concorrentes previstos pelo produto.

1. **BLOQUEANTE — `release` continua com TOCTOU.** A leitura do owner ocorre antes do `rename` ([lock.py](/home/flavio/projetos/regent/src/regent/protocol/lock.py:108), [lock.py](/home/flavio/projetos/regent/src/regent/protocol/lock.py:117)). Interleaving alcançável:

   1. R valida seu token antigo.
   2. Um takeover substitui o lock.
   3. R renomeia o lock novo.
   4. R detecta a divergência, mas, enquanto tenta restaurar, outro `acquire` ocupa o path.
   5. A restauração falha e o lock legítimo fica isolado no aside.

   Portanto, verificar antes do rename apenas deslocou a janela; não tornou o claim token-condicional. O teste continua sequencial e só chama o release antigo depois que o takeover terminou ([test_lock.py](/home/flavio/projetos/regent/tests/test_lock.py:151)).

2. **BLOQUEANTE — fence-before-handover não está serializado entre takeovers.** Depois de remover o lock suspeito, o path fica vazio enquanto o control é rotacionado e antes do novo `mkdir` ([lock.py](/home/flavio/projetos/regent/src/regent/protocol/lock.py:183), [lock.py](/home/flavio/projetos/regent/src/regent/protocol/lock.py:190)). Nesse intervalo:

   1. A remove o lock antigo.
   2. B observa `free`, portanto usa `previous=None`.
   3. A rotaciona o control para token A.
   4. B rotaciona incondicionalmente para token B, pois a divergência só é verificada quando `previous is not None` ([lock.py](/home/flavio/projetos/regent/src/regent/protocol/lock.py:211)).
   5. A cria o lock e retorna sucesso; B perde o `mkdir`.
   6. Estado final: lock A, control B.

   Além disso, uma rotação divergente é apenas auditada; o takeover ainda cria o lock ([lock.py](/home/flavio/projetos/regent/src/regent/protocol/lock.py:218)). Isso pode deixar permanentemente separados o owner físico e o token aceito pelo fencing. O teste de corrida não passa `control_store`, e o teste fim-a-fim é sequencial, portanto nenhum cobre esse caso.

3. **ALTA — o piso de epoch ainda pode ser apagado na conclusão.** `_check_epoch_monotonic` retorna imediatamente quando o novo `activity` é `null` ([control.py](/home/flavio/projetos/regent/src/regent/protocol/control.py:270)). Assim, aceita concluir epoch 10 gravando `last_concluded.epoch=1` — ou `last_concluded=null` — e depois reiniciar com epoch 2. Reproduzi em memória a sequência aceita `10 → idle(last_concluded=1) → 2`. O teste só exercita a conclusão bem-formada com epoch 10, sem tentar corromper o piso.

4. **MÉDIA — tipos estritos ainda têm uma exceção.** `schema_version=True` é aceito porque `True == 1` na comparação atual ([control.py](/home/flavio/projetos/regent/src/regent/protocol/control.py:118)). Também há divergência documental: `last_concluded.epoch` passou a ser obrigatório no código, mas continua ausente do schema normativo do [PLAN.md](/home/flavio/projetos/regent/.regent/plans/PLAN-001/PLAN.md:49).

Como ressalva para a fase de condução, o mutex ainda possui a janela `mkdir → meta.json`: um processo vivo suspenso além do timeout pode ser tratado como ownerless e evitado. Isso exige temporização adversarial e não fundamenta sozinho o veredito, mas contradiz a garantia absoluta de que detentores vivos nunca são evitados.

Confirmei as demais correções: verificação imediatamente pré-publicação, `__exit__` token-condicional, `flock` no audit, no-op sem publicação, timestamps tz-aware e tokens 32-hex.

Foram descobertos 37 testes, mas neste sandbox 36 falharam por infraestrutura — não existe diretório temporário gravável; o teste de façade passou. O `twine check --strict` dos artefatos já existentes passou. Isso não contradiz os gates registrados, mas os gates atuais não cobrem os interleavings bloqueantes acima.

REPROVADO