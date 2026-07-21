# PLAN-004 / STEP-06 — Correções da 2ª revisão final (9 achados residuais)

step_base_sha: b6d369e (commit do STEP-05)
files_touched: src/regent/conduction/{hookscript,turnlog,turn}.py,
  tests/{test_hookscript,test_confine,test_turn}.py

## Mapa achado→correção

- **1 (checkpoint/stop/recuperação):** \_set_phase agora é ATÔMICO (O_TRUNC+fsync+replace);
  stop_check em CADA fronteira (COMPOSED e GATED, além do pré-launch); `recover_turn`
  implementado (trailer→STEP→worktree; PARTIAL = mediador decide, nunca retoma mid-agent).
- **2 (commit operacional sem fencing/CAS):** roteado pelo MESMO mecanismo do produto —
  índice privado, token reconferido, update-ref <new> <old> na menor janela.
- **3 (FULL.log do gate quebra atribuição/suja worktree):** o sidecar GATE-*.md-FULL.log
  é isento e COMMITADO (produto e operacional) quando existe.
- **4 (bypass do current-step via outro artifact_dir):** artifact_dir DEVE ser exatamente
  `.regent/plans/<id>/build` (canônico), não qualquer dir sob .regent.
- **5 (modo/tipo fora da prova):** hook grava `mode` no post; atribuição rejeita mudança
  de modo pós-post (chmod preservando bytes = violação, testado).
- **6 (payload malformado allowlisted):** tool_input não-dict = deny (fail-closed), testado.
- **2/7 confirmados:** produto já tinha CAS; operacional agora também. Fencing imediato.

## Gates

PYTHONPATH=src python3 -m unittest discover -s tests → Ran 176 tests — OK (3 execuções)
bash scripts/gate-package.sh → 0.6.0 PASSED. E2e refeito: TURN_OK, índice limpo,
recover_turn → COMMITTED.
