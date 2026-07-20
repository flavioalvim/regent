# PLAN-001 / STEP-06 — Correções da segunda revisão final (janelas de corrida residuais)

step_base_sha: d62f0e3 (commit do registro do ADVISOR-REVIEW-2)
files_touched:
  - src/regent/protocol/control.py (verify acoplado ao publish; __exit__ condicional;
    re-check pré-rename na evicção; epoch com piso via last_concluded; tipos estritos;
    mutate com no-op verdadeiro)
  - src/regent/protocol/lock.py (release verify-antes-de-rename; takeover rotaciona o
    control ANTES de criar o lock novo; rotação skipped auditada; free-path fence)
  - src/regent/protocol/audit.py (flock exclusivo no append)
  - tests/test_control.py, tests/test_lock.py, tests/test_stop.py

## Mapa achado→correção (2ª revisão)

- **BLOQUEANTE 1 (ABA do recuperador + verify desacoplado + __exit__ incondicional):**
  (a) `verify_still_held` movido para DENTRO de `_publish`, imediatamente antes do
  `os.replace` — detentor deslocado aborta em vez de duplo-publicar; (b) `__exit__` do
  mutex remove SÓ se o meta token é o dele (nunca apaga instância alheia); (c) o
  recuperador RE-LÊ o meta canônico imediatamente antes do rename e desiste se o token
  não é mais o julgado (instância fresca nunca é reivindicada). Combinado com "vivo nunca
  é evitado" (STEP-05), o cenário de dois vencedores exige evicção de detentor vivo — que
  não existe mais no código.
- **BLOQUEANTE 2 (release/takeover abrem o path):** `release` verifica o token ANTES de
  qualquer rename (detentor obsoleto recebe NotLockOwner sem deslocar nada, nem
  transitoriamente); `takeover` agora **rotaciona o token no control ANTES de criar o
  lock novo** (fence-before-handover): crash no meio deixa o control cercado a um token
  sem lock — seguro (sem usurpação; próximo takeover vê free e re-cerca); se outro
  candidato adquirir o path na janela, ele NÃO passa no fencing do control e a perda é
  sinalizada. Teste de corrida agora afirma que o token vencedor É o dono final.
- **ALTA (janela/estado parcial do fencing):** ordem invertida resolve a janela (control
  cercado antes do handover); rotação com token divergente é AUDITADA
  (`turn_token_rotation_skipped`), nunca silenciosa.
- **ALTA (epoch pelo ciclo ocioso):** `last_concluded` ganha `epoch` (schema); o piso
  sobrevive a `activity=null` e (re)início do ocioso exige epoch ESTRITAMENTE maior.
  Teste `test_epoch_monotonic_through_idle_cycle` (10 → null → 1 rejeitado; 11 aceito).
- **MÉDIA (interleaving de write parcial):** append serializado por `flock` exclusivo
  (O_APPEND sozinho não protege fragmentos parciais).
- **MÉDIA (no-op em corrida):** `mutate()` compara o corpo devolvido pelo callback com o
  corrente e NÃO publica quando semanticamente inalterado — no-op verdadeiro também no
  caminho de corrida.
- **MÉDIA (tipos estritos):** bool rejeitado como int; timestamps exigem timezone;
  tokens/ids uuid4 validados como 32-hex (turn.token, suspension.owning_turn,
  stop_request.id, stop_request.turn_token).

## Gates

```
PYTHONPATH=src python3 -m unittest discover -s tests → Ran 37 tests — OK (3 execuções)
bash scripts/gate-package.sh → build 0.3.0 + twine check PASSED + gate-package: OK
```
