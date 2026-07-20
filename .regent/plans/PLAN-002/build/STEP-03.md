# PLAN-002 / STEP-03 — Upgrade v0→v1 no init + semeadura do control + doctor

step_base_sha: 7efc36c (commit do STEP-02)
files_touched:
  - src/regent/templates/MANIFEST.json (novo — hashes sha256 de TODAS as versões
    conhecidas de cada template, legadas colhidas do git: 2748a91 e a7e7abb)
  - scripts/update-manifest.py (novo — passo de release, idempotente)
  - src/regent/initcmd.py (estado 'upgradeable' por hash conhecido; upgrade atômico com
    restauração de originais no rollback; kind 'control': semeia ausente, válido em
    qualquer versão evoluída = no-op, corrupto = conflito)
  - src/regent/doctor.py (linha 'control' initialized/uninitialized/corrupt; corrupto
    derruba o exit — PLAN-002)
  - tests/test_init_upgrade.py (novo, 7 testes) + asserção de control no test_initcmd

## Gate (PYTHONPATH=src python3 -m unittest discover -s tests)

Ran 74 tests — OK (3 execuções)

Cobertura nova: upgrade v0→v1 real (conteúdo legado por hash), conteúdo desconhecido
preservado como conflito (control NÃO semeado junto), rollback de upgrade restaura o
original sem temporários, re-init sobre control evoluído é no-op byte-preservante,
control semeado válido, doctor com control corrupto = exit ≠0.
