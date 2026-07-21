# PLAN-003 / STEP-03 — Skills religadas + anti-drift

step_base_sha: fd7a749 (commit do STEP-02)
files_touched:
  - src/regent/templates/skills/regent/SKILL.md (§4 consultas → advisor consult;
    gates de build → gate run com proveniência) + MANIFEST atualizado
  - tests/test_skills_v1.py (anti-drift: 2 subcomandos novos; teste de que a invocação
    crua do codex SUMIU das skills)

## Registro

- A skill não prescreve mais `codex --ask-for-approval ...` (teste
  `test_skill_no_longer_prescribes_raw_codex`); consultas = `regent advisor consult`
  (par de evidência automático, retry = artefato novo); gates de etapa =
  `regent gate run --declared-in` (proveniência verificada; RED/TIMEOUT nunca commitam).
- regent-stop já não citava codex (verificado).

## Gate (PYTHONPATH=src python3 -m unittest discover -s tests)

Ran 131 tests — OK (3 execuções)
