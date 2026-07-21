# PLAN-006 / STEP-04 — Consolidação 0.8.0

**Base:** 5348b40a04679a33bc68d17e5ff097fba449a8a5 (STEP-03)

## O que foi implementado
- **Skill de build** (`templates/skills/regent/SKILL.md`): adicionada a 4ª via de
  build **"Supervised hands-off (preferred)"** = rehearse (prever, read-only) →
  arm (autorização durável do dono) → daemon run (dirige revalidando o arm por
  turno; STEPS_COMPLETE ≠ aceito — revisão final/CONCLUSION/conclude ficam com o
  MEDIADOR). Cabeçalho "Capability level" atualizado: condução COMPLETA
  (turn/loop+abort/daemon+arm/disarm); fase 5 (daemon em background, arm
  automático, notificações) declarada como futura.
- **Anti-drift** (`tests/test_skills_v1.py`): `KNOWN_SUBCOMMANDS` +
  rehearse/arm/disarm/daemon run; regex de grupo inclui `daemon`.
- **Versão 0.8.0**: `pyproject.toml` + `src/regent/__init__.py`; teste
  `test_cli_version_reports_080`.
- **MANIFEST.json**: novo hash do SKILL.md regent anexado (upgrade limpo p/ hosts
  na versão anterior) via `scripts/update-manifest.py`.

## e2e (REAL fake-claude, ponta a ponta pela CLI)
`test_e2e_arm_daemon_drives_two_steps_to_complete`: um fake-claude que escreve
`work/<step>.out` ATRAVÉS do hook confinado (satisfaz a atribuição git-anchored);
`regent arm` → `regent daemon run --once --claude-bin <fake>` dirige STEP-01 e
STEP-02 → `STEPS_COMPLETE` (exit 0), ambos commitados com `Regent-Step`, arm-token
removido, atividade ainda ACTIVE (conclusão é mediada).

## Gate
`bash scripts/gate-package.sh` → build 0.8.0 + `twine check --strict` PASSED →
`gate-package: OK`. Suíte completa: 240 OK.
