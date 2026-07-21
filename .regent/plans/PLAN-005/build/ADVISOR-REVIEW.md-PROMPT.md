Revisor adversarial (Codex) do regent — REVISÃO FINAL DO BUILD do PLAN-005 (REQ-005 §6,
condução fase 3). MÁXIMO ~8 min, objetivo. Plano v3: .regent/plans/PLAN-005/PLAN.md
(contratos + Emendas v3); etapas em .regent/plans/PLAN-005/build/STEP-0{1..4}.md. Revise
DIRETAMENTE: src/regent/conduction/{process,abort,loop}.py e a keepalive/suspensão em
turn.py, + tests/{test_abort,test_loop,test_loop_cli}.py. Foco nos contratos v3:
(a) runner CANCELÁVEL sem deadlock (thread leitora drena stdout; cancel>timeout; aborted!=
timed_out; killpg+reap); (b) abort-request vinculado (id/epoch/token) O_EXCL + nonce de
turno em voo + claim único + descarte de stale auditado; keepalive ~1s seta cancel;
(c) ABORTED e STOPPED suspendem VIA APP LAYER liberando o turn lock (emenda ao PLAN-004);
(d) loop: loop lock (flock), revalida APPROVAL por turno, STEP corrente NÃO-falsificável
(trailer exato + arquivo em HEAD), tentativa max+1, sem auto-retry, mapa exceção→condição
completo, evidência com op-commit CAS. Procure bugs REAIS de correção/segurança/recuperação
não cobertos pelos 204 testes e desvios não declarados. Gates: 204 testes verdes 3×,
gate-package 0.7.0 OK, e2e real (loop 2 STEPs→COMPLETE). Itens declaradamente de FASE 4
(daemon background/ativação/ensaio) são RESSALVAS, não bloqueio. TERMINE obrigatoriamente
com uma linha contendo apenas: APROVADO, APROVADO COM RESSALVAS ou REPROVADO.
