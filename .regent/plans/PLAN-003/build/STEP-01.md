# PLAN-003 / STEP-01 — regent advisor consult

step_base_sha: ffcb7ad (baseline pós-flush)
files_touched:
  - src/regent/conduction/{__init__,process,evidence,consult}.py (novos)
  - src/regent/activity_cli.py (subcomando advisor consult + 4 códigos novos no catálogo)
  - tests/test_consult.py (novo, 12 testes dirigidos)

## O que foi implementado

- `SubprocessRunner` (port injetável): start_new_session=True; timeout → killpg(SIGKILL)
  do GRUPO antes de reportar TIMEOUT.
- `EvidenceSet`: contrato atômico único do PAR/conjunto — pré-checagem de TODOS os paths
  antes de qualquer escrita (CONFLICT com a lista), siblings primeiro, main por último,
  escrita O_EXCL|O_NOFOLLOW + replace, órfãos removidos em falha não-terminal.
- `run_consult`: flags de sandbox FORÇADAS no argv (testado por captura); prompt copiado
  byte-a-byte primeiro; msg-file temporário FORA do repo; desfechos SUCCESS/TIMEOUT/
  FAILURE sempre completam o par (testado nos 3); verdict = última linha não-vazia vs
  regex (default documentado; --expect-verdict explícito fail-closed: SUCCESS sem
  casamento = ADVISOR_FAILED); codex ausente = ADVISOR_UNAVAILABLE.
- CLI: advisor consult com envelope/exit codes do catálogo estendido (declarado no plano).
- Integração real: fake-codex em PATH via CLI completo (exit 0, verdict CONCORDA).

## Gate (PYTHONPATH=src python3 -m unittest discover -s tests)

Ran 121 tests — OK (3 execuções)
