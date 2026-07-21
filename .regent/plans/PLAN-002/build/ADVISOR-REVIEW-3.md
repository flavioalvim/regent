---
outcome: SUCCESS
exit_code: 0
timestamp: 2026-07-21T00:01:41Z
linkage: PLAN-002/build
verdict: REPROVADO (contabilidade permissiva/incoerente; escapes residuais do init)
---

Os achados não fecharam integralmente.

1. **BLOQUEANTE — `explain` ainda não é default-deny com contabilidade exata.**

   Em [activity.py](/home/flavio/projetos/regent/src/regent/activity.py:466), a condição implementada é `delta <= accountable`, não `delta == accountable`.

   Contraexemplos reproduzidos:

   - Append de `stop_request_discarded` com `request_id`, sem mudança no control: `unexplained: []`.
   - Duas mutações contabilizadas com delta de versão 1: também aprovado.
   - Descarte legítimo `stop_request: objeto → null`, com audit correspondente e delta 1: recusado como `stop_request` inexplicado.

   Portanto, audit inventado ou desacoplado pode passar, enquanto a transição legítima declarada não passa. Os testes novos não cobrem esses casos.

2. **ALTA — guarda de symlink e journal do `init` continuam parciais.**

   - A guarda ancestral é explicitamente ignorada para itens `symlink` em [initcmd.py](/home/flavio/projetos/regent/src/regent/initcmd.py:122). Assim, `.claude/skills` apontando para fora permite criar as integrações fora do projeto em [initcmd.py](/home/flavio/projetos/regent/src/regent/initcmd.py:171).
   - O journal previsível é escrito com `write_text` em [initcmd.py](/home/flavio/projetos/regent/src/regent/initcmd.py:151); um `.init-journal.json` preexistente como symlink é seguido e pode sobrescrever arquivo externo.
   - Falha ao remover journal ou `.regent` durante rollback é silenciada em [initcmd.py](/home/flavio/projetos/regent/src/regent/initcmd.py:181), podendo ainda resultar na mensagem “all changes rolled back”. No caminho de sucesso, falha ao remover o journal também é ignorada.

   A atomicidade declarada por arquivo + journal + reexecução é uma ressalva aceitável; esses escapes e mensagens incorretas não são consequência inevitável desse modelo.

3. **Contrato JSON — fechado nos pontos solicitados.**

   `USAGE.detail` virou string, `ACTIVITY_OPEN` voltou ao keyset exato, `TOKEN_MISMATCH` emite strings e linha corrompida do audit vira sentinela.

A versão 0.4.0 e `git diff --check` estão corretos. Minha tentativa do gate descobriu os 106 testes, mas 102 não puderam iniciar porque o sandbox não oferece diretório temporário gravável; isso não contradiz os 106 verdes registrados. De todo modo, os contraexemplos acima são determinísticos e não cobertos pelos gates atuais.

Single-host, daemon/`--abort` futuros e atomicidade por arquivo com convergência permanecem ressalvas aceitáveis. A atribuibilidade ainda permissiva é bloqueante.

REPROVADO