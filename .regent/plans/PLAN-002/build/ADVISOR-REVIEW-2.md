---
outcome: SUCCESS
exit_code: 0
timestamp: 2026-07-20T23:53:42Z
linkage: PLAN-002/build
verdict: REPROVADO (atribuibilidade bloqueante; init parcial; contrato JSON medio)
---

A segunda revisão ainda encontra um bloqueante real. O bloqueante de concorrência foi fechado; o de atribuibilidade, não.

### Achados

1. **BLOQUEANTE — `control explain` ainda não é default-deny.**

   - Alterações isoladas de `version` e `updated_at` são sempre consideradas explicadas, embora nenhuma operação legítima necessariamente as justifique. Reproduzi com um control válido: `version: 10→999` resultou em `unexplained: []` ([activity.py](/home/flavio/projetos/regent/src/regent/activity.py:423)).
   - O `control.version` registrado no início da etapa pela skill nunca é fornecido nem comparado pelo comando. Ele compara somente `HEAD↔worktree`, contrariando o contrato inicial/final do PLAN ([activity_cli.py](/home/flavio/projetos/regent/src/regent/activity_cli.py:179), [SKILL.md](/home/flavio/projetos/regent/src/regent/templates/skills/regent/SKILL.md:70), [PLAN.md](/home/flavio/projetos/regent/.regent/plans/PLAN-002/PLAN.md:124)).
   - O audit não é realmente comparado: contam-se as linhas no HEAD e toma-se o sufixo atual. Remover ou alterar linhas preexistentes sem aumentar a contagem produz delta vazio e aprovação ([activity_cli.py](/home/flavio/projetos/regent/src/regent/activity_cli.py:203)).
   - Eventos permitidos são validados apenas pelo nome, sem schema ou vínculo com a transição ([activity.py](/home/flavio/projetos/regent/src/regent/activity.py:450)).
   - O teste novo inclusive chama de legítimo um `stop_request` incompleto; o CLI rejeitaria esse objeto via schema, mas o teste não demonstra a alegada validação “bem formada” ([test_step06_fixes.py](/home/flavio/projetos/regent/tests/test_step06_fixes.py:69)).

2. **ALTA — o achado de atomicidade/symlinks do init foi fechado apenas parcialmente.**

   A substituição por arquivo e o conflito para symlink no próprio `SKILL.md` estão corretos. Ainda restam:

   - Symlinks em diretórios ancestrais são seguidos; `path.is_symlink()` verifica somente o componente final. Um `.regent/skills/regent` apontando para fora ainda permite criar ou atualizar um `SKILL.md` externo ([initcmd.py](/home/flavio/projetos/regent/src/regent/initcmd.py:84)).
   - O tempfile previsível também pode ser um symlink preexistente e é aberto com `write_text` antes do `replace` ([initcmd.py](/home/flavio/projetos/regent/src/regent/initcmd.py:176)).
   - A atomicidade continua sendo por arquivo, não da instalação: morte entre itens deixa versões misturadas até nova execução.
   - Falhas do rollback continuam silenciadas, embora a mensagem afirme que todas as mudanças foram restauradas ([initcmd.py](/home/flavio/projetos/regent/src/regent/initcmd.py:152), [initcmd.py](/home/flavio/projetos/regent/src/regent/initcmd.py:183)). Isso não satisfaz integralmente o contrato de rollback seguro e ausência de estado parcial do [PRD](/home/flavio/projetos/regent/docs/PRD.md:92).

3. **MÉDIA — o contrato JSON ainda não está completamente saneado.**

   - Tipo de atividade inválido retorna `USAGE` com `detail` objeto, mas `USAGE.detail` deve ser string ([activity.py](/home/flavio/projetos/regent/src/regent/activity.py:143)).
   - ID divergente no resume retorna `ACTIVITY_OPEN.detail` com o campo adicional `asked`, fora do schema exato ([activity.py](/home/flavio/projetos/regent/src/regent/activity.py:170)).
   - Se o release estrito falhar com `NotLockOwner` depois do CAS de suspend/conclude, o control já não possui `turn`; o handler então emite `control_token: null`, embora o contrato exija string ([activity_cli.py](/home/flavio/projetos/regent/src/regent/activity_cli.py:130), [PLAN.md](/home/flavio/projetos/regent/.regent/plans/PLAN-002/PLAN.md:41)).
   - Audit JSON corrompido pode escapar de `read_all()` como `JSONDecodeError`, quebrando a garantia de stdout sempre JSON.

### Situação dos oito achados anteriores

| Achado | Resultado |
|---|---|
| Composição `start/resume` | **Fechado** — `ops flock`, guards e pós-condição do teste estão adequados no escopo single-host. |
| Atribuibilidade | **Não fechado — bloqueante.** |
| Release/limpeza silenciosos | **Fechado** no fluxo principal; falhas reais propagam. |
| Upgrade atômico/symlink | **Parcial**, com problemas altos acima. |
| Takeover idle/SUSPENDED | **Fechado.** |
| Catálogo JSON | **Parcial**, com violações médias acima. |
| Dados requeridos pelas skills | **Fechado**: reason e checkpoint chegam aos consumidores. |
| Dois esquemas | **Fechado**: conteúdo aberto ou terminal em ambos produz `MULTIPLE_SCHEMES`. |

São ressalvas aceitáveis: o `flock` ser exclusivamente single-host; daemon e `--abort` permanecerem futuros; e as extensões declaradas `UNATTRIBUTABLE` e `ActivityObj.checkpoint/reason`.

Os hashes atuais das duas skills estão no manifesto, versão 0.4.0 está consistente e `git diff --check` passou. Tentei rerodar os 102 testes, mas este sandbox não oferece diretório temporário gravável: 98 testes falharam no `TemporaryDirectory`, não no produto. Portanto não contradigo a evidência registrada de 102 verdes 3× e gate-package, mas esses gates não cobrem os contraexemplos acima.

REPROVADO