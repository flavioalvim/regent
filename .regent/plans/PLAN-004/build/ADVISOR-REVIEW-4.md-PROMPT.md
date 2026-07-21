Revisor adversarial (Codex) do regent — QUARTA revisão final do BUILD do PLAN-004, após o
STEP-07 (leia .regent/plans/PLAN-004/build/STEP-07.md e ADVISOR-REVIEW-3.md). MÁXIMO ~8 min.
Verifique DIRETAMENTE em src/regent/conduction/{hookscript,turnlog,turn}.py se os 4
residuais fecharam: (1) stop_check em TODA fronteira + STOPPED suspende a atividade
(suspend_activity) + fsync do dir da fase; (2) evidência de gate pré-criada pelo agente =
violação, nunca isenta/commitada; (3) deleção e swap regular→symlink pós-post = violação
(lstat/islink sem deref; _rel não segue o leaf); (4) build canônico IGUAL + sob root real
(symlink escape fechado). Procure achados REAIS remanescentes de correção/segurança/
atribuição. Se restarem apenas refinamentos teóricos ou itens de fase 3 (daemon/loop/
--abort/ensaio), classifique como RESSALVA e não como bloqueio. Gates: 181 testes verdes
3×, gate-package 0.6.0 OK, e2e refeito (TURN_OK, índice limpo). TERMINE obrigatoriamente com
uma linha contendo apenas: APROVADO, APROVADO COM RESSALVAS ou REPROVADO.
