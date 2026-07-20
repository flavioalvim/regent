# PLAN-001 (v3) — Camada de protocolo do regent (control CAS + turn lock + stop-request)

*v2 após ADVISOR-REVIEW-1 (7 objeções incorporadas — ver CLAUDE-REBUTTAL.md). v3 incorpora
VERBATIM os 3 residuais do ADVISOR-REVIEW-2: recuperação de micro-mutex órfão, fencing do
stop-request por token de turno, e testes nomeados de takeover/ABA/crash-recovery/
durabilidade do audit.*

## Objetivo

Implementar `regent.protocol` — fundação transacional do produto: estado de controle com
escrita compare-and-swap REAL, lock de turno do executor e representação durável de
stop-request, conforme REQ-003/004. **Reimplementação das invariantes provadas** no ArtNFT
(`docs/brainstorm-mvp/scripts/`: mutex por `mkdir()`, publicação atômica tempfile+replace,
versionamento monotônico), com origem citada por módulo — não é port 1:1 (o modelo de
atores mudou: executor único, REQ-003 §4).

## Escopo

**Dentro:** `src/regent/protocol/{control,lock,stop,audit}.py` + façade com exports
nominais; testes dirigidos (nomeados por etapa) portando casos das suítes IMP-000; P-01
como 1ª classe (redefinido corretamente: acquire não muta estado versionado).

**Fora (diferido explicitamente):** daemon/condução (supervisor_*), confinamento e **P-03**
(allowlist de paths — pertence ao confinamento), adapter de consulta ao advisor, religação
das skills v0 ao control.json, sequência canônica completa de parada / `--abort` /
`CANCELLED` (exigem condução), semeadura do control.json pelo `init`, publicação PyPI.

## Schema v1 do `control.json` (normativo)

```
{
  "schema_version": 1,
  "version": <int monotônico — token do CAS>,
  "updated_at": "<ISO-8601 UTC>",
  "activity": null | {
    "type": "brainstorm" | "plan" | "build",
    "id": "<ROUND-NNN | PLAN-NNN>",
    "epoch": <int, incrementa a cada (re)início de atividade — guarda ABA>,
    "state": "ACTIVE" | "SUSPENDED",
    "turn": null | { "owner": "executor", "token": "<uuid4>", "acquired_at": "<ISO>" },
    "suspension": null | { "previous_state": str, "checkpoint": str, "owning_turn": str,
                           "in_flight": str|null, "reason": str, "at": "<ISO>" }
  },
  "stop_request": null | { "id": "<uuid4>", "activity_id": str, "activity_epoch": int,
                           "turn_token": str|null, "requested_at": "<ISO>" },
  // turn_token=null → canal do mediador (vale para a atividade, independe do turno);
  // turn_token≠null → OBRIGATORIAMENTE igual ao turn.token corrente, senão OBSOLETO
  // (takeover rotaciona o token ⇒ requests do turno anterior expiram — fencing ABA),
  "last_concluded": null | { "type": str, "id": str, "status": str, "at": "<ISO>" }
}
```

Invariantes: `state=ACTIVE ⇒ turn≠null ∧ suspension=null`; `state=SUSPENDED ⇒ turn=null ∧
suspension≠null`; `activity=null` = inicializado e ocioso; `stop_request` é OBSOLETO
(descarte COM auditoria) sse: `activity_id`/`activity_epoch` divergem dos correntes, OU
`turn_token≠null` e diverge do `turn.token` corrente.
Validação estrita default-deny: schema desconhecido/corrompido/invariante violada = erro
sem tocar o arquivo.

## Etapas

### STEP-01 — Control store transacional + auditoria (`protocol/control.py`, `protocol/audit.py`)

Mutações do control sob **micro-mutex exclusivo de mutação** (`mkdir`-style em
`<control>.lock.d`, distinto do turn lock; NUNCA segurado ao adquirir o turn lock — ordem
documentada no módulo): seção crítica = load → validar versão esperada → publicar.
Publicação: tempfile no mesmo diretório → `flush`+`fsync` do arquivo → `os.replace` →
`fsync` do diretório (atomicidade ≠ durabilidade, ambas cobertas); temporários órfãos
limpos na entrada da seção crítica. **Recuperação do micro-mutex:** o mutex dir contém
`meta.json` (pid, `at`); mutex órfão (idade > threshold de mutação, ~60s, ou processo
morto) é removido À FORÇA com registro de auditoria, e a mutação seguinte prossegue.
`audit.py`: appender JSONL para **`.regent/protocol/audit.jsonl`** (evidência
compartilhável, REQ-001 §3) — cada append é `O_APPEND` de linha única + `fsync`
(durabilidade), seguro sob concorrência.
- **Critérios:** dois escritores concorrentes → exatamente um vence, o outro recebe
  conflito; stop-request concorrente com update do executor não perde campos; corrupção
  rejeitada sem tocar o arquivo; morte antes do replace deixa o control íntegro; crash do
  detentor do micro-mutex NÃO bloqueia mutações futuras; append do audit durável e sem
  perda sob concorrência.
