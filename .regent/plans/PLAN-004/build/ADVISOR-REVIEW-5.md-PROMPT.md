Revisor adversarial (Codex) do regent — QUINTA revisão final do BUILD do PLAN-004, após o
STEP-08 (leia .regent/plans/PLAN-004/build/STEP-08.md e ADVISOR-REVIEW-4.md). MÁXIMO ~7 min.
O STEP-08 fechou o cluster de stop/suspensão: helper _boundary (heartbeat+stop_check+
suspend+raise) em COMPOSED/LAUNCHED/GATED + stop_check IMEDIATAMENTE antes do COMMITTING
(stop durante verify/atribuição/evidência suspende em vez de commitar); _stopped_suspend
não engole falha (takeover→CONFLICT); stop_check antes do checkpoint VERIFIED. Verifique em
src/regent/conduction/turn.py se os 3 pontos fecharam e se resta bloqueio REAL de
correção/segurança/atribuição NO ESCOPO DESTA FASE. Itens de fase 3 (daemon/loop contínuo/
--abort/ensaio/decisão automática de turno) e a janela mínima teórica entre fencing e
update-ref são RESSALVAS aceitáveis já declaradas, não bloqueios. Gates: 182 testes verdes
3×, gate-package 0.6.0 OK, e2e real. TERMINE obrigatoriamente com uma linha contendo apenas:
APROVADO, APROVADO COM RESSALVAS ou REPROVADO.
