Você é o revisor adversarial (Codex/advisor) do produto regent — REVISÃO FINAL DO BUILD do
PLAN-003 (REQ-005 §6). Plano aprovado: .regent/plans/PLAN-003/PLAN.md (v3); registros:
.regent/plans/PLAN-003/build/STEP-0{1..4}.md e BASELINE.md. Revise DIRETAMENTE:
src/regent/conduction/{process,evidence,consult,gate}.py, o wiring em
src/regent/activity_cli.py, as skills religadas (templates) e tests/{test_consult,
test_gate}.py. Verifique fidelidade aos contratos v3 (sandbox forçado; par/conjunto de
evidência atômico com CONFLICT; --expect-verdict explícito fail-closed; proveniência
verbatim; killpg do grupo com teste real de filho órfão; FULL.log; códigos novos), bugs
reais não cobertos pelos 131 testes, e desvios não declarados. NOTA: esta consulta está
sendo executada PELO PRÓPRIO `regent advisor consult` (dogfood) — o artefato que você está
gerando é a evidência automática dele. Gates: 131 testes verdes 3×, gate-package 0.5.0 OK,
e2e real registrado. Contexto: fase 2 (daemon/confinamento) declaradamente futura. Seja
objetivo (máx ~8 min). Achados com severidade. TERMINE obrigatoriamente com uma linha
contendo apenas: APROVADO, APROVADO COM RESSALVAS ou REPROVADO.
