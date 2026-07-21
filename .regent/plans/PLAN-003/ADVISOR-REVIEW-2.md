---
outcome: SUCCESS
exit_code: 0
timestamp: 2026-07-21T00:27:12Z
linkage: PLAN-003
verdict: DISCORDA (4 residuais: incorporar NOS contratos)
---

O v2 resolve integralmente apenas a proveniência (`--declared-in` obrigatório, comparação verbatim e `PROVENANCE`). As demais objeções aparecem no resumo, na réplica ou em nomes de testes, mas não foram incorporadas de modo consistente aos contratos normativos:

1. `--expect-verdict`: o contrato ainda diz que `outcome: SUCCESS` implica exit 0, sem exceção normativa para a flag explícita sem casamento.
2. Íntegra: o contrato do gate ainda especifica apenas cauda de 200 KiB; não define criação, formato, conflito ou atomicidade de `<artifact>-FULL.log`.
3. `killpg`: `start_new_session=True` e `killpg(SIGKILL)` não constam do contrato/etapas, somente do preâmbulo e da réplica; o teste nomeado não substitui a especificação operacional.
4. Par atômico: o contrato ainda declara conflito apenas para o artefato principal e não normatiza pré-checagem dos dois caminhos, ordem de commit, rollback nem recuperação de falha parcial.

DISCORDA