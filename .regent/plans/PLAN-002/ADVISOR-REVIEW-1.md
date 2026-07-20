---
outcome: SUCCESS
exit_code: 0
timestamp: 2026-07-20T22:43:13Z
linkage: PLAN-002
verdict: DISCORDA (10 objeções)
---

Há bloqueadores de correção, recuperação e aderência aos requisitos.

1. **O upgrade de hosts v0 é impossível pelo `init` atual.** O plano manda hosts sem control executar `regent init`, mas o `init` considera divergente qualquer skill cujo conteúdo não seja idêntico ao template empacotado ([initcmd.py](/home/flavio/projetos/regent/src/regent/initcmd.py:49)). Ao atualizar para skills v1, todo host v0 legítimo entrará em conflito antes de semear o control. É necessário um protocolo de upgrade atômico para versões conhecidas das skills — hashes/manifesto de versão, preservando conteúdo desconhecido — e teste v0→v1 real.

2. **As operações de atividade não são simples wrappers da façade.** O protocolo entregue não possui `start`, `resume` nem `conclude`; ele fornece primitivas independentes de CAS e lock. Cada comando proposto compõe duas transações, uma no XDG e outra no `control.json` ([PLAN.md](/home/flavio/projetos/regent/.regent/plans/PLAN-002/PLAN.md:28)). Faltam ordenação, compensação e recuperação para crashes entre:

   - adquirir lock e publicar ACTIVE;
   - publicar SUSPENDED e liberar lock;
   - adquirir lock e publicar o resume;
   - concluir no control e liberar lock;
   - persistir ou remover `turn.json`.

   Deve existir uma camada de aplicação testável, com tabela explícita de estados divergentes e reexecução idempotente. Também é preciso dizer expressamente se `resume` incrementa o epoch; o PLAN-001 diz que ele incrementa a cada “(re)início”, enquanto o PLAN-002 só promete token novo.

3. **O plano promete recuperação por takeover, mas não oferece comando para realizá-la.** O risco 3 diz que a skill orientará takeover ([PLAN.md](/home/flavio/projetos/regent/.regent/plans/PLAN-002/PLAN.md:110)), porém nenhum subcomando o expõe. Depois da perda de `turn.json`, de um lock suspeito ou de `control=ACTIVE` com lock livre, as skills ficam sem caminho de recuperação, embora `TurnLock.takeover()` exista ([lock.py](/home/flavio/projetos/regent/src/regent/protocol/lock.py:100)). É necessário um takeover explícito, mediado, auditado, com `--reason`, além de uma matriz de reconciliação control×lock.

4. **O contrato do token e a “emenda P-01” se contradizem com o protocolo.** O plano afirma que o token vive “APENAS” no XDG ([PLAN.md](/home/flavio/projetos/regent/.regent/plans/PLAN-002/PLAN.md:41)), mas o schema exige o mesmo token em `control.activity.turn.token`. Deve distinguir “cópia local usada pelo CLI” de “token de fencing autoritativo no control”. P-01 não precisa ser enfraquecido: `TurnLock.acquire()` deve continuar alterando somente XDG; quem também muda `control.json` é a operação composta `activity start`.

5. **O mutex de mutação entregue viola a política XDG que o plano passa a expor em produção.** `ControlStore` coloca `control.json.lock` ao lado do control, dentro de `.regent/`, embora REQ-001 §3 reserve process locks descartáveis ao XDG. O PLAN-002 precisa mover/configurar esse mutex para o state dir local ou declarar e deliberar uma emenda ao requisito; hoje ele simplesmente herda a contradição.

6. **`control.json` versionado torna o protocolo de build incoerente sem coreografia de commits.** `activity start` suja o worktree imediatamente, enquanto REQ-005 §3 exige worktree limpo no início de cada passo. Stop requests e auditorias também podem aparecer durante o build. O plano não define:

   - quando mutações do control recebem commit operacional;
   - relação desse commit com `BASELINE.md` e `BASE-SHA`;
   - como pendência de commit operacional é distinguida de alteração unattributable;
   - como um stop externo evita contaminar o commit deliberado do passo.

   Sem isso, o fluxo feliz do e2e não demonstra conformidade com o build real.

7. **“Control manda” não é uma regra default-deny suficiente.** É preciso tratar todas as combinações entre control e arquivos: atividade apontando para diretório inexistente; ID/tipo incompatível; control ativo A e artefato aberto B; múltiplos artefatos abertos; terminal artifact já existente para atividade ACTIVE; artefato legado aberto com control ocioso. Apenas o último caso foi mencionado ([PLAN.md](/home/flavio/projetos/regent/.regent/plans/PLAN-002/PLAN.md:78)). Também falta especificar se `SUSPENSION.md` deixa de existir; manter checkpoint no arquivo e no control cria duas fontes de verdade.

8. **A sequência de stop continua subespecificada.** `stop request` somente grava a intenção; nada no plano obriga `/regent` a executar `stop check` em fronteiras determinadas, manter heartbeat, persistir evidência antes da suspensão ou retomar do primeiro passo incompleto da sequência canônica de REQ-004 §4. Também é preciso recusar ou normalizar `stop request` quando a atividade já está SUSPENDED — a primitiva atual aceita qualquer atividade não nula ([stop.py](/home/flavio/projetos/regent/src/regent/protocol/stop.py:25)).

9. **O contrato JSON não é implementável de forma interoperável como escrito.** Faltam schemas exatos de sucesso, catálogo de códigos de erro, tipos de `detail`, códigos de saída, política de stderr, erros de parsing do `argparse`, descoberta do root, definição completa do XDG/hash e redaction do status. O critério diz que as skills citarão “códigos de erro exatos”, mas nenhum código é definido. “Capacidades” também não tem schema nem matriz comando×capacidade, apesar de REQ-003 §6 exigir essa matriz; o efeito de control corrupto/uninitialized no exit do `doctor` permanece ambíguo.

10. **Os gates cobrem quase apenas o caminho feliz.** Um teste textual de existência de subcomandos e um e2e `start→suspend→resume→conclude` não cobrem os riscos centrais. São necessários testes de fault injection em cada fronteira lock/control/token, takeover via CLI, duas invocações concorrentes, divergências control×arquivos, upgrade v0→v1, init com control válido já evoluído, rollback incluindo temporários, pureza JSON inclusive em erros de parsing, stop externo honrado em boundary e compatibilidade com clean-worktree/build commits.

DISCORDA