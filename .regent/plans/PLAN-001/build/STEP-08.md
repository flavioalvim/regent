# PLAN-001 / STEP-08 — Correções da quarta revisão (primitiva flock; fim da família TOCTOU)

step_base_sha: 5ca6e8e (commit do STEP-07)
files_touched:
  - src/regent/protocol/control.py (_MutationMutex → _FlockMutex)
  - src/regent/protocol/lock.py (lifecycle mutex via flock; acquire recusa dir existente;
    remoção estrita antes da rotação do fence)
  - tests/test_control.py, tests/test_lock.py

## Mapa achado→correção (4ª revisão)

- **BLOQUEANTE (recuperação concorrente do mutex-diretório ainda TOCTOU):** a causa raiz
  era a PRIMITIVA — mutex por diretório exige julgar/evitar órfãos, e o julgamento é
  inerentemente corrível. Substituída por **flock do kernel em arquivo de lock dedicado**
  (produto v0 é single-host por REQ-003): aquisição atômica no kernel; detentor morto é
  liberado AUTOMATICAMENTE; **não existe mais código de staleness/evicção/recuperação —
  logo não existe o que correr**. O arquivo de lock nunca é unlinked (evita dois flocks
  em inodes distintos — documentado). `verify_still_held` removido: um flock não pode ser
  "perdido" enquanto o fd está aberto. Vale para o mutex de mutação do control E para o
  mutex de ciclo de vida do turn lock.
- **ALTA (rename sobre dir vazio absorve lock ownerless):** `_acquire_locked` agora
  RECUSA qualquer dir existente (ownerless incluso) ANTES do rename — evicção é trabalho
  do takeover (com grace e auditoria), nunca efeito colateral silencioso. Seguro porque
  todo o ciclo de vida é serializado pelo flock. Teste novo:
  `test_acquire_refuses_ownerless_dir`.
- **ALTA (falha de remoção podia rotacionar o fence com o lock antigo vivo):**
  `_remove_tree_strict` (levanta OSError e verifica pós-condição) chamado ANTES da
  rotação — se o lock antigo não pôde ser removido, o takeover aborta SEM tocar o
  control.
- Testes de evicção do mutex-diretório substituídos pelos equivalentes flock:
  `test_mutex_auto_released_after_holder_death` (crash segurando o flock não bloqueia
  ninguém) e `test_mutex_alive_holder_blocks_until_timeout` (detentor vivo bloqueia até
  MutationMutexBusy, nada é publicado).

## Gates

```
PYTHONPATH=src python3 -m unittest discover -s tests → Ran 38 tests — OK (3 execuções)
bash scripts/gate-package.sh → build 0.3.0 + twine check PASSED + gate-package: OK
```
