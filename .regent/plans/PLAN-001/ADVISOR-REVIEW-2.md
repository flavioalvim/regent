---
outcome: SUCCESS
exit_code: 0
timestamp: 2026-07-20T21:12:27Z
linkage: PLAN-001
verdict: DISCORDA (3 residuais, incorporados no v3)
---

O v2 resolve integralmente P-01/P-03, redução do STEP-03 e gate de empacotamento. Porém, três lacunas das objeções originais ainda impedem aprovação para `/regent build`:

1. **Crash do micro-mutex não tem recuperação definida.** O teste mata o processo antes do `replace`, mas o `mkdir` de mutação pode permanecer para sempre. O plano prevê limpeza apenas de temporários, sem owner/token, detecção de mutex órfão ou teste provando que outra mutação consegue prosseguir após o crash ([PLAN.md](/home/flavio/projetos/regent/.regent/plans/PLAN-001/PLAN.md:57)).

2. **O vínculo do stop-request com o turno é contraditório.** `turn_token` é anulável e a invariante de validade compara somente `activity_id` e `activity_epoch`; os critérios de obsolescência também ignoram o token. Assim, um request do turno anterior dentro da mesma epoch pode ser aceito após takeover, contrariando o fencing/ABA e o “vínculo inequívoco à atividade e ao turno” ([PLAN.md](/home/flavio/projetos/regent/.regent/plans/PLAN-001/PLAN.md:41), [PLAN.md](/home/flavio/projetos/regent/.regent/plans/PLAN-001/PLAN.md:47), [PLAN.md](/home/flavio/projetos/regent/.regent/plans/PLAN-001/PLAN.md:93)).

3. **Os gates ainda não demonstram contratos exigidos nas objeções 3, 6 e 7.** Faltam testes nomeados para rejeição de operação de control com token divergente após takeover, corrida/ABA do takeover, recuperação e nova escrita após crash, e persistência do audit. O plano especifica `fsync` para publicação do control, mas não para o append do `audit.jsonl`; `test_audit_append_and_readback` não prova durabilidade nem concorrência ([PLAN.md](/home/flavio/projetos/regent/.regent/plans/PLAN-001/PLAN.md:60), [PLAN.md](/home/flavio/projetos/regent/.regent/plans/PLAN-001/PLAN.md:67), [PLAN.md](/home/flavio/projetos/regent/.regent/plans/PLAN-001/PLAN.md:84)).

DISCORDA