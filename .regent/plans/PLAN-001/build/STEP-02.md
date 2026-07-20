# PLAN-001 / STEP-02 — Turn lock do executor

files_touched:
  - src/regent/protocol/lock.py (novo)
  - tests/test_lock.py (novo, 9 testes dirigidos)

## O que foi implementado

- `TurnLock`: primitiva `mkdir()` provada (invariante do turn_lock.py do ArtNFT,
  reimplementada — não port) no diretório de estado LOCAL; `owner.json` com token uuid4,
  `acquired_at`, `heartbeat_at`.
- Contratos: `heartbeat`/`release` exigem o token corrente (`NotLockOwner`); lock sumido =
  `StaleLock`; `status()` → free/held/suspect (heartbeat velho > stale_after, ou sem owner
  além do grace — cobre o crash entre mkdir e gravação do owner).
- `takeover(actor, reason)`: só de lock suspeito; rename atômico do dir para o lado (um
  candidato vence) + **guarda ABA**: se a instância renomeada não é a mesma julgada
  suspeita (token divergente), restaura e perde. Auditoria completa em
  `.regent/protocol/audit.jsonl` (actor, reason, previous_owner, age_seconds, new_token).
- Fencing fim-a-fim: token vigente espelhado em `control.activity.turn.token`;
  `cas_write(..., turn_token=)` rejeita o detentor anterior.
- P-01: acquire toca SOMENTE o state dir; teste prova `.regent/` e git byte-idênticos.

## Vermelho→verde durante a etapa (registro fiel)

O gate pegou um bug real na 1ª implementação: `test_takeover_race_single_winner` → ambos os
candidatos venciam (['won','won']) porque o 2º renomeava o lock NOVO do vencedor (com
stale_after=0 ele também parecia suspeito) — exatamente a corrida ABA apontada no
ADVISOR-REVIEW-2. Corrigido com a guarda de instância (comparação do token julgado);
gate re-rodado 3× verde.

## Gate (PYTHONPATH=src python3 -m unittest discover -s tests)

```
Ran 26 tests — OK (3 execuções consecutivas)
```
