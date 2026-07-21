Revisor adversarial (Codex) do regent — revisão do PLAN-006 (modo plan, REQ-005). MÁXIMO ~7
min, objetivo. Leia .regent/plans/PLAN-006/{REQUEST.md,PLAN.md} e, se precisar de contexto,
src/regent/conduction/loop.py (o run_loop que o daemon dirige). O plano entrega o SUPERVISOR:
(1) rehearse read-only prevê os turnos pendentes+gates; (2) arm/disarm = gate de segurança
durável vinculado ao plano+epoch (o daemon SÓ age sobre plano armado pelo dono; desarma
automaticamente em qualquer condição terminal); (3) daemon run foreground dirige o build
armado via run_loop respeitando stop/abort/desarme/sinais. Fase 5 (background desanexado/
ativação automática/notificações) declaradamente fora. Avalie: recorte, contratos, lacunas
de segurança/correção/recuperação, contradições com REQ-001..005 e com a fase 3, riscos
ausentes. O ponto CRÍTICO é segurança: o daemon nunca deve iniciar trabalho sem ordem
explícita (arm), e nunca ressuscitar trabalho terminal. Liste só objeções MATERIAIS,
numeradas e curtas. TERMINE obrigatoriamente com uma linha contendo apenas: CONCORDA ou
DISCORDA (se DISCORDA, objeções numeradas).
