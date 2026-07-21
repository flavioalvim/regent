---
outcome: SUCCESS
exit_code: 0
timestamp: 2026-07-21T02:50:14+00:00
linkage: PLAN-005
verdict: DISCORDA
---

1. **Avanço do STEP ainda é falsificável.** `git log --grep` prova apenas uma mensagem contendo texto semelhante; não prova que o commit contém o `build/STEP-NN.md` atualmente presente em `HEAD`. Commit alheio, trailer parcial ou STEP revertido pode gerar avanço/`COMPLETE`. Deve validar trailer exato e o artefato versionado correspondente.

2. **A identidade da tentativa é contraditória.** A réplica define linkage `PLAN/STEP/tryK`, mas o PLAN mantém linkage `PLAN/STEP` e sufixa apenas arquivos. Assim, `Regent-Turn` e `recover_turn` podem confundir um HALTED anterior com a tentativa atual. `tryK` precisa integrar linkage, trailers e recuperação; `K` deve ser `max existente + 1`, não contagem. O identificador único de `LOOP-<slug>.md` também precisa ser definido para retries.

3. **O abort continua sujeito à corrida entre turnos.** `activity_id`, `epoch` e `turn_token` permanecem iguais durante vários turnos da mesma atividade. Um pedido criado no fim da tentativa A pode ser validado e matar B. É necessário nonce de execução/tentativa registrado atomicamente como “in flight”. O arquivo global publicado por `rename` também permite que escritores concorrentes se sobrescrevam; `.claimed` fixo não fecha esse protocolo.

4. **O runner por `poll()` pode deadlockar.** Como o processo usa `stdout=PIPE`, apenas consultar `poll()` sem drenar a saída bloqueia filhos que encham o pipe. O contrato deve exigir drenagem concorrente ou `communicate()` com intervalos curtos, além de precedência determinística abort×timeout e reap do grupo.

5. **A máquina de abort não é recuperável sob crash.** Não existe checkpoint durável das fases claim→cancel/kill→evidência→suspensão→release→cleanup. Crash após evidência e antes de `service.suspend` deixa atividade ACTIVE/worktree sujo; `recover_turn` apenas entrega ao mediador, contrariando a reexecução idempotente da sequência do REQ-004. Crash após suspensão e antes do resumo tampouco possui caminho de conclusão.

6. **O mapa exceção→condição ainda não é completo.** Faltam, entre outros, `ARTIFACT_OUTSIDE_REGENT`, `STEP_ALREADY_DONE`, `EvidenceConflict`, falha de spawn, erro Git/op-commit, erro de suspensão/liberação de lock e entrada malformada. A via de op-commit sem fencing também não define CAS, corrida com `resume` nem comportamento de falha preservando `SUSPENDED`; portanto JSON, evidência e estado final continuam não garantidos.

DISCORDA