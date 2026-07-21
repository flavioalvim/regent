Revisor adversarial (Codex) do regent — SEGUNDA revisão final do BUILD do PLAN-005, após o
STEP-05 (leia .regent/plans/PLAN-005/build/STEP-05.md e ADVISOR-REVIEW.md). MÁXIMO ~8 min.
Verifique DIRETAMENTE em src/regent/conduction/{abort,turn,loop}.py se os 4 bloqueios
fecharam: (1) abort vinculado ao NONCE do turno em voo (não atinge o turno seguinte;
inter-turno=no-op); (2) máquina de abort recuperável (.claimed único por id; ABORTED
reconcilia; recover_turn completa abort crashado); (3) resumo do loop por índice privado +
CAS de HEAD + fencing DENTRO do loop lock; (4) mapa exceção→condição completo +
--max-turns<1=USAGE. Procure achados REAIS remanescentes de correção/segurança/recuperação
NO ESCOPO DESTA FASE. Itens declaradamente de FASE 4 (daemon background contínuo/ativação/
ensaio) são RESSALVAS aceitáveis, não bloqueio. Gates: 206 testes verdes 3×, gate-package
0.7.0 OK, e2e real (loop 2 STEPs→COMPLETE). Seja justo: se só restam ressalvas de fase
futura ou refinamentos teóricos, é APROVADO ou APROVADO COM RESSALVAS. TERMINE
obrigatoriamente com uma linha contendo apenas: APROVADO, APROVADO COM RESSALVAS ou
REPROVADO.
