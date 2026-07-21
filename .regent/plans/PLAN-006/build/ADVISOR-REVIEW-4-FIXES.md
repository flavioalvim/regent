# PLAN-006 — respostas ao ADVISOR-REVIEW-4 (REPROVADO)

Um único bloqueador remanescente, sutil: ordenação de durabilidade.

## #1 (BLOQUEADOR) — falha de fsync do dir mascarada pela retentativa
Cenário: `unlink()` OK mas o `fsync` do diretório FALHA. O arquivo já saiu do
namespace, então a 2ª tentativa vê "no arm token" (benigno) e `_confirm_disarmed`
retorna True — mas a remoção NUNCA foi durável (pode ressurgir após crash).

Correção:
- `_unlink_durable` agora executa o `fsync` do diretório (barreira de
  durabilidade) MESMO quando o arquivo já sumiu (`FileNotFoundError` = pass, mas
  fsync mesmo assim). Remoção só é "feita" quando o fsync SUCEDE.
- O caminho "no arm token" de `disarm` agora chama `_unlink_durable` (roda a
  barreira) antes de declarar o token ausente; se o fsync falhar, retorna
  `{"disarmed": false, "reason": "fsync failed"}` — NÃO-benigno, então
  `_confirm_disarmed` re-tenta e, persistindo, o daemon reporta `DISARM_FAILED`.
- Assim, uma remoção só é confirmada após um `fsync` de diretório bem-sucedido:
  a ausência é duravelmente confirmada, fechando a janela de ressurreição.

Testes:
- `test_daemon_disarm_failed_when_dir_fsync_persistently_fails` (fsync sempre
  falha → DISARM_FAILED);
- `test_daemon_recovers_when_dir_fsync_succeeds_on_retry` (fsync falha 1×, sucede
  na retentativa → STEPS_COMPLETE, token duravelmente removido).

## Confirmados FECHADOS pelo revisor (rodada 3)
Todos os caminhos terminais via `finish()`; DISARM_FAILED/exit 3 quando o arquivo
persiste; rearm legítimo cercado por arm_id; retentativas limitadas (sem laço
preso); audit de descarte só após remoção.

## Gates
Suíte completa 255 OK; `bash scripts/gate-package.sh` → 0.8.0 + twine --strict OK.
