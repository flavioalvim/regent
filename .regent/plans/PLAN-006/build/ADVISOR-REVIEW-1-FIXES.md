# PLAN-006 — respostas ao ADVISOR-REVIEW-1 (REPROVADO)

O revisor (Codex) reprovou com 3 bloqueadores + 1 alto + 1 médio, todos REAIS.
Incorporados verbatim, com um teste dirigido por achado.

## #1 (BLOQUEADOR) — `disarm()`/`read_arm()` sem CAS atômico + sem fsync do dir
- `disarm`, a descarte-de-obsoleto de `read_arm` e a escrita de `arm` agora são
  serializadas por um **flock** (`arm.lock`) — check-and-delete é um CAS atômico:
  um daemon antigo (arm_id A) nunca corre um rearm B e o apaga.
- `read_arm` descarta o token obsoleto SÓ se, RE-LIDO sob o lock, o arm_id em disco
  ainda for o mesmo obsoleto (um rearm na janela é preservado).
- Toda remoção agora faz `fsync` do diretório (`_unlink_durable`) — um crash após
  `unlink` não ressuscita o token.
- Testes: `test_read_arm_discard_keeps_rearmed_token`,
  `test_disarm_cas_old_id_does_not_remove_rearm` (mantido).

## #2 (BLOQUEADOR) — daemon podia iniciar turno após `CONCLUSION.md`
- O `guard` do daemon agora retorna False se `build/CONCLUSION.md` existe — barra
  INICIAR qualquer turno mesmo que a conclusão apareça após o arm (inclusive num
  crash entre escrever a conclusão e `activity conclude`).
- Teste: `test_daemon_refuses_to_start_when_conclusion_present`.

## #3 (BLOQUEADOR) — TOCTOU entre guard e lançamento
- Em `loop.py` o guard foi movido para IMEDIATAMENTE ANTES de `run_turn` (após o
  preparo do prompt), encurtando a janela guard→launch ao mínimo. Um desarme
  concluído nessa janela é observado; o turno EM VOO segue sendo responsabilidade
  da via de abort (contrato declarado). Teste:
  `test_daemon_guard_disarm_stops_between_turns` (desarme tardio → DISARMED).

## #4 (ALTO) — `arm()` não validava a config; falha tardia deixava token armado
- `_validate_arm_config` valida na hora do arm: `prompt_template` é arquivo;
  `declared_in` é arquivo SOB o diretório canônico do plano E com ≥1 STEP, cada um
  com gate; `artifact_dir` sob `.regent`; `envelope` não-vazio. (Fecha o caso
  "template inexistente arma com sucesso" e "declared_in vazio → STEPS_COMPLETE".)
- `run_daemon` agora captura QUALQUER exceção de `run_loop` (não só `LoopError`) →
  DESARMA e reporta `FAILED`.
- Testes: `test_arm_rejects_missing_template`,
  `test_arm_rejects_declared_in_outside_plan_dir`, `test_arm_rejects_plan_without_steps`,
  `test_daemon_disarms_on_unexpected_failure`.

## #5 (MÉDIO) — exit codes e streaming divergiam do contrato
- `_DAEMON_EXIT`: `SIGNALLED`→2 (parada do dono), `LOOP_MISCONFIGURED`→3 (falha),
  `FAILED`→3.
- A CLI `daemon run` agora emite **uma linha JSON por transição** (via `on_state`)
  e o objeto-resumo final como ÚLTIMA linha. Teste:
  `test_daemon_cli_streams_transitions`.

## Fora de escopo (não-bloqueio, confirmado pelo revisor)
Fase 5 (daemon em background, ativação automática, notificações). O revisor não
conseguiu rodar os testes (sandbox read-only sem tmp gravável) — limitação do
ambiente do consult, não do código.

## Gates
Suíte completa 247 OK; `bash scripts/gate-package.sh` → 0.8.0 + twine --strict OK.
