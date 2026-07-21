Revisor adversarial (Codex) do regent — QUARTA revisão final do BUILD do PLAN-005, após o
STEP-07 (leia .regent/plans/PLAN-005/build/STEP-07.md e ADVISOR-REVIEW-3.md). MÁXIMO ~7 min.
O STEP-07 fechou: (1) recover_turn no ramo SUSPENDED exige marcador VINCULADO E lock FREE
antes de limpar (senão ABORT_RECOVERY_INCOMPLETE/UNBOUND, marcador preservado); (2) QUALQUER
git error no resumo → LOOP_CONFLICT independente da condição anterior; + testes dos ramos.
Verifique em src/regent/conduction/{turn,loop}.py se resta bloqueio REAL de correção/
segurança/recuperação NO ESCOPO DESTA FASE (fase 3: loop + abort). Itens de FASE 4 (daemon
background contínuo/ativação/ensaio/decisão automática de iniciar build) e janelas teóricas
mínimas fencing→update-ref são RESSALVAS aceitáveis já declaradas. Gates: 209 testes verdes
3×, gate-package 0.7.0 OK, e2e real (loop 2 STEPs→COMPLETE). Seja justo: se só restam
ressalvas de fase futura/teóricas, é APROVADO ou APROVADO COM RESSALVAS. TERMINE
obrigatoriamente com uma linha contendo apenas: APROVADO, APROVADO COM RESSALVAS ou
REPROVADO.
