# PLAN-001 / STEP-04 — Façade nominal, gate de pacote e consolidação

step_base_sha: 5b5eb3e (commit do STEP-03)
files_touched:
  - src/regent/protocol/__init__.py (façade nominal com __all__)
  - tests/test_protocol_facade.py (novo)
  - scripts/gate-package.sh (novo, fail-closed: set -euo pipefail)
  - src/regent/__init__.py + pyproject.toml (versão 0.3.0)
  - README.md (seção "Protocol layer")
  - .gitignore (.venv-dev/)

## O que foi implementado

- Façade `regent.protocol` exportando NOMINALMENTE os 12 símbolos do plano:
  AuditLog, ControlSchemaError, ControlStore, LockHeld, MutationMutexBusy, NotLockOwner,
  StaleLock, TurnLock, VersionConflict, read_valid_stop_request, record_stop_request,
  suspend_activity — com `test_facade_exports_all_symbols` conferindo `__all__` 1:1.
- `scripts/gate-package.sh`: suíte completa + `.venv-dev` dedicado (build+twine) +
  `python -m build` + `twine check --strict`, exit codes preservados (sem `| tail`).
- README documenta a camada e sua dormência declarada até a fase de condução.

## Gate (`bash scripts/gate-package.sh`)

```
Ran 33 tests — OK
Successfully built regent_cli-0.3.0.tar.gz and regent_cli-0.3.0-py3-none-any.whl
Checking dist/regent_cli-0.3.0-py3-none-any.whl: PASSED
Checking dist/regent_cli-0.3.0.tar.gz: PASSED
gate-package: OK
```
