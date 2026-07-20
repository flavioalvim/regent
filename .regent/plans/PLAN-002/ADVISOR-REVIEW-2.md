---
outcome: SUCCESS
exit_code: 0
timestamp: 2026-07-20T22:47:54Z
linkage: PLAN-002
verdict: DISCORDA (6 residuais prescritivos, incorporados no v3)
---

O v2 resolve adequadamente, em nível de plano, as objeções originais 1, 3, 4 e 5. As demais permanecem bloqueadoras; portanto, ainda não está aprovável para `/regent build`.

1. **Objeção original 2 — recuperação incompleta.** A tabela não cobre `turn.json` local divergente ou remanescente após `suspend`/`conclude`; as linhas 7 e 9 simplesmente consideram esses estados “sãos”. Além disso, a linha 3 atribui `ACTIVE+free` a “pós-publicar/pré-lock”, impossível na ordem declarada `acquire→CAS`. Logo, não é verdadeira a afirmação de que todo crash cai numa linha com recuperação idempotente. Faltam também gates das fronteiras de persistência e remoção do token local. [PLAN.md](/home/flavio/projetos/regent/.regent/plans/PLAN-002/PLAN.md:53)

2. **Objeção original 6 — coreografia de commits ainda insuficiente.** Não foi definida a relação com `BASELINE.md`/`BASE-SHA`, nem como distinguir uma mutação operacional pendente de uma alteração indevida nesses mesmos arquivos. Dizer que mudanças em `control.json` e `audit.jsonl` “nunca” são unattributable elimina a verificação default-deny. Também não há mecanismo que impeça um stop concorrente entre inspeção, staging e commit de contaminar o commit deliberado. [PLAN.md](/home/flavio/projetos/regent/.regent/plans/PLAN-002/PLAN.md:86)

3. **Objeção original 7 — matriz ainda não completa.** Faltam explicitamente: incompatibilidade de tipo; `ACTIVE(X)` com X ausente e somente Y aberto; e o caso normal `SUSPENDED(X)` com o diretório X existente. A remoção de `SUSPENSION.md` resolveu a duplicidade do checkpoint, mas não completa a matriz control×arquivos. [PLAN.md](/home/flavio/projetos/regent/.regent/plans/PLAN-002/PLAN.md:75)

4. **Objeção original 8 — sequência canônica não é recuperável integralmente.** A camada de aplicação começa com “evidência já persistida pelo chamador”; portanto, não controla nem registra as fases de encerramento da subetapa, persistência da evidência e confirmação. Não existe journal ou regra observável para retomar do primeiro passo incompleto após crash. As fronteiras, heartbeat e normalização de request suspenso foram resolvidos, mas a exigência central de retomada idempotente não. [PLAN.md](/home/flavio/projetos/regent/.regent/plans/PLAN-002/PLAN.md:69) [PLAN.md](/home/flavio/projetos/regent/.regent/plans/PLAN-002/PLAN.md:93)

5. **Objeção original 9 — contrato JSON continua indeterminado.** `detail` permanece literalmente `<any>`; `status` e `capabilities` usam reticências; e não existem schemas exatos de sucesso para `start`, `suspend`, `conclude`, `heartbeat` e `takeover`. A política de redaction do status também continua ausente. Catálogo, exits, argparse, root e XDG foram acrescentados, mas isso não produz o contrato interoperável pedido. [PLAN.md](/home/flavio/projetos/regent/.regent/plans/PLAN-002/PLAN.md:30)

6. **Objeção original 10 — gates não demonstram todas as correções.** Só há fault injection nomeada para duas fronteiras; faltam `resume`, `conclude` e persistência/remoção do token. Não há teste da linha 5 (`TOKEN_MISMATCH`), das linhas control×arquivos, de rollback/temporários do upgrade ou da compatibilidade real com clean-worktree, `BASE-SHA` e separação dos commits. A réplica afirma testes “por fronteira” e “cada linha da matriz”, mas eles não constam das etapas do plano. [PLAN.md](/home/flavio/projetos/regent/.regent/plans/PLAN-002/PLAN.md:110) [PLAN.md](/home/flavio/projetos/regent/.regent/plans/PLAN-002/PLAN.md:141)

DISCORDA