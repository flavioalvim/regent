Revisor adversarial (Codex) do regent — RE-REVISÃO do BUILD do PLAN-006 (condução fase 4),
2ª rodada. A 1ª rodada REPROVOU com 5 achados; foram TODOS corrigidos (ver
.regent/plans/PLAN-006/build/ADVISOR-REVIEW-1-FIXES.md). MÁXIMO ~8 min, objetivo.

Verifique DIRETAMENTE se cada correção fecha o achado, SEM regressão:
(#1) `disarm()`, o descarte-de-obsoleto de `read_arm()` e a escrita de `arm()` em
src/regent/conduction/supervisor.py agora são serializados por um flock (`_arm_lock`);
check-and-delete é CAS atômico por arm_id; `read_arm` só descarta o obsoleto se, re-lido
SOB o lock, o arm_id em disco ainda for o mesmo; `_unlink_durable` faz fsync do diretório.
Confirme que não há mais corrida disarm/rearm nem ressurreição após crash.
(#2) o `guard` do daemon em run_daemon retorna False se `build/CONCLUSION.md` existe —
barra INICIAR turno mesmo se a conclusão aparecer após o arm. Confirme.
(#3) em src/regent/conduction/loop.py o guard foi movido para IMEDIATAMENTE antes de
`run_turn` (após preparar o prompt). Confirme que a janela guard→launch é mínima e que o
DISARMED é reportado.
(#4) `_validate_arm_config` valida template/declared_in-sob-o-dir-do-plano/steps-com-gate/
artifact_dir-sob-.regent/envelope na hora do arm; `run_daemon` captura QUALQUER exceção de
`run_loop` (não só LoopError) → DESARMA e reporta FAILED. Confirme que um arm inválido
falha cedo e que uma falha inesperada nunca deixa o token armado.
(#5) `_DAEMON_EXIT` em src/regent/activity_cli.py: SIGNALLED→2, LOOP_MISCONFIGURED→3,
FAILED→3; a CLI `daemon run` emite uma linha JSON por transição + objeto final. Confirme.

Procure NOVOS bugs REAIS de correção/segurança/recuperação introduzidos pelas correções
(ex.: deadlock/reentrância do `_arm_lock`; `read_arm` chamado dentro de um lock já detido;
guard que agora bloqueia indevidamente; validação que rejeita configs legítimas; ordem
ALREADY_ARMED vs validação). Itens de FASE 5 (daemon em background, ativação automática,
notificações) são fora de escopo. Gates verdes: 247 testes, gate-package 0.8.0 OK, e2e real
(arm→daemon --once dirige 2 STEPs→STEPS_COMPLETE→desarma).

TERMINE obrigatoriamente com uma linha contendo APENAS uma destas: APROVADO,
APROVADO COM RESSALVAS ou REPROVADO.
