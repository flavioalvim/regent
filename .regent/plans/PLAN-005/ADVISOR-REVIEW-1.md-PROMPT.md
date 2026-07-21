Revisor adversarial (Codex) do regent — revisão do PLAN-005 (modo plan, REQ-005). MÁXIMO
~7 min, objetivo. Leia .regent/plans/PLAN-005/{REQUEST.md,PLAN.md} e, se precisar de
contexto, src/regent/conduction/turn.py (fase 2, o run_turn que o loop encadeia). O plano
entrega `regent loop run` (encadeia turnos supervisionados sobre um plano de build aprovado;
decide o STEP corrente do DISCO; para em COMPLETE/HALTED/STOPPED/ABORTED/MAX_TURNS; sem
auto-retry) + `--abort` real (abort-request durável no XDG, checado na thread keep-alive do
turno, mata o grupo do agente, suspende). Fase 4 (daemon background/ativação/ensaio)
declaradamente fora. Avalie: recorte, contratos, lacunas de correção/segurança/recuperação,
contradições com REQ-001..005 e com a fase 2, riscos ausentes. Liste só objeções MATERIAIS,
numeradas e curtas. TERMINE obrigatoriamente com uma linha contendo apenas: CONCORDA ou
DISCORDA (se DISCORDA, objeções numeradas).
