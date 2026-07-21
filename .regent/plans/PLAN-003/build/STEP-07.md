# PLAN-003 / STEP-07 — Correção do residual (guarda única de limpeza de órfãos)

step_base_sha: 0558813 (commit do STEP-06)
files_touched: src/regent/conduction/{consult,gate,evidence}.py, tests/test_consult.py

- Guarda ÚNICA de cleanup envolvendo a operação INTEIRA (publicação do sibling, temp
  file, execução e publicação do main) em consult E gate: QUALQUER exceção — inclusive
  EvidenceConflict do no-clobber numa corrida no artefato principal — remove os siblings
  já publicados; só o write_main completo (desfecho terminal) deixa o par.
- evidence.py: os handlers internos também capturam EvidenceConflict (não é OSError).
- Teste dirigido novo: runner que "corre" criando o artefato principal durante a execução
  → EvidenceConflict E a cópia do prompt é limpa (a evidência do corredor fica intacta).

Gates: Ran 133 tests — OK (3×) · gate-package 0.5.0 OK
