Revisor adversarial (Codex) do regent — RE-REVISÃO do BUILD do PLAN-006 (condução fase 4),
3ª rodada. Rodada 2 REPROVOU com 1 bloqueador + 3 altos; TODOS corrigidos (ver
.regent/plans/PLAN-006/build/ADVISOR-REVIEW-2-FIXES.md). MÁXIMO ~8 min, objetivo.

Verifique DIRETAMENTE em src/regent/conduction/supervisor.py e src/regent/conduction/loop.py:
(#1) `_unlink_durable`: FileNotFoundError=sucesso; qualquer outra falha de unlink/fsync
PROPAGA. `disarm` captura OSError da remoção → `{"disarmed": false, "reason": "unlink
failed"}` (nunca sucesso falso). O descarte em `read_arm` mantém o token se a remoção falhar
e nunca alega sucesso. Confirme que não há mais sucesso-sem-remoção.
(#2) o `guard` do daemon revalida `_approval_status(root, plan) == "APPROVED"` além de sinal/
CONCLUSION.md/binding do arm. Confirme que APPROVAL revogado na janela topo-do-loop→lançamento
barra o turno.
(#3) `_validate_arm_config` retorna cópia CANÔNICA com paths ABSOLUTOS (prompt_template,
declared_in, artifact_dir, envelope, gate_envelope); `arm` grava essa cópia no token. Confirme
que o daemon roda igual de qualquer CWD.
(#4) `emit()` captura QUALQUER exceção de `on_state` (ex.: BrokenPipeError) e seta o flag de
parada — a exceção nunca escapa e o token sempre desarma. Confirme.

Procure NOVOS bugs REAIS de correção/segurança/recuperação introduzidos por ESTAS correções
(ex.: canonização que quebra o vínculo declared_in↔plan_dir; guard que agora chama
_approval_status a cada turno com custo/efeito colateral; emit que engole erro legítimo e
mascara; propagação de OSError em disarm chamada de dentro do run_daemon terminal deixando
estado inconsistente). Se NÃO houver bloqueador nem alto reais remanescentes, APROVE (ressalvas
menores são aceitáveis). Itens de FASE 5 (daemon background, ativação automática, notificações)
são fora de escopo. Gates verdes: 251 testes, gate-package 0.8.0 OK, e2e real (arm→daemon
--once dirige 2 STEPs→STEPS_COMPLETE→desarma).

TERMINE obrigatoriamente com uma linha contendo APENAS uma destas: APROVADO,
APROVADO COM RESSALVAS ou REPROVADO.
