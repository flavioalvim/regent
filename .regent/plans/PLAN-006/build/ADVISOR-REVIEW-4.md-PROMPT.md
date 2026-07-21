Revisor adversarial (Codex) do regent — RE-REVISÃO do BUILD do PLAN-006 (condução fase 4),
4ª rodada. Rodada 3 REPROVOU com 1 bloqueador + 1 alto; ambos corrigidos (ver
.regent/plans/PLAN-006/build/ADVISOR-REVIEW-3-FIXES.md). MÁXIMO ~8 min, objetivo.

Verifique DIRETAMENTE em src/regent/conduction/supervisor.py:
(#1) todo caminho terminal de `run_daemon` (SIGNALLED, STOPPED, LoopError, FAILED, terminal
normal) passa por `finish()`, que chama `_confirm_disarmed()` (desarma + confirma, re-tenta
3×; "no arm token"/"arm_id mismatch (rearmed)" = já-desarmado). Se a remoção persistir
falhando → estado `DISARM_FAILED` (exit 3, ok=false), token AINDA armado, nunca terminal
limpo. Confirme que o daemon jamais reporta terminal limpo com token armado.
(#2) em `read_arm`, o `audit.append(arm_token_discarded)` só ocorre no ramo `else` (após
`_unlink_durable` bem-sucedido). Confirme que remoção falha ⇒ sem audit de descarte e token
mantido.

Procure NOVOS bugs REAIS (correção/segurança/recuperação) introduzidos por ESTAS correções
(ex.: `_confirm_disarmed` re-tentar mascarar um rearm legítimo; `finish()` alterando estado
que deveria ser preservado; DISARM_FAILED com semântica de exit inconsistente; laço de
re-tentativa preso). Se NÃO houver bloqueador nem alto reais remanescentes, APROVE — ressalvas
menores são aceitáveis e podem ficar para a FASE 5 (daemon background, ativação automática,
notificações), que é fora de escopo. Gates verdes: 253 testes, gate-package 0.8.0 OK, e2e real
(arm→daemon --once dirige 2 STEPs→STEPS_COMPLETE→desarma).

TERMINE obrigatoriamente com uma linha contendo APENAS uma destas: APROVADO,
APROVADO COM RESSALVAS ou REPROVADO.
