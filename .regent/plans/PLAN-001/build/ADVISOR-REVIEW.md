---
outcome: SUCCESS
exit_code: 0
timestamp: 2026-07-20T21:34:15Z
linkage: PLAN-001/build
verdict: REPROVADO (2 BLOQUEANTES, 3 ALTAS, 3 MEDIAS, 1 BAIXA)
---

Resultado: o build não pode ser aceito. Há duas violações bloqueantes das invariantes centrais de exclusão mútua/CAS.

- **BLOQUEANTE — recuperação do micro-mutex pode permitir dois CAS vencedores.** A recuperação decide que a instância é obsoleta e chama `_remove()` sem qualquer identidade/token da aquisição ([control.py](/home/flavio/projetos/regent/src/regent/protocol/control.py:255), [control.py](/home/flavio/projetos/regent/src/regent/protocol/control.py:281)). Interleaving possível:

  1. A adquire, lê versão N e fica lento.
  2. B considera o mutex velho, remove-o, adquire o mesmo path e publica N+1.
  3. A continua e também publica seu N+1, sobrescrevendo B.

  Mesmo com A morto, dois recuperadores podem ambos julgar a instância antiga; o segundo pode remover o mutex recém-criado pelo primeiro. Os testes exercitam apenas um sucessor após crash, não recuperação concorrente nem holder vivo expirado. Isso invalida o “CAS REAL”.

- **BLOQUEANTE — `release` e `heartbeat` podem destruir ou usurpar um lock tomado por outro holder.** Ambos validam o token em `_owner_or_raise()` e só depois operam novamente pelo path canônico ([lock.py](/home/flavio/projetos/regent/src/regent/protocol/lock.py:71), [lock.py](/home/flavio/projetos/regent/src/regent/protocol/lock.py:75), [lock.py](/home/flavio/projetos/regent/src/regent/protocol/lock.py:151)). Se um takeover ocorrer entre essas ações:

  - `release(old_token)` apaga `owner.json` e o diretório do novo owner;
  - `heartbeat(old_token)` sobrescreve `owner.json` do novo owner com o token antigo.

  A guarda ABA do takeover não protege essas operações. Além disso, um candidato perdedor pode renomear temporariamente o lock fresco e tentar restaurá-lo ([lock.py](/home/flavio/projetos/regent/src/regent/protocol/lock.py:111)); nessa janela o path aparece livre e um terceiro `acquire()` pode vencer, impedindo a restauração. O teste de corrida verifica apenas `["lost", "won"]`, não que o token vencedor continue sendo o owner ([test_lock.py](/home/flavio/projetos/regent/tests/test_lock.py:80)).

- **ALTA — fencing takeover→control não é fim-a-fim.** `takeover()` apenas retorna o novo token; não atualiza nem coordena `control.activity.turn.token`. Até uma chamada posterior fazer isso, operações protegidas pelo token antigo continuam aceitas pelo `ControlStore`. O teste denominado fim-a-fim cria o control somente depois do takeover, já contendo o token novo ([test_lock.py](/home/flavio/projetos/regent/tests/test_lock.py:114)); portanto não testa a rotação de um control existente nem a janela vulnerável.

- **ALTA — o schema v1 não é estrito/default-deny e abre uma falha na obsolescência.** A validação do request exige apenas quatro campos e não exige a presença de `turn_token` ([control.py](/home/flavio/projetos/regent/src/regent/protocol/control.py:95)). `_matches_current()` interpreta campo ausente como `null`, isto é, canal do mediador ([stop.py](/home/flavio/projetos/regent/src/regent/protocol/stop.py:120)). Assim, um request corrompido/legado sem fencing passa na validação e sobrevive ao takeover. Também são aceitos timestamps inválidos, IDs não UUID, `turn.owner` divergente, campos ausentes/extras e tipos inadequados; `activity` não-mapping pode produzir `AttributeError`. A monotonicidade de `activity.epoch` entre versões tampouco é aplicada.

- **ALTA — mudanças auditáveis possuem janelas de crash sem auditoria.** Takeover, recuperação do mutex e descarte do stop-request alteram estado antes de chamar `AuditLog.append()` ([lock.py](/home/flavio/projetos/regent/src/regent/protocol/lock.py:111), [control.py](/home/flavio/projetos/regent/src/regent/protocol/control.py:277), [stop.py](/home/flavio/projetos/regent/src/regent/protocol/stop.py:68)). Um crash nessas janelas deixa a ação concluída sem o registro obrigatório. No takeover, crash entre `rename` e `acquire` ainda deixa o lock canônico aparentemente livre.

- **MÉDIA — a durabilidade do audit está incompleta.** O append chama `fsync` somente no arquivo; na primeira criação não sincroniza o diretório, logo a entrada pode desaparecer após queda de energia. Também ignora retorno parcial de `os.write`, podendo persistir uma linha JSON truncada ([audit.py](/home/flavio/projetos/regent/src/regent/protocol/audit.py:31)). O teste apenas confirma que algum `fsync` foi chamado e que escritas pequenas normais não se perderam.

- **MÉDIA — as transições chamadas idempotentes não são no-op.** Tanto regravar um stop-request equivalente quanto reaplicar uma suspensão passam por `mutate()`, incrementam `version`, alteram `updated_at` e republicam o arquivo ([stop.py](/home/flavio/projetos/regent/src/regent/protocol/stop.py:35), [stop.py](/home/flavio/projetos/regent/src/regent/protocol/stop.py:89), [control.py](/home/flavio/projetos/regent/src/regent/protocol/control.py:170)). Além disso, a reaplicação de suspensão aceita qualquer `turn_token` quando o checkpoint coincide. Os testes verificam ID/booleano, não ausência de mutação.

- **MÉDIA — a façade exporta a exceção errada.** `regent.protocol.NotLockOwner` é a classe de `control.py`, enquanto `TurnLock.release/heartbeat` levantam outra classe definida em `lock.py`; portanto `except regent.protocol.NotLockOwner` não captura o erro documentado do lock ([__init__.py](/home/flavio/projetos/regent/src/regent/protocol/__init__.py:17), [lock.py](/home/flavio/projetos/regent/src/regent/protocol/lock.py:40)). A façade ainda acrescenta `MutationMutexBusy`, ausente da lista nominal aprovada.

- **BAIXA — desvios de evidência do plano.** `STEP-01.md` contém placeholder em vez do SHA-base e `STEP-02`–`04` não registram `step_base_sha`, contrariando REQ-005 §3 ([STEP-01.md](/home/flavio/projetos/regent/.regent/plans/PLAN-001/build/STEP-01.md:3), [STEP-02.md](/home/flavio/projetos/regent/.regent/plans/PLAN-001/build/STEP-02.md:1)). O teste nominal `test_suspend_requires_full_payload` não existe exatamente; foi renomeado para `test_suspend_requires_full_payload_and_token` ([test_stop.py](/home/flavio/projetos/regent/tests/test_stop.py:64)).

A publicação do `control.json` contém corretamente `fsync` do arquivo e do diretório, a fórmula de obsolescência está correta para documentos bem-formados, os trailers de etapa existem, e o script de pacote é fail-closed. Esses acertos não compensam as quebras de exclusão mútua.

Não requalifiquei os gates informados: a tentativa de reexecução neste ambiente somente-leitura foi impedida pela ausência de diretório temporário gravável; isso é uma limitação do ambiente de revisão, não um achado do produto.

REPROVADO