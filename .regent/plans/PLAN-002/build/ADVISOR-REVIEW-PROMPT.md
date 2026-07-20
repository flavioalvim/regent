Você é o revisor adversarial (Codex/advisor) do produto regent — REVISÃO FINAL DO BUILD do
PLAN-002 (REQ-005 §6). Plano aprovado: .regent/plans/PLAN-002/PLAN.md (v3); registros de
etapa em .regent/plans/PLAN-002/build/STEP-0{1..5}.md (com vermelho→verde fiéis). Revise o
DIFF INTEGRAL: `git diff af59ca6b8b7ad1ff512228acdb09f36629c88604..HEAD` e o código final (src/regent/activity.py,
activity_cli.py, cli.py, initcmd.py, doctor.py, templates/, tests/). Verifique:
(a) fidelidade ao plano v3 — camada de aplicação com a tabela de 12 linhas, contrato JSON
com catálogo/schemas/exit codes, upgrade por manifesto, matriz control×arquivos (que virou
EXECUTÁVEL no workspace.verdict do status — decisão registrada no STEP-04), skills v1 com
fronteiras de stop/heartbeat, coreografia de commits testada, errata do lock file no XDG,
epoch incrementando no resume, P-01 intacto (token autoritativo no control);
(b) bugs reais de correção/concorrência/recuperação que os 92 testes não cubram;
(c) desvios não declarados. Gates registrados: 92 testes verdes 3×, gate-package OK 0.4.0,
e2e real registrado no STEP-05 (host novo + upgrade v0.2 genuíno + ciclo completo com stop
honrado). Contexto: v0→v1 CLI single-host; daemon/confinamento/--abort são fases futuras
declaradas. Emita achados com severidade (BLOQUEANTE/ALTA/MÉDIA/BAIXA). TERMINE
obrigatoriamente com uma linha contendo apenas: APROVADO, APROVADO COM RESSALVAS ou
REPROVADO.
