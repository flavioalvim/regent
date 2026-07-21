# PLAN-003 / STEP-02 — regent gate run

step_base_sha: 77de985 (commit do STEP-01)
files_touched:
  - src/regent/conduction/gate.py (autorado na janela do STEP-01, staged AGORA — registro
    fiel; a atribuição do commit é desta etapa)
  - tests/test_gate.py (novo, 9 testes dirigidos)

## O que foi implementado

- Proveniência VERIFICADA: o comando deve constar verbatim no artefato --declared-in
  (ProvenanceError/PROVENANCE; nada é escrito).
- Execução via bash -c com start_new_session; timeout → killpg do grupo — TESTE REAL:
  filho `sleep 60 &` morto junto (kill -0 → ProcessLookupError).
- Íntegra sempre: ≤200 KiB inline; acima, FULL.log (sidecar no MESMO contrato atômico do
  conjunto — conflito testado) + cauda declarada (output_bytes/truncated no header).
- GREEN/RED/TIMEOUT fail-closed; evidência nunca sobrescrita.

## Gate (PYTHONPATH=src python3 -m unittest discover -s tests)

Ran 130 tests — OK (3 execuções)
