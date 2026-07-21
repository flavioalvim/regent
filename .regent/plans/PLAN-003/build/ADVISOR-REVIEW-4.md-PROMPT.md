Revisor adversarial (Codex) do regent — SEGUNDA revisão final do BUILD do PLAN-003, após o
STEP-06 (leia .regent/plans/PLAN-003/build/STEP-06.md — mapa dos seus 7 achados — e o
ADVISOR-REVIEW-3.md com header dogfoodado). MÁXIMO ~6 minutos. Verifique DIRETAMENTE em
src/regent/conduction/{process,evidence,consult,gate}.py se os 7 fecharam: comando vazio =
PROVENANCE; cleanup de órfão em erro não-terminal; pipeline de BYTES (FULL.log cru, cauda
por bytes, decode replace); publish NO-CLOBBER via os.link (TOCTOU fechado); regex
explícita vazia honrada (is not None); cópia do prompt por bytes; exit_code no envelope.
Gates: 132 testes verdes 3×, gate-package 0.5.0 OK. Só liste violações MATERIAIS
restantes. TERMINE obrigatoriamente com uma linha contendo apenas: APROVADO, APROVADO COM
RESSALVAS ou REPROVADO.
