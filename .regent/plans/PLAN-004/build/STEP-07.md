# PLAN-004 / STEP-07 — Correções da 3ª revisão (4 achados residuais de segurança)

step_base_sha: 5e67cfa (commit do STEP-06)
files_touched: src/regent/conduction/{hookscript,turnlog,turn}.py,
  tests/{test_confine,test_turn}.py

## Mapa achado→correção

- **1 (stop/checkpoint/recuperação):** stop_check em TODAS as fronteiras (COMPOSED,
  LAUNCHED, pós-GATE antes de VERIFIED); `STOPPED` agora SUSPENDE a atividade de fato
  (`suspend_activity` com checkpoint `turn:<phase>`, retomável por /regent);
  \_set_phase ganha fsync do diretório.
- **2 (lavar GATE/FULL pela isenção):** se o agente pré-cria o path de evidência do gate,
  `run_gate` levanta EvidenceConflict → GATE_CONFLICT: os arquivos NÃO são isentos NEM
  commitados (nem no operacional) → TURN_VIOLATION; e2e-teste: forja não commitada.
- **3 (deleção e tipo escapam):** deleção de path com post = violação (agente confinado
  não deleta via tools permitidas); swap regular→symlink pós-post = violação; hook e
  verificador usam `lstat`/`islink` (NUNCA dereferenciam); `_rel` canoniza o PAI mas
  não segue o symlink do leaf (fecha o vetor de renomear o path por resolve()).
- **4 (build canônico com symlink):** artifact_dir deve ser IGUAL ao build canônico E
  estar sob o root REAL (`_under`) — `build` symlink p/ fora resolve e falha.

## Gates

PYTHONPATH=src python3 -m unittest discover -s tests → Ran 181 tests — OK (3 execuções)
bash scripts/gate-package.sh → 0.6.0 PASSED. E2e refeito: TURN_OK, índice limpo.
