# PLAN-002 / STEP-05 — Consolidação 0.4.0

step_base_sha: c54c80f (commit do STEP-04)
files_touched:
  - pyproject.toml + src/regent/__init__.py (0.4.0)
  - README.md (skills v1 + subcomandos + upgrade por manifesto)
  - src/regent/activity.py (explain_control_diff — respaldo executável da
    atribuibilidade da coreografia)
  - tests/test_choreography.py (novo, 3 testes) + VersionTest no test_activity_cli

## Testes de coreografia (propriedades normativas com git real)

- BASE-SHA tomado após commit operacional de descarga (baseline limpo INCLUSIVE nos
  exceptuados);
- atribuibilidade: stop_request chegando no meio da etapa = explicado; atividade trocada
  = unexplained → commit da etapa DEVE falhar (helper `explain_control_diff`);
- stop chegando APÓS o staging não contamina o commit deliberado (staged intacto) e fica
  pendente para o commit operacional seguinte, honrado no boundary.

Nota registrada: a comparação de atribuibilidade vive como helper de biblioteca
(`explain_control_diff`); a skill prescreve a checagem via snapshots do `regent status`
(control.version no início da etapa). Expor como subcomando dedicado fica para a fase de
condução (o daemon é quem commitará etapas de fato).

## E2e REAL (venv + CLI instalada, registrado)

```
pip install ~/projetos/regent → regent 0.4.0
host NOVO:      regent init → seeded .regent/control.json → status IDLE_CLEAN
host v0.2 REAL: (skills de a7e7abb) regent init → "upgraded" ×2 + control seeded
ciclo:          start(ACTIVE, epoch 0) → heartbeat ok → stop request → stop_requested
                true → suspend(SUSPENDED, checkpoint "PLAN.md pendente", evidence) →
                resume(checkpoint devolvido, epoch 1) → conclude(APPROVED) →
                status: activity null, IDLE_CLEAN, lock free
```

## Gates

```
PYTHONPATH=src python3 -m unittest discover -s tests → Ran 92 tests — OK
bash scripts/gate-package.sh → build 0.4.0 + twine check PASSED + gate-package: OK
```
