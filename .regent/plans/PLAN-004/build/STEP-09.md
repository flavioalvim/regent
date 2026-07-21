# PLAN-004 / STEP-09 — Correções da 5ª revisão (cobertura de stop em TODAS as rotas)

step_base_sha: 4e2d96b (commit do STEP-08)
files_touched: src/regent/conduction/turn.py, tests/test_turn.py

## Mapa achado→correção

- **1a (_boundary LAUNCHED só no sucesso):** movido para rodar INCONDICIONALMENTE logo
  após o launch (antes de ramificar em timeout/failure) — stop durante o launch é honrado
  em QUALQUER exit.
- **1b (check pré-commit só p/ TURN_OK):** agora INCONDICIONAL — um stop chegado durante
  verify/atribuição/evidência suspende, para QUALQUER desfecho, sem commitar produto NEM
  evidência operacional (o mediador retoma com /regent; o artefato fica em disco,
  não-commitado).
- **2 (teste não cobria o pré-commit):** substituído por dois testes que INJETAM o stop
  visível só na 4ª chamada de stop_check (após COMPOSED/LAUNCHED/GATED): TURN_OK suspende
  sem commitar work/out.txt; GATE_RED suspende sem commit operacional (HEAD inalterado).

## Gates

PYTHONPATH=src python3 -m unittest discover -s tests → Ran 183 tests — OK (3 execuções)
bash scripts/gate-package.sh → 0.6.0 PASSED.
