Revisor adversarial (Codex) do regent — SEGUNDA revisão final do BUILD do PLAN-004, após o
STEP-05 (leia .regent/plans/PLAN-004/build/STEP-05.md — mapa dos seus 9 achados — e
ADVISOR-REVIEW.md com sua reprovação anterior). MÁXIMO ~8 min. Verifique DIRETAMENTE em
src/regent/conduction/{hookscript,turnlog,turn}.py se os 9 fecharam: (1) re-baseline dos
efeitos do gate + gate_envelope ⊆ envelope; (2) isenção por ARQUIVO específico do
supervisor; (3) evidência do gate no commit + git reset --mixed sincroniza índice normal;
(4) current-step calculado + declared_in vinculado ao PLAN.md da atividade + gate extraído
do bloco do step + containment por realpath; (5) exit não-zero → FAILURE; (6) checkpoint
durável de fase + stop_check + keepalive cobrindo launch E gate; (7) fencing+CAS
imediatamente antes do update-ref, commit operacional também fencido; (8) atribuição por
(path,tool_use_id) com pre ALLOW; (9) hook default-deny por allowlist. Procure regressões
ou achados REAIS remanescentes. Gates: 172 testes verdes 3×, gate-package 0.6.0 OK, e2e
real refeito (TURN_OK commita gate evidence + índice limpo). TERMINE obrigatoriamente com
uma linha contendo apenas: APROVADO, APROVADO COM RESSALVAS ou REPROVADO.
