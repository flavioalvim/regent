# PLAN-003 (v2) — Condução fase 1: advisor consult e gate run mecanizados

*v2 após ADVISOR-REVIEW-1 (5 objeções incorporadas — ver CLAUDE-REBUTTAL.md): proveniência
obrigatória do comando de gate (--declared-in + verbatim, erro PROVENANCE); --expect-verdict
explícito é fail-closed (ADVISOR_FAILED sem casamento); íntegra sempre preservada
(<artifact>-FULL.log acima de 200 KiB); timeout mata o GRUPO de processos
(start_new_session + killpg, com teste real de filho órfão); o PAR de artefatos tem
contrato atômico único (pré-existência de qualquer um = CONFLICT; todo desfecho terminal
deixa o par completo).*

## Objetivo

Os dois sub-passos que hoje o executor faz À MÃO em todo turno — consultar o advisor e
rodar gates — viram comandos do CLI com **evidência automática e fail-closed**:
`regent advisor consult` (porta o `CodexConsultAdapter` provado na IMP-003, com a tupla
do REQ-003 §5 gerada pelo comando, não pela disciplina do executor) e `regent gate run`
(executa o comando de gate declarado e registra saída+exit como evidência). Elimina a
classe de erro "evidência esquecida/incompleta/editada à mão".

## Escopo

**Dentro:** módulo `src/regent/conduction/` (`consult.py`, `gate.py`) + subcomandos;
formato de artefato de evidência; religação das skills (a prescrição manual do codex vira
o comando); testes com adapter de processo INJETADO (sem depender do codex real na suíte).

**Fora (fase 2 da condução):** daemon/loop supervisionado, executor confinado (hooks
HMAC), `--abort` real, decisão automática de turno, ensaio; publicação PyPI.

## Contratos normativos

### `regent advisor consult`
`regent advisor consult --prompt-file <path> --artifact <path-out> --linkage <str>
[--timeout <s=600>] [--expect-verdict <REGEX>]`
- Invoca `codex --ask-for-approval never --sandbox read-only exec --cd <root> -o <tmp>
  "<prompt>"` (flags de sandbox OBRIGATÓRIAS, não configuráveis).
- SEMPRE persiste (mesmo em falha/timeout): `<artifact>` = resposta integral com
  cabeçalho estruturado (`outcome: SUCCESS|TIMEOUT|FAILURE`, `exit_code: int|null`,
  `timestamp`, `linkage`, `verdict: <str|null>`) e `<artifact>-PROMPT.md` = prompt
  integral (cópia byte-a-byte do prompt-file). Escrita atômica (tmp+replace); artefato
  pré-existente = erro (`CONFLICT` — evidência nunca é sobrescrita).
- `verdict` = última linha não-vazia da resposta se casar `--expect-verdict` (default
  `^(CONCORDA|DISCORDA.*|APROVADO( COM RESSALVAS)?|REPROVADO|QUITADAS|PENDENTES.*)$`);
  sem casamento → `verdict: null`.
- stdout JSON: `{"ok": bool, "outcome": ..., "verdict": str|null, "artifact": path,
  "prompt_copy": path}`; exit 0 SÓ com outcome SUCCESS (fail-closed: TIMEOUT/FAILURE →
  exit 3 com envelope `{"error": "ADVISOR_FAILED", "detail": {"outcome", "exit_code"}}`
  — código novo no catálogo, extensão declarada). Advisor ausente → capacidade:
  `{"error": "ADVISOR_UNAVAILABLE"}` exit 2 (código novo declarado).

### `regent gate run`
`regent gate run --command "<shell>" --declared-in <plan-artifact> --artifact <path-out>
--linkage <str> [--timeout <s=1800>]` — o comando DEVE constar verbatim no artefato
referenciado (senão erro `PROVENANCE`, código novo declarado)
- Executa via `bash -c` no root do host; captura stdout+stderr combinados (cauda de até
  200 KiB no artefato, tamanho integral registrado) e exit code.
