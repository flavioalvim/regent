# PLAN-005 / STEP-01 — Runner cancelável + abort-request + suspensão via app layer

step_base_sha: 38a077d (baseline)
files_touched:
  - src/regent/conduction/process.py (RunResult.aborted; run(cancel=) cancelável e
    sem deadlock — thread leitora drena stdout; cancel > timeout; killpg + reap)
  - src/regent/conduction/abort.py (novo — abort-request vinculado O_EXCL, nonce de turno,
    claim único, descarte de stale auditado)
  - src/regent/conduction/turn.py (attempt sufixa artefatos; keepalive checa abort ~1s e
    seta cancel; ABORTED suspende; STOPPED e ABORTED suspendem VIA APP LAYER — libera o
    turn lock, EMENDA declarada ao PLAN-004)
  - tests/test_abort.py (novo, 10) + fake-runners com cancel=None

## O que foi implementado

- Runner cancelável por poll com thread leitora (sem deadlock em saída grande — testado
  500 KiB); `aborted` distinto de `timed_out`; cancel tem precedência; grupo morto+reap.
- abort-request no XDG vinculado a {activity_id, epoch, turn_token}, criado O_EXCL (um
  pendente), honrado só com nonce de turno em voo E vínculo casado, claim único
  (rename→.claimed), stale descartado+auditado.
- keepalive checa o abort a cada ~1s e seta o cancel; heartbeat a cada ~60s.
- **Correção do gap do PLAN-004:** suspensão (STOPPED e ABORTED) roteada por
  `service._suspend_locked` (app layer), que LIBERA o turn lock — regressões provam lock
  free após stop e após abort.

## Gate (PYTHONPATH=src python3 -m unittest discover -s tests)

Ran 193 tests — OK (3 execuções)
