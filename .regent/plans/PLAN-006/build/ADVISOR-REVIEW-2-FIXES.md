# PLAN-006 — respostas ao ADVISOR-REVIEW-2 (REPROVADO)

O revisor confirmou #2/#3/#5 (rodada 1) FECHADOS; #1 e #4 parciais + 2 novos altos.
Todos reais. Incorporados, um teste dirigido por achado.

## #1 (BLOQUEADOR) — remoção não comprovadamente durável / sucesso falso
- `_unlink_durable` agora: `FileNotFoundError` = sucesso (já removido); QUALQUER
  outra falha de `unlink`/`fsync` PROPAGA (não é mais engolida).
- `disarm` captura `OSError` da remoção e retorna `{"disarmed": false,
  "reason": "unlink failed"}` — nunca reporta remoção que não ocorreu.
- O descarte em `read_arm` mantém o token se a remoção falhar (re-avaliado no
  próximo ciclo) e nunca alega sucesso.
- Testes: `test_disarm_reports_false_when_unlink_fails`,
  `test_read_arm_discard_cas_keeps_rearm_under_race` (agora simula o interleaving
  A→B real via injeção em `_raw_arm`: A lê snapshot OBSOLETO, disco tem B; sob o
  lock re-lê B, arm_id difere → NÃO apaga B).

## #2 (ALTO, novo) — guard tardio não revalidava APPROVED
- O `guard` do daemon agora retorna False se `_approval_status(root, plan) !=
  APPROVED` — fecha a janela entre a checagem de aprovação no topo do `run_loop` e
  o lançamento. Teste: `test_daemon_guard_revalidates_approval` (injeta
  APPROVED→CANCELLED entre as duas leituras → DISARMED).

## #3 (ALTO, novo) — config não canonizada persistida
- `_validate_arm_config` agora RETORNA uma cópia CANÔNICA com todos os paths
  resolvidos para ABSOLUTOS (prompt_template, declared_in, artifact_dir, envelope,
  gate_envelope); `arm` grava essa cópia no token. O daemon comporta-se igual de
  qualquer CWD. Teste: `test_arm_persists_canonical_absolute_paths`.

## #4 (ALTO, novo) — exceção no callback de streaming deixava token armado
- `emit()` agora captura QUALQUER exceção do `on_state` (ex.: `BrokenPipeError`) e
  seta o flag de parada — o guard interrompe o loop e o caminho terminal desarma
  limpo; a exceção nunca escapa. Teste: `test_daemon_streaming_exception_disarms`.

## Confirmados FECHADOS pelo revisor (rodada 1)
#2 (CONCLUSION.md no guard), #3 (guard imediatamente antes de run_turn), #4
(validação inicial + FAILED em exceção), #5 (exit codes + streaming),
ALREADY_ARMED antes da validação sob o lock, flock/CAS sem reentrância/deadlock.

## Gates
Suíte completa 251 OK; `bash scripts/gate-package.sh` → 0.8.0 + twine --strict OK.
