Revisor adversarial (Codex) do produto regent — revisão do PLAN-004 (modo plan, REQ-005).
MÁXIMO ~7 minutos, seja objetivo. Leia: .regent/plans/PLAN-004/{REQUEST.md,PLAN.md} e, se
precisar de contexto, src/regent/conduction/ (fase 1 já entregue) e docs/PRD.md. O plano
entrega `regent turn run`: um claude -p CONFINADO (settings privado + hook PreToolUse/
PostToolUse com HMAC por turno, sem Bash, escrita restrita ao envelope), verificação da
cadeia HMAC do log, gate mecanizado e COMMIT PELO SUPERVISOR (nunca pelo agente). Fase 3
(daemon/loop/--abort) declaradamente fora. Avalie: recorte correto p/ uma fase? contratos
implementáveis (hook, cadeia HMAC, confinamento, verificação git×envelope×log)? lacunas de
segurança/correção? contradições com REQ-001..005 e com a fase 1? riscos ausentes? Liste
só objeções MATERIAIS, numeradas e curtas. TERMINE obrigatoriamente com uma linha contendo
apenas: CONCORDA ou DISCORDA (se DISCORDA, objeções numeradas).
