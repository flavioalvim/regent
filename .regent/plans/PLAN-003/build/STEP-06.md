# PLAN-003 / STEP-06 — Correções da revisão final dogfoodada (7 achados)

step_base_sha: ba31ac4 (commit do STEP-05)
files_touched: src/regent/conduction/{process,evidence,consult,gate}.py,
  src/regent/activity_cli.py, tests/test_consult.py

## Contexto (registro fiel do dogfood)

A revisão final foi executada PELO PRÓPRIO `regent advisor consult`: a 1ª e a 2ª
consultas registraram TIMEOUT automaticamente (evidência completa sem intervenção); a 2ª
expôs AO VIVO o bug do stdin herdado (codex pendurado esperando EOF) → STEP-05
(stdin=DEVNULL + regressão). A 3ª consulta completou com veredicto REPROVADO extraído
automaticamente e 7 achados.

## Mapa achado→correção

- **ALTA 1 (proveniência fail-open com comando vazio):** comando vazio/whitespace =
  PROVENANCE antes de qualquer coisa.
- **ALTA 2 (par quebrado em erro não-terminal):** execução envolta em try —
  cleanup_orphans() remove a cópia do prompt em QUALQUER exceção não-terminal.
- **ALTA 3 (bytes arbitrários):** runner passa a BYTES fim-a-fim (RunResult.output_bytes;
  .output = decode replace); FULL.log guarda os BYTES crus; cauda cortada POR BYTES e
  decodificada com replace — saída não-UTF8 nunca derruba nem perde evidência.
- **ALTA 4 (TOCTOU precheck→publish):** `atomic_write` virou NO-CLOBBER real —
  os.link(tmp, dst) atômico (EEXIST se corrida) → EvidenceConflict; evidência nunca é
  sobrescrita nem por escritor concorrente.
- **MÉDIA 5 (regex explícita vazia):** `is not None` em vez de truthiness — regex vazia
  explícita é honrada (fail-closed).
- **MÉDIA 6 (byte-a-byte do prompt):** cópia via read_bytes/escrita binária (read_text
  normalizaria CRLF).
- **MÉDIA 7 (envelope):** ADVISOR_FAILED.detail ganha exit_code (e run_consult o expõe).

## Vermelho→verde: FakeRunner do teste atualizado para o campo bytes.

## Gates

PYTHONPATH=src python3 -m unittest discover -s tests → Ran 132 tests — OK (3 execuções)
bash scripts/gate-package.sh → 0.5.0 PASSED + gate-package: OK
