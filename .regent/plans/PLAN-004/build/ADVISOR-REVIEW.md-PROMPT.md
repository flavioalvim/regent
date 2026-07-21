Revisor adversarial (Codex) do regent — REVISÃO FINAL DO BUILD do PLAN-004 (REQ-005 §6,
condução fase 2). MÁXIMO ~7 min, objetivo. Plano v3: .regent/plans/PLAN-004/PLAN.md;
etapas em .regent/plans/PLAN-004/build/STEP-0{1..4}.md. Revise DIRETAMENTE o código:
src/regent/conduction/{hookscript,turnlog,confine,turn}.py e tests/{test_hookscript,
test_confine,test_turn}.py. Foco nos contratos v3: (a) hook confina por real-path,
Bash/exec negados, fail-closed; cadeia HMAC como AUDITORIA + selo terminal (não anti-forja
do agente); (b) prova de atribuição PELO GIT — diff global == conjunto atribuído, blob
content_sha256 conferido vs evento post, efeitos de gate escopados, exceptuados;
(c) commit do SUPERVISOR por índice privado + CAS de HEAD + fencing de token, agente jamais
commita; (d) pré-condições REQ-005 (build ativo, step corrente, gate do step, artifact-dir
sob .regent, worktree limpo). Procure bugs REAIS de correção/segurança/atribuição não
cobertos pelos 168 testes e desvios não declarados. Gates: 168 testes verdes 3×,
gate-package 0.6.0 OK, e2e real (TURN_OK commita; TURN_VIOLATION não commita o arquivo
escapado). Contexto: fase 3 (daemon/loop/--abort) declaradamente futura; a consulta roda
pelo próprio regent advisor consult (dogfood). Achados com severidade. TERMINE
obrigatoriamente com uma linha contendo apenas: APROVADO, APROVADO COM RESSALVAS ou
REPROVADO.