- **Testes dirigidos:** `test_cas_two_processes_one_wins` (multiprocesso com barreira),
  `test_concurrent_stop_and_executor_update_no_field_loss`,
  `test_corrupt_control_rejected_untouched`, `test_kill_before_replace_leaves_control_intact`,
  `test_orphan_tempfiles_cleaned`, `test_mutation_mutex_stale_recovered_after_crash`,
  `test_mutation_recovers_and_writes_after_crash`,
  `test_audit_append_fsynced_and_concurrent`.
- **Gate:** `PYTHONPATH=src python3 -m unittest discover -s tests`

### STEP-02 — Turn lock do executor (`protocol/lock.py`)

Reimplementação da INVARIANTE do turn_lock.py (primitiva `mkdir()` mantida) no diretório
XDG (estado local descartável): dentro do lock dir, arquivo `owner.json` com token uuid4,
`acquired_at`, heartbeat. Contratos: release/heartbeat SÓ com o token corrente; takeover SÓ
de lock suspeito (idade > threshold OU sem owner.json após grace — cobre crash entre mkdir
e gravação do owner), sempre explícito e auditado em `.regent/protocol/audit.jsonl`
(`{actor, reason, previous_owner, age_seconds, at}`); fencing ABA: o token do turno vigente
é gravado no `control.activity.turn.token` — operações de control com token divergente
falham. **P-01 (correto):** `acquire` bem-sucedido altera SOMENTE o XDG — `.regent/` e o
git ficam byte-idênticos.
- **Critérios:** contenção básica; release com token errado falha; takeover de lock fresco
  recusado; takeover de suspeito auditado; lock sem owner vira suspeito após grace; P-01.
- **Testes dirigidos:** `test_second_acquire_fails`, `test_release_wrong_token_fails`,
  `test_takeover_fresh_lock_refused`, `test_takeover_stale_lock_audited`,
  `test_ownerless_lock_suspect_after_grace`, `test_acquire_leaves_regent_and_git_untouched`,
  `test_takeover_race_single_winner` (dois candidatos ao takeover, um vence),
  `test_control_op_with_divergent_token_rejected_after_takeover` (fencing ABA fim-a-fim).
- **Gate:** `PYTHONPATH=src python3 -m unittest discover -s tests`

### STEP-03 — Stop-request: representação e transições (`protocol/stop.py`)

ESCOPO REDUZIDO (a sequência canônica completa é da fase de condução): gravar stop-request
via CAS vinculado a `{activity_id, activity_epoch, turn_token}`; leitura valida o vínculo e
descarta obsoletos COM auditoria; helper de transição `ACTIVE→SUSPENDED` exigindo o payload
completo do REQ-004 §5; cada transição é idempotente (reaplicar = no-op detectado).
- **Critérios:** request válido honrável (canal do mediador com `turn_token=null` incluso);
  obsoleto (id/epoch divergente OU token de turno divergente pós-takeover) descartado e
  auditado; transição SUSPENDED valida payload; reaplicação idempotente.
- **Testes dirigidos:** `test_stop_request_linked_and_readable`,
  `test_stale_stop_request_discarded_with_audit`,
  `test_stop_request_old_turn_token_stale_after_takeover`,
  `test_mediator_stop_request_null_token_valid`, `test_suspend_requires_full_payload`,
  `test_transitions_idempotent`.
- **Gate:** `PYTHONPATH=src python3 -m unittest discover -s tests`

### STEP-04 — Façade nominal, gate de pacote e consolidação

`protocol/__init__.py` exporta NOMINALMENTE: `ControlStore`, `ControlSchemaError`,
`VersionConflict`, `TurnLock`, `LockHeld`, `NotLockOwner`, `StaleLock`, `record_stop_request`,
`read_valid_stop_request`, `suspend_activity`, `AuditLog`. Docstrings citam módulo de origem
no ArtNFT. README ganha seção "Protocol layer". Versão **0.3.0**. Gate de pacote vira
script versionado `scripts/gate-package.sh` (`set -euo pipefail`; cria/reusa `.venv-dev`
com `build`+`twine`; roda suíte completa, `python -m build` e `twine check dist/*`
preservando exit codes).
- **Critérios:** cada símbolo listado importável; suíte completa verde; build+check verdes
  via script fail-closed.
- **Testes dirigidos:** `test_facade_exports_all_symbols`.
- **Gate:** `bash scripts/gate-package.sh`

## Riscos (dominantes primeiro)

1. **Lost update** → micro-mutex de mutação + teste multiprocesso (STEP-01).
2. **Crash consistency** → fsync arquivo+diretório, fault injection, limpeza de órfãos.
3. **ABA/fencing** → epoch da atividade + token do turno espelhado no control.
4. **Relógio/heartbeat** → thresholds conservadores; idades por diferença de timestamps
   UTC gravados (não relógio monotônico entre processos — limitação documentada).
5. **Identidade do projeto no XDG** → diretório derivado do path canônico do repo (hash);
   colisão por rename de path documentada como limitação v0.
6. **Dois locks (mutação × turno)** → ordem de aquisição documentada e testada: micro-mutex
   nunca envolve o turn lock.
7. **Camada dormente até a condução** → façade estável + escopo explícito.

## Idioma

Código/artefatos de sistema em inglês (REQ-002 §1); este PLAN.md em PT (mediador PT-BR).
