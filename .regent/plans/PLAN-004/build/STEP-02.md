# PLAN-004 / STEP-02 — Confinamento + prova git de atribuição

step_base_sha: 22cd253 (commit do STEP-01)
files_touched:
  - src/regent/conduction/confine.py (novo — composição do turno confinado)
  - src/regent/conduction/turnlog.py (attribute_changes usado; -uall no status)
  - tests/test_confine.py (novo, 13 testes)

## O que foi implementado

- `compose`: dir privado FORA do repo (tmpdir), settings.json gerado apontando os hooks
  Pre/PostToolUse para a CÓPIA privada de hookscript.py, segredo por turno (32B), settings
  e hook read-only (0400). `launch_argv`: `claude -p --setting-sources "" --settings
  <priv> --tools Read,Write,Edit,MultiEdit --permission-mode acceptEdits` (sem Bash;
  nenhuma config herdada). `launch_env`: allowlist mínimo + REGENT_*.
- `attribute_changes` (a prova de fato): diff global (git status -uall) == conjunto
  atribuído — cada path ∈ envelope com blob content_sha256 CONFERIDO contra o evento post;
  mudança sem post = violação; blob divergente = violação; efeito de gate só dentro do
  gate_envelope declarado; exceptuados operacionais (PLAN-002) passam.

## Vermelho→verde (registro fiel)

2 correções reais: git status lista DIRETÓRIO não-rastreado (dist/) — trocado por -uall
(arquivos individuais); e o fixture punha o event.log DENTRO do repo (no turno real ele
vive no dir privado fora) — movido para fora, como no desenho.

## Gate (PYTHONPATH=src python3 -m unittest discover -s tests)

Ran 161 tests — OK (3 execuções)
