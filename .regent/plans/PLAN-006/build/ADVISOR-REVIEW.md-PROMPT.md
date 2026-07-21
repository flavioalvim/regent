Revisor adversarial (Codex) do regent — REVISÃO FINAL DO BUILD do PLAN-006 (condução
fase 4). MÁXIMO ~8 min, objetivo. Plano: .regent/plans/PLAN-006/PLAN.md (v2 APPROVED,
contratos normativos); etapas em .regent/plans/PLAN-006/build/STEP-0{1..4}.md. Base do
build: 56592563 (git diff 56592563..HEAD). Revise DIRETAMENTE:
src/regent/conduction/supervisor.py (rehearse, arm/read_arm/disarm, run_daemon), o
parâmetro `guard` em src/regent/conduction/loop.py, e a fiação CLI em
src/regent/activity_cli.py (rehearse|arm|disarm|daemon + _DAEMON_EXIT), além de
tests/{test_supervisor,test_supervisor_cli}.py.

Foco nos contratos normativos da fase 4 — procure bugs REAIS de correção/segurança/
recuperação NÃO cobertos pelos 240 testes, e desvios não declarados do PLAN.md:

(a) ARM-TOKEN como gate de segurança durável: gravação atômica (tmp+fsync+rename+fsync do
dir, O_EXCL); pré-condições DURAS em arm() (build ACTIVE cujo id==plano, APPROVED, sem
CONCLUSION.md, workspace executável, token CORRENTE); NUNCA autoriza atividade futura;
arm-token de OUTRO plano em disco = ALREADY_ARMED (leitura RAW antes da validação de
vínculo — exige desarme explícito, nunca sobrescreve às cegas).
(b) read_arm() só honra o token se AINDA vinculado à atividade CORRENTE (plan+epoch+token);
takeover (token rotacionado) ou novo ciclo (epoch mudou) → descartado + auditado, nunca
sobrevive a um ciclo. disarm() é CAS por arm_id (daemon antigo A não apaga rearm B).
(c) DAEMON: nunca age sem arm-token VÁLIDO (senão IDLE); guard revalida o arm ANTES de cada
turno (DISARMED só barra INICIAR o próximo); toda condição terminal DESARMA; honra
stop-request e SIGINT/SIGTERM (desarma + sai, handlers restaurados no finally).
(d) SEGURANÇA-CERNE: loop COMPLETE = STEPS_COMPLETE, NÃO "aceito" — o daemon NÃO faz a
revisão final, NÃO cria CONCLUSION.md, NÃO conclui a atividade (decisão MEDIADA do dono).
Verifique que o código honra isso (não conclui, não escreve CONCLUSION).
(e) CLI: exit codes de _DAEMON_EXIT coerentes (OK=0, stop do dono=2, falha=3); arm/disarm/
rehearse retornam JSON puro.

Riscos a sondar: TOCTOU entre read_arm e o início do turno; corrida de disarm/rearm; guard
que não observa desarme concorrente; arm-token que sobrevive a conclude+restart; daemon
que re-tenta sozinho após terminal; escrita não-atômica do arm-token; env do fake-claude.

Itens declaradamente de FASE 5 (daemon em BACKGROUND desanexado, ativação AUTOMÁTICA,
notificações) são fora de escopo — NÃO são bloqueio. Gates verdes: 240 testes 3×,
gate-package 0.8.0 OK, e2e real (arm→daemon --once dirige 2 STEPs→STEPS_COMPLETE→desarma).

TERMINE obrigatoriamente com uma linha contendo APENAS uma destas: APROVADO,
APROVADO COM RESSALVAS ou REPROVADO.