- SEMPRE persiste o artefato com cabeçalho (`outcome: GREEN|RED|TIMEOUT`, `exit_code`,
  `timestamp`, `linkage`, `command`); escrita atômica; pré-existente = `CONFLICT`.
- stdout JSON `{"ok": bool, "outcome": ..., "exit_code": int|null, "artifact": path}`;
  exit 0 SÓ com GREEN; RED/TIMEOUT → exit 3, envelope `{"error": "GATE_RED",
  "detail": {...}}` (código novo declarado). O comando NUNCA é inventado pelo regent —
  vem do plano (token→comando do LOTE, herança IMP-000).

### Formato do cabeçalho de evidência (ambos)
Front-matter delimitado por `---` com chaves em inglês (REQ-002); corpo = saída integral.
Compatível com o formato que os builds PLAN-001/002 usaram à mão.

### Injeção para testes
`consult.py`/`gate.py` recebem um runner de processo injetável (`ProcessRunner` port);
a suíte usa fakes determinísticos (sucesso/verdict, falha, timeout, saída gigante);
UM teste de integração real com um binário fake em PATH (`fake-codex` shell script)
valida o wiring ponta a ponta sem rede.

## Etapas

### STEP-01 — `conduction/consult.py` + subcomando
- **Testes:** `test_consult_success_persists_tuple_and_verdict`,
  `test_consult_expect_verdict_fail_closed`, `test_consult_pair_conflict_either_file`,
  `test_consult_terminal_outcome_always_completes_pair`,
  `test_consult_timeout_records_and_fails_closed`,
  `test_consult_failure_records_exit_code`, `test_consult_refuses_existing_artifact`,
  `test_consult_missing_codex_is_capability_error`,
  `test_consult_prompt_copy_byte_identical`, `test_consult_sandbox_flags_forced`
  (o fake registra argv; asserta `--sandbox read-only` e `--ask-for-approval never`).
- **Gate:** `PYTHONPATH=src python3 -m unittest discover -s tests`

### STEP-02 — `conduction/gate.py` + subcomando
- **Testes:** `test_gate_green_persists_and_exits_zero`, `test_gate_provenance_required`,
  `test_gate_timeout_kills_process_group` (filho sleep real morto),
  `test_full_log_sidecar_over_200k`,
  `test_gate_red_fails_closed_with_artifact`, `test_gate_timeout_recorded`,
  `test_gate_refuses_existing_artifact`, `test_gate_output_tail_truncation_declared`.
- **Gate:** `PYTHONPATH=src python3 -m unittest discover -s tests`

### STEP-03 — Skills religadas + anti-drift
A seção de consultas do `/regent` prescreve `regent advisor consult` (a invocação manual
do codex sai do texto); fronteiras de build usam `regent gate run` para os gates de etapa.
- **Testes:** anti-drift atualizado (novos subcomandos e códigos no catálogo),
  `test_skill_no_longer_prescribes_raw_codex` (a string `codex --ask-for-approval` não
  aparece mais nas skills).
- **Gate:** `PYTHONPATH=src python3 -m unittest discover -s tests`

### STEP-04 — Consolidação 0.5.0
Versão 0.5.0; README; e2e real com `fake-codex` + gate verdadeiro (unittest) num host
fake, registrado no STEP.
- **Testes:** `test_cli_version_reports_050`.
- **Gate:** `bash scripts/gate-package.sh`

## Riscos

1. Parser de verdict frágil → regex explícita com default documentado + `verdict: null`
   honesto quando não casa (nunca inventa veredicto).
2. Saídas gigantes → cauda limitada declarada no artefato (tamanho integral registrado).
3. Suíte dependendo do codex real → runner injetado + fake em PATH; o codex real só é
   exigido em runtime (capacidade, REQ-003 §6).
4. Sobrescrita de evidência → `CONFLICT` em artefato pré-existente (retry = novo nome,
   consistente com "nova consulta registrada" do REQ-003 §5).

## Idioma
Código/CLI/artefatos de sistema em inglês (REQ-002); este PLAN.md em PT (mediador PT-BR).
