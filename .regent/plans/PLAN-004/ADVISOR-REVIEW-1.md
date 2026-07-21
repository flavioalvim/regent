---
outcome: SUCCESS
exit_code: 0
timestamp: 2026-07-21T01:31:42+00:00
linkage: PLAN-004
verdict: DISCORDA
---

1. `Regent-Turn` contorna o REQ-005: faltam vínculo rígido a PLAN aprovado/STEP ativo, `STEP-NN.md`, trailer `Regent-Step`, worktree limpo e fases recuperáveis. `artifact-dir` livre também pode violar REQ-001.

2. O confinamento não isola a configuração efetiva. `--settings` mantém fontes omitidas; faltam `--setting-sources ""`, ambiente mínimo e `--tools` explicitamente restritivo. Hooks, plugins, MCPs e ferramentas herdadas permanecem possíveis. [Referência oficial](https://code.claude.com/docs/en/cli-usage).

3. “Segredo só no env do hook; Claude não o vê” é falso: segredo em `settings.json` ou no ambiente de lançamento fica acessível ao processo, enquanto `Read` irrestrito pode alcançar settings privados ou `/proc`. A HMAC não prova antiforja nesse modelo.

4. O contrato do hook é inexequível como escrito: `PostToolUse` não conhece a decisão do Pre nem pode negar após a escrita; DENY não gera Post. São necessários eventos Pre allow/deny e Post success/failure separados, correlacionados por `tool_use_id`. [Semântica oficial](https://code.claude.com/docs/en/hooks).

5. A cadeia HMAC não detecta remoção do último evento nem do log inteiro sem selo terminal esperado. Também faltam serialização canônica e lock para hooks paralelos; `seq`/HMAC anterior podem bifurcar.

6. `git status × envelope × allow` não prova atribuição dos bytes finais: não compara `content_sha256`, modo/tipo/deleção, nem exige diferença global igual ao conjunto atribuído. Pior: o gate roda via Bash depois da verificação e pode alterar um path previamente autorizado, que então será commitado sem novo evento. Regride a prova já adotada de baseline global, blob Git verificado, índice privado e CAS de HEAD.

7. Recuperação e fencing estão ausentes: falha entre gate, evidência, staging e commit deixa artefatos conflitantes sem fase idempotente. Além disso, timeout padrão de 1800 s iguala o `stale_after` da fase 1; sem heartbeat durante launch/gate, takeover pode rotacionar o token antes do commit.

DISCORDA