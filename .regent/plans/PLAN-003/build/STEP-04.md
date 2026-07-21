# PLAN-003 / STEP-04 — Consolidação 0.5.0

step_base_sha: 686a27e (commit do STEP-03)
files_touched: pyproject.toml + src/regent/__init__.py (0.5.0); README.md (fase 1 da
condução); tests/test_activity_cli.py (test_cli_version_reports_050)

## E2e REAL registrado (host fake, fake-codex em PATH, CLI da árvore)

```
regent init → initialized
advisor consult --expect-verdict '^CONCORDA$' → outcome SUCCESS, verdict CONCORDA
  (artefato com header estruturado + ADVISOR-E2E.md-PROMPT.md byte-idêntico)
gate run --command "echo e2e-gate-ok" --declared-in PLAN-E2E.md → GREEN
```

## Gates

PYTHONPATH=src python3 -m unittest discover -s tests → Ran 131 tests — OK (3 execuções)
bash scripts/gate-package.sh → build 0.5.0 + twine check PASSED + gate-package: OK
