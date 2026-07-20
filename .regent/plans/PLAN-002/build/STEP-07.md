# PLAN-002 / STEP-07 — Correções da 2ª revisão final (atribuibilidade real)

step_base_sha: f3d0961 (commit do registro do ADVISOR-REVIEW-2)
files_touched:
  - src/regent/activity.py (explain com CONTABILIDADE DE VERSÃO + since_version)
  - src/regent/activity_cli.py (--since-version; audit por PREFIXO real; USAGE/
    ACTIVITY_OPEN/TOKEN_MISMATCH nos schemas exatos)
  - src/regent/initcmd.py (guarda de symlink ANCESTRAL; tempfile O_EXCL|O_NOFOLLOW
    único; journal de instalação; rollback com relatório honesto de falhas)
  - src/regent/protocol/audit.py (linha corrompida vira sentinela, nunca exceção crua)
  - src/regent/templates/skills/regent/SKILL.md (--since-version prescrito) + MANIFEST
  - tests/test_step06_fixes.py (4 dirigidos novos + fixtures endurecidas pelo próprio
    explain)

## Mapa achado→correção

- **BLOQUEANTE (explain não default-deny):** NADA é explicado por default agora —
  `version`/`updated_at` só são explicados quando o delta de versão é IGUAL à
  contagem de mutações legítimas contabilizadas (chegada bem-formada de stop_request com
  keyset exato + descartes auditados com request_id); salto solto de versão (10→999) =
  unexplained (testado). `--since-version` implementa o snapshot da skill (HEAD ≤ N ≤
  worktree, senão unexplained). Audit comparado por **PREFIXO real** (HEAD deve ser
  prefixo do worktree; história reescrita com mesma contagem = default-deny — testado);
  linha nova corrompida = default-deny.
- **ALTA (init parcial):** paths semeados com ancestral symlink que resolve fora do host
  = conflito (testado: nada escrito fora); tempfile único com O_EXCL|O_NOFOLLOW (symlink
  pré-existente jamais seguido); journal `.init-journal.json` marca instalação em
  andamento (crash → próxima execução completa via manifesto — mensagem explícita);
  rollback devolve a LISTA do que não conseguiu restaurar e a mensagem não mente mais.
  Atomicidade de instalação = por arquivo + journal + convergência por re-run
  (declarado; transação multi-arquivo verdadeira exigiria staging de FS fora do escopo).
- **MÉDIA (contrato):** USAGE.detail = string; ACTIVITY_OPEN.detail sem campo extra;
  TOKEN_MISMATCH nunca null (strings vazias como fallback declarado); audit corrompido
  não quebra o stdout-JSON.

## Vermelho→verde: fixture de audit reescrito com 1 linha (reverso = idêntico) corrigida
para ≥2 linhas distintas.

## Gates

PYTHONPATH=src python3 -m unittest discover -s tests → Ran 106 tests — OK (3 execuções)
bash scripts/gate-package.sh → 0.4.0 PASSED + gate-package: OK
