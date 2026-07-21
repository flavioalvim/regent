Revisor adversarial (Codex) do regent — OITAVA revisão final do BUILD do PLAN-005, após o
STEP-11 (leia .regent/plans/PLAN-005/build/STEP-11.md e ADVISOR-REVIEW-7.md). MÁXIMO ~7 min.
O STEP-11 fechou a última janela: checagem FINAL de cancel imediatamente antes de escrever a
evidência → abort na janela verify/attribute/evidence vira ABORTED (evidência ABORTED, handler
COMMITTED suspende sem commitar STEP). Verifique em src/regent/conduction/{gate,turn,loop,abort}.py
se resta bloqueio REAL de correção/segurança/recuperação ALCANÇÁVEL NO ESCOPO DESTA FASE
(fase 3: loop + abort). Itens de FASE 4 (daemon background contínuo/ativação/ensaio/decisão
automática de iniciar build) e a janela teórica MÍNIMA entre a checagem final de cancel e o
update-ref (análoga à ressalva fencing→update-ref já aceita) são RESSALVAS aceitáveis. Gates:
213 testes verdes 3×, gate-package 0.7.0 OK, e2e real (loop 2 STEPs→COMPLETE; abort no gate e
na janela verify→ABORTED+SUSPENDED sem commit). Seja justo: reprovar SÓ por bloqueio material
ALCANÇÁVEL e substantivo nesta fase; se só restam janelas teóricas mínimas ou itens de fase
futura, é APROVADO ou APROVADO COM RESSALVAS. TERMINE obrigatoriamente com uma linha contendo
apenas: APROVADO, APROVADO COM RESSALVAS ou REPROVADO.
