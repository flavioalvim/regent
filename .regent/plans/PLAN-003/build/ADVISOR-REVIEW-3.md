---
outcome: SUCCESS
exit_code: 0
timestamp: 2026-07-21T01:06:22+00:00
linkage: PLAN-003/build
verdict: REPROVADO
---

1. **ALTA — Proveniência fail-open:** `command=""` sempre passa em `command not in declared_text` e executa `bash -c ""`, produzindo GREEN sem gate declarado. Falta rejeitar comando vazio e validar a declaração exata. [gate.py](/home/flavio/projetos/regent/src/regent/conduction/gate.py:27)

2. **ALTA — Par atômico quebrado em erro não terminal:** a cópia do prompt é gravada antes de `mkstemp`/execução; qualquer exceção posterior deixa `-PROMPT.md` órfão. O CLI então pode retornar `IO`, mas a próxima tentativa recebe `CONFLICT`. [consult.py](/home/flavio/projetos/regent/src/regent/conduction/consult.py:41)

3. **ALTA — Saída de gate não é integral para bytes arbitrários:** `text=True` usa decodificação estrita; saída não UTF-8 causa `UnicodeDecodeError`, sem artefato nem envelope JSON. Reproduzido com um processo emitindo `0xff`. A cauda também é cortada por caracteres, não por bytes. [process.py](/home/flavio/projetos/regent/src/regent/conduction/process.py:25) [gate.py](/home/flavio/projetos/regent/src/regent/conduction/gate.py:40)

4. **ALTA — Evidência pode ser sobrescrita em corrida:** existe TOCTOU entre `precheck()` e `os.replace()`. Se outro processo criar o destino nesse intervalo, `os.replace` sobrescreve a evidência, contrariando `CONFLICT`/“nunca sobrescrita”. [evidence.py](/home/flavio/projetos/regent/src/regent/conduction/evidence.py:48) [evidence.py](/home/flavio/projetos/regent/src/regent/conduction/evidence.py:39)

5. **MÉDIA — `--expect-verdict` vazio não é fail-closed:** `expect_verdict or DEFAULT_VERDICT_RE` substitui uma regex explicitamente vazia pelo default; uma resposta `CONCORDA` pode ser aceita embora não case a regex fornecida. [consult.py](/home/flavio/projetos/regent/src/regent/conduction/consult.py:68)

6. **MÉDIA — Contrato byte-a-byte do prompt não é cumprido:** `read_text()` normaliza CRLF para LF antes da cópia. O teste usa apenas LF e não detecta a alteração. [consult.py](/home/flavio/projetos/regent/src/regent/conduction/consult.py:31)

7. **MÉDIA — Envelope `ADVISOR_FAILED` incompleto:** o contrato exige `detail.exit_code`; o resultado de `run_consult` não o expõe e o CLI o omite. [activity_cli.py](/home/flavio/projetos/regent/src/regent/activity_cli.py:156)

REPROVADO