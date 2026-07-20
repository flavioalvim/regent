# PLAN-001 / STEP-07 — Correções da terceira revisão (serialização do ciclo de vida)

step_base_sha: f69f245 (commit do STEP-06)
files_touched:
  - src/regent/protocol/lock.py (reescrito: ciclo de vida serializado)
  - src/regent/protocol/control.py (mutex por rename de staging pré-populado; piso de
    epoch não-apagável; schema_version rejeita bool)
  - tests/test_lock.py (corrida de takeover redesenhada p/ semântica serializada)
  - .regent/plans/PLAN-001/PLAN.md (emenda declarada: last_concluded.epoch no schema)

## Causa raiz fechada (em vez de deslocar janelas)

- **BLOQUEANTE 1 e 2 (TOCTOU do release; fence não serializado entre takeovers):** TODAS
  as operações de ciclo de vida do turn lock (acquire, heartbeat, release, takeover,
  status) agora rodam sob um **mutex de ciclo de vida dedicado** — o MESMO primitivo
  endurecido do mutex de mutação do control (token de instância, evicção só com pid
  morto, recuperação auditada, remoção condicional). Serializado, cada
  read-judge-act é atômico em relação aos demais: sem verify-então-rename, sem path
  transitoriamente livre para um terceiro acquire, sem rotação dupla do fence (o cenário
  A/B do achado 2 é impossível: B espera o mutex e vê o lock fresco de A como held).
  Rotação divergente agora **ABORTA o takeover** (auditada) — dono físico e token
  cercado nunca se separam. Ordem de aquisição documentada e livre de deadlock:
  lifecycle → control-mutation, nunca o inverso.
- **Ressalva da 3ª revisão (janela mkdir→meta/owner) TAMBÉM fechada:** aquisição do
  mutex E do lock viraram **rename atômico de diretório pré-populado** (meta/owner
  escritos ANTES da instância ficar visível) — "ownerless" só pode ser artefato legado.
- **ALTA (piso de epoch apagável na conclusão):** o PISO (max de activity.epoch e
  last_concluded.epoch) **nunca pode regredir** — concluir epoch 10 gravando
  last_concluded.epoch=1 ou null é rejeitado; sequência 10→idle(1)→2 do advisor agora
  impossível.
- **MÉDIA:** `schema_version=True` rejeitado (`_require_int` rejeita bool); schema
  normativo do PLAN.md emendado com `last_concluded.epoch` (emenda declarada).
- Teste de corrida redesenhado para a semântica serializada: seed com heartbeat antigo,
  candidatos com threshold realista → exatamente um vence E é o dono final.

## Gates

```
PYTHONPATH=src python3 -m unittest discover -s tests → Ran 37 tests — OK (3 execuções)
bash scripts/gate-package.sh → build 0.3.0 + twine check PASSED + gate-package: OK
```
