# PLAN-001 / STEP-05 — Correções da revisão final do advisor (REPROVADO → fix)

step_base_sha: fa8891c (commit do registro do ADVISOR-REVIEW)
files_touched:
  - src/regent/protocol/control.py (reescrito)
  - src/regent/protocol/lock.py (reescrito)
  - src/regent/protocol/audit.py (durabilidade)
  - src/regent/protocol/stop.py (no-op verdadeiro + token no re-apply + audit-intent)
  - src/regent/protocol/__init__.py (docstring: classe única + desvio declarado)
  - tests/test_control.py, tests/test_lock.py, tests/test_stop.py (novos dirigidos)
  - .regent/plans/PLAN-001/build/STEP-0{1..4}.md (step_base_sha retroativos)

## Mapa achado→correção

- **BLOQUEANTE 1 (dois vencedores de CAS via recuperação do micro-mutex):** recuperação
  agora SÓ evita detentor com **pid morto** (ou dir sem meta além do timeout) — detentor
  vivo NUNCA é evitado, por mais lento (quem espera recebe `MutationMutexBusy`); meta.json
  ganha **token de instância**; a evicção é reivindicada por **rename atômico** com
  verificação do token julgado (dois recuperadores → um vence; instância fresca nunca é
  evitada); o detentor **re-verifica a posse** (`verify_still_held`) imediatamente antes de
  publicar. Teste novo: `test_mutation_mutex_alive_holder_never_evicted`.
- **BLOQUEANTE 2 (release/heartbeat destroem/usurpam lock pós-takeover):** `heartbeat` é
  **instance-bound via dir-fd** (read-verify-write pelo fd do diretório: se o takeover
  renomear a instância no meio, a escrita cai no dir renomeado/descartado — usurpação
  impossível); `release` **reivindica por rename**, verifica o token DENTRO da instância
  reivindicada e só então destrói; mismatch → restaura (falha de restauração auditada).
  Testes novos: `test_heartbeat_old_token_after_takeover_does_not_usurp`,
  `test_release_old_token_after_takeover_preserves_new_lock`.
- **ALTA (fencing não fim-a-fim):** `takeover(..., control_store=)` **rotaciona o token no
  control na mesma operação**; teste fim-a-fim refeito: control PRÉ-EXISTENTE com token
  antigo → takeover → token rotacionado → op do detentor anterior rejeitada.
- **ALTA (schema não estrito):** validação por **conjuntos exatos de chaves** em todos os
  níveis (extras/faltantes = erro), tipos, timestamps ISO parseáveis, `turn.owner ==
  "executor"`, `stop_request` DEVE conter a chave `turn_token`; **monotonicidade de epoch**
  aplicada no cas_write.
- **ALTA (janelas de crash sem auditoria):** takeover, evicção de mutex e descarte de
  stop-request auditam a **INTENÇÃO ANTES de agir** (crash nunca deixa ação concluída sem
  registro; semântica documentada: o registro é de intenção).
- **MÉDIA (durabilidade do audit):** loop sobre `os.write` parcial + `fsync` do arquivo E
  do diretório a cada append.
- **MÉDIA (idempotência não era no-op):** re-request e re-suspend equivalentes retornam
  SEM mutação (versão não incrementa — asserts novos); re-apply de suspensão exige o
  token do turno suspensor.
- **MÉDIA (façade/exceção):** `NotLockOwner` é CLASSE ÚNICA (lock importa do control);
  `MutationMutexBusy` mantido na façade como **desvio declarado** da lista nominal
  (chamadores precisam capturá-lo).
- **BAIXA (evidência):** `step_base_sha` preenchido nos STEP-01..04; teste renomeado para
  o nome exato do plano (`test_suspend_requires_full_payload`).

## Gates

```
PYTHONPATH=src python3 -m unittest discover -s tests → Ran 36 tests — OK (3 execuções)
bash scripts/gate-package.sh → build 0.3.0 + twine check PASSED + gate-package: OK
```
