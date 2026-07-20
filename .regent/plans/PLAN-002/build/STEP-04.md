# PLAN-002 / STEP-04 — Skills v1 control-backed

step_base_sha: adc1c77 (commit do STEP-03)
files_touched:
  - src/regent/templates/skills/regent/SKILL.md (reescrita v1)
  - src/regent/templates/skills/regent-stop/SKILL.md (reescrita v1)
  - src/regent/templates/MANIFEST.json (hashes v1 anexados via update-manifest.py)
  - src/regent/activity.py (workspace_report + classify_workspace + WORKSPACE_VERDICTS —
    a matriz control×arquivos virou EXECUTÁVEL dentro do `regent status`)
  - tests/test_skills_v1.py (novo, 14 testes)

## Decisão de implementação registrada

A matriz control×arquivos do plano NÃO ficou só em texto de skill: `regent status` ganhou
o campo `workspace` ({open_artifacts, verdict}) que a computa deterministicamente
(esquemas EN e legado PT). A skill lê o veredicto pronto (OK/SUSPENDED_OK/IDLE_CLEAN
prosseguem; o resto = reportar e perguntar ao mediador) — cada linha testável sem LLM,
como o plano exigia.

## Skills v1

- /regent: detecção = `regent status`; matriz argumento×estado sobre o JSON; abrir/
  retomar/concluir atividade = subcomandos; fronteiras nomeadas de `stop check` +
  `heartbeat` (antes de cada artefato; entre fases de etapa de build); suspensão via
  `activity suspend --checkpoint --evidence`; erros com códigos EXATOS do catálogo e
  caminho mediado de takeover; hosts legados PT sem control = file-driven até `regent
  init` (upgrade por manifesto); capability v1 declarada (sem daemon/--abort).
- /regent-stop: stop-request durável + suspensão CAS; SUSPENSION.md eliminada do fluxo
  v1 (checkpoint só no control); commit operacional não-bloqueante.

## Vermelho→verde (registro fiel)

3 falhas na 1ª execução: regex do anti-drift pegava prosa ("regent activity in progress")
→ restringido a spans de backtick; veredictos de workspace confundidos com códigos de
erro → formalizados como constante WORKSPACE_VERDICTS do produto; fixture do
SUSPENDED_ORPHAN reusava dir aberto de outra asserção → isolada.

## Gate (PYTHONPATH=src python3 -m unittest discover -s tests)

Ran 88 tests — OK (3 execuções)
