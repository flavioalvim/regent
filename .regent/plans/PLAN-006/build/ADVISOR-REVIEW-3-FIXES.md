# PLAN-006 — respostas ao ADVISOR-REVIEW-3 (REPROVADO)

O revisor confirmou #2/#3/#4 (rodada 2) FECHADOS. Restaram 2 achados, ambos sobre
o daemon IGNORAR o retorno (agora verídico) de `disarm()`. Corrigidos.

## #1 (BLOQUEADOR) — `run_daemon` ignorava falhas de desarme em TODO caminho terminal
- Novo `_confirm_disarmed(service, arm_id)`: desarma e CONFIRMA a remoção,
  re-tentando falhas transitórias (3×). Retorna False só se uma falha REAL de
  remoção persistir. Razões benignas ("no arm token", "arm_id mismatch (rearmed)")
  contam como já-desarmado.
- Todos os caminhos terminais (SIGNALLED, STOPPED, LoopError, FAILED, terminal
  normal) agora passam por `finish()`, que usa `_confirm_disarmed`; se o token não
  puder ser removido, o estado vira **`DISARM_FAILED`** (exit 3, `ok=false`) — o
  daemon NUNCA reporta terminal limpo com o token ainda armado, então uma execução
  posterior não re-dirige silenciosamente.
- `DISARM_FAILED` adicionado a `_DAEMON_EXIT` (→3). Teste:
  `test_daemon_reports_disarm_failed_when_removal_persists_failing`.

## #2 (ALTO) — descarte auditava "discarded" ANTES de remover
- Em `read_arm`, o `_unlink_durable` é tentado PRIMEIRO; o `audit.append(
  arm_token_discarded)` só ocorre no ramo `else` (remoção bem-sucedida). Se a
  remoção falhar, o token é mantido e o audit NÃO alega descarte. Teste:
  `test_read_arm_discard_no_audit_when_removal_fails`.

## Confirmados FECHADOS pelo revisor (rodada 2)
`_unlink_durable` (FileNotFoundError=sucesso, resto propaga); guard revalida
APPROVED (leitura pura, custo irrelevante); config canônica absoluta preserva o
vínculo declared_in↔plan_dir e independe do CWD; `emit` captura exceção de
`on_state`.

## Gates
Suíte completa 253 OK; `bash scripts/gate-package.sh` → 0.8.0 + twine --strict OK.
