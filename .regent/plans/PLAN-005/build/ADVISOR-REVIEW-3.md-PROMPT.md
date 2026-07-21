Revisor adversarial (Codex) do regent — TERCEIRA revisão final do BUILD do PLAN-005, após
o STEP-06 (leia .regent/plans/PLAN-005/build/STEP-06.md e ADVISOR-REVIEW-2.md). MÁXIMO ~8
min. Verifique em src/regent/conduction/{turn,loop}.py se os 3 residuais fecharam:
(1) recover_turn valida o vínculo do .claimed, não engole falha, só limpa em SUSPENDED+lock
livre, estados de retorno realistas; (2) resumo re-checa token IMEDIATAMENTE antes do
update-ref e rebaixa COMPLETE→LOOP_CONFLICT se o resumo obrigatório não commitar;
(3) spawn/IO→HALTED(FAILURE), git errors→LOOP_CONFLICT com JSON (incl. _committed_steps
antes do try e _write_loop_evidence). Procure achados REAIS remanescentes NO ESCOPO DESTA
FASE. Itens de FASE 4 (daemon background/ativação/ensaio) e janelas teóricas mínimas são
RESSALVAS. Gates: 206 testes verdes 3×, gate-package 0.7.0 OK, e2e real. Seja justo: se só
restam ressalvas de fase futura/teóricas, é APROVADO ou APROVADO COM RESSALVAS. TERMINE
obrigatoriamente com uma linha contendo apenas: APROVADO, APROVADO COM RESSALVAS ou
REPROVADO.
