# PLAN-002 / STEP-08 — Correções da 3ª revisão (contabilidade por transição casada)

step_base_sha: f01650f (commit do registro do ADVISOR-REVIEW-3)
files_touched:
  - src/regent/activity.py (explain v3: transições CASADAS com eventos)
  - src/regent/initcmd.py (guarda ancestral também nos symlinks; journal via
    escrita atômica O_EXCL; falhas de limpeza reportadas nos dois caminhos)
  - tests/test_step06_fixes.py (3 dirigidos novos)

## Mapa achado→correção

- **BLOQUEANTE (contabilidade permissiva/incoerente):** modelo de transição casada —
  chegada bem-formada = explicada; **obj→null SÓ com discard auditado de request_id
  CASADO** = explicada (o caso legítimo que era recusado agora passa, testado); evento
  de discard SEM transição casada = `audit:...-unmatched` (evento inventado nunca
  compra crédito de versão, testado); **delta de versão == contagem EXATA** (nem mais
  nem menos — 1 mutação com delta 2 = recusado, testado).
- **ALTA (escapes do init):** guarda de symlink ancestral aplicada TAMBÉM aos itens de
  integração (`.claude/skills` apontando p/ fora = conflito, nada escrito fora —
  testado); journal escrito via `_atomic_write` (O_EXCL|O_NOFOLLOW + replace — symlink
  pré-existente nunca seguido); falha ao limpar journal/.regent entra na lista de
  não-restaurados (rollback) ou vira warning explícito (sucesso) — a mensagem nunca
  mente.
- Contrato JSON: já fechado na 3ª revisão (confirmado pelo advisor).

## Gates

PYTHONPATH=src python3 -m unittest discover -s tests → Ran 109 tests — OK (3 execuções)
bash scripts/gate-package.sh → 0.4.0 PASSED + gate-package: OK
