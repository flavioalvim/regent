# PLAN-004 / STEP-04 — Consolidação 0.6.0

step_base_sha: b8be03c (commit do STEP-03)
files_touched: src/regent/templates/skills/regent/SKILL.md (+MANIFEST) — turno confinado
  como forma preferida de executar um STEP no /regent; pyproject+__init__ (0.6.0);
  README (fase 2 da condução); tests/test_activity_cli.py + test_skills_v1.py (anti-drift
  do turn run + versão).

## E2e REAL registrado (host fake, fake-claude + hook verdadeiro, CLI da árvore)

```
regent init → regent activity start build PLAN-001 →
TURN OK:        turn run --claude-bin fake-claude → outcome TURN_OK,
                committed ['work/generated.txt']; HEAD contém work/generated.txt +
                STEP-01.md + TURN-*.md; trailers Regent-Step + Regent-Turn presentes
TURN VIOLATION: turn run --claude-bin escaping-claude (agente escreve escaped.txt FORA
                do envelope, sem passar pelo hook) → outcome TURN_VIOLATION; escaped.txt
                NÃO commitado (git ls-files vazio), fica no worktree p/ o mediador
```

## Vermelho→verde (fiel — bug pego SÓ pelo e2e)

A CLI passa --artifact-dir/--envelope RELATIVOS; run_turn fazia relative_to(root) num path
relativo → ValueError. Os unit tests usavam paths absolutos e não pegaram. Corrigido:
resolver contra o root no início de run_turn. É exatamente o valor do dogfood e2e.

## Gates

PYTHONPATH=src python3 -m unittest discover -s tests → Ran 168 tests — OK (3 execuções)
bash scripts/gate-package.sh → 0.6.0 PASSED + gate-package: OK
