# PLAN-004 / STEP-05 — Correções da revisão final (9 achados)

step_base_sha: d57cec4 (commit do STEP-04)
files_touched: src/regent/conduction/{hookscript,turnlog,turn}.py,
  tests/{test_confine,test_turn}.py

## Mapa achado→correção

- **1 (efeitos do gate fail-open):** RE-BASELINE — turn.py captura o conjunto de mudanças
  ANTES do gate; após o gate, o delta (só o que surgiu depois) são os efeitos do gate, e
  SÓ eles podem ser atribuídos como tal, exigindo ∈ gate_envelope ⊆ envelope (subset
  verificado). Mudança sem post que já existia antes do gate = violação.
- **2 (artifact_dir isento recursivamente):** isenção agora é por ARQUIVO específico do
  supervisor (GATE-*.md, TURN-*.md, STEP-NN.md), não o diretório.
- **3 (evidência do gate fora do commit + índice dessincronizado):** GATE-STEP-NN.md entra
  no commit (produto e operacional); `git reset --mixed HEAD` sincroniza o índice NORMAL
  após mover HEAD (e2e: worktree limpo após o turno).
- **4 (pré-condições REQ-005 frouxas):** current-step CALCULADO (menor STEP-NN sem
  STEP-NN.md); declared_in vinculado a .regent/plans/<id>/PLAN.md por realpath; gate
  EXTRAÍDO do bloco daquele step (`**Gate:** `...``) e comparado exato; containment de
  .regent por realpath (não prefixo textual).
- **5 (exit não-zero commitado como sucesso):** exit_code ∉ {0,None} → FAILURE (nunca
  TURN_OK).
- **6 (checkpoint/stop/recuperação ausentes):** \_set_phase durável (turn.phase no XDG) em
  COMPOSED/LAUNCHED/GATED/VERIFIED/COMMITTING/COMMITTED; stop_check em fronteira; keepalive
  (thread, 120s) cobre launch E gate (join só no fim).
- **7 (fencing/CAS parciais):** token reconferido + CAS de HEAD IMEDIATAMENTE antes do
  update-ref; commit operacional também com fencing.
- **8 (atribuição incompleta):** posts indexados por (path, tool_use_id) SÓ com pre ALLOW
  correspondente; deleção ainda checa envelope; post sem pre-allow = violação (testado).
- **9 (hook não default-deny):** allowlist de tools read-only conhecidas; QUALQUER outra
  (Bash, tool desconhecida/futura, payload malformado) = deny.

## Gates

PYTHONPATH=src python3 -m unittest discover -s tests → Ran 172 tests — OK (3 execuções)
bash scripts/gate-package.sh → 0.6.0 PASSED. E2e real refeito: TURN_OK commita agente +
gate evidence; índice limpo pós-commit.
