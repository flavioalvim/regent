---
outcome: SUCCESS
exit_code: 0
timestamp: 2026-07-21T01:37:13+00:00
linkage: PLAN-004
verdict: DISCORDA
---

1. O vínculo ao REQ-005 continua incompleto: o v2 não exige que `--step` pertença ao plano aprovado, seja o STEP corrente, nem que o gate seja o daquele STEP. Também não normatiza a criação de `build/STEP-NN.md`; isso aparece apenas na réplica.

2. A prova pós-gate é contraditória: o contrato diz gate antes da verificação, mas as fases executam `VERIFIED → GATED`. Além disso, efeitos legítimos do gate não possuem evento `post`, embora todo path alterado o exija. Assim, ou escapam da prova, ou sempre causam violação.

3. A idempotência permanece apenas declarativa: faltam checkpoint durável, transições atômicas e recuperação `trailer → STEP file → worktree` para crashes em launch, selo, gate, evidência, staging e CAS. Reexecutar agente/gate não é intrinsecamente idempotente, e não há testes de crash nessas fronteiras.

DISCORDA