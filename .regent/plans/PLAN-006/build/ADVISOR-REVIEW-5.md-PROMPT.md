Revisor adversarial (Codex) do regent — RE-REVISÃO do BUILD do PLAN-006 (condução fase 4),
5ª rodada. Rodada 4 REPROVOU com 1 bloqueador (ordenação de durabilidade do fsync);
corrigido (ver .regent/plans/PLAN-006/build/ADVISOR-REVIEW-4-FIXES.md). MÁXIMO ~8 min.

Verifique DIRETAMENTE em src/regent/conduction/supervisor.py:
- `_unlink_durable`: o `fsync` do diretório roda MESMO quando o arquivo já sumiu
  (FileNotFoundError=pass, mas fsync mesmo assim); erro de fsync PROPAGA.
- `disarm`: o caminho "no arm token" chama `_unlink_durable` (barreira de durabilidade)
  antes de declarar ausente; fsync falho → `{"disarmed": false, "reason": "fsync failed"}`
  (não-benigno). Assim `_confirm_disarmed` re-tenta e, persistindo, o daemon reporta
  DISARM_FAILED. Uma remoção só é confirmada após um fsync de diretório bem-sucedido.

Confirme que a janela de ressurreição pós-crash está fechada: nenhum terminal limpo
(STEPS_COMPLETE/ok=true) é reportado sem um fsync de diretório bem-sucedido após a remoção.

Procure QUALQUER bug REAL remanescente de correção/segurança/recuperação nos contratos da
fase 4 (rehearse, arm/read_arm/disarm, run_daemon, guard, loop guard). Se NÃO houver
bloqueador nem alto reais, APROVE — ressalvas menores e itens declaradamente de FASE 5
(daemon background, ativação automática, notificações) NÃO são bloqueio. Gates verdes: 255
testes, gate-package 0.8.0 OK, e2e real (arm→daemon --once dirige 2 STEPs→STEPS_COMPLETE→
desarma).

TERMINE obrigatoriamente com uma linha contendo APENAS uma destas: APROVADO,
APROVADO COM RESSALVAS ou REPROVADO.
