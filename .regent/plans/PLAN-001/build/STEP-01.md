# PLAN-001 / STEP-01 — Control store transacional + auditoria

step_base_sha: (HEAD no início da etapa = commit do baseline; ver trailer Regent-Step no git log)
files_touched:
  - src/regent/protocol/__init__.py (novo, façade preenchida no STEP-04)
  - src/regent/protocol/audit.py (novo)
  - src/regent/protocol/control.py (novo)
  - tests/test_control.py (novo, 9 testes dirigidos)

## O que foi implementado

- `AuditLog`: JSONL append-only em `.regent/protocol/audit.jsonl`; cada append é linha
  única `O_APPEND` + `fsync` (durável, seguro sob concorrência).
- `ControlStore`: `seed`/`load` (validação estrita default-deny do schema v1 com
  invariantes ACTIVE/SUSPENDED), `cas_write` (CAS REAL: seção crítica sob micro-mutex
  mkdir + `meta.json` {pid, at}; conflito de versão detectado DENTRO da seção),
  `mutate` (retry-on-conflict), fencing opcional por `turn_token` (`assert_turn_token`).
- Publicação atômica E durável: tempfile no mesmo dir → fsync(arquivo) → `os.replace` →
  fsync(diretório); órfãos `.control-tmp-*` limpos na entrada da seção crítica.
- Recuperação de micro-mutex: dir órfão (meta velha > timeout, pid morto, ou sem meta além
  do timeout) removido à força com registro `mutation_mutex_recovered` no audit.
- Test hook documentado `_CRASH_BEFORE_REPLACE` (os._exit antes do replace) para os testes
  de crash consistency.

## Gate (PYTHONPATH=src python3 -m unittest discover -s tests)

```
Ran 17 tests in 0.511s
OK
```

Inclui os 8 dirigidos nomeados no plano (test_cas_two_processes_one_wins,
test_concurrent_stop_and_executor_update_no_field_loss,
test_corrupt_control_rejected_untouched, test_kill_before_replace_leaves_control_intact,
test_orphan_tempfiles_cleaned, test_mutation_mutex_stale_recovered_after_crash,
test_mutation_recovers_and_writes_after_crash, test_audit_append_fsynced_and_concurrent)
+ test_invariant_violation_rejected (extra) + os 8 pré-existentes de init/doctor.
