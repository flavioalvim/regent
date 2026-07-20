# PLAN-002 (v3) — Skills control-backed: religar /regent e /regent-stop ao regent.protocol

*v2 após ADVISOR-REVIEW-1 (10 objeções — ver CLAUDE-REBUTTAL.md). v3 incorpora VERBATIM os
6 residuais do ADVISOR-REVIEW-2: tabela de recuperação completa (linhas de token local
divergente/remanescente; linha 3 rediagnosticada), coreografia de commits com BASE-SHA e
verificação de atribuibilidade das mutações operacionais, matriz control×arquivos
completa, sequência canônica de suspensão com checkpoints observáveis, schemas JSON
exatos por comando, e a lista integral de gates.*

## Objetivo

O estado das atividades passa a viver no `control.json` (transacional, PLAN-001), operado
pelas skills através de subcomandos do CLI `regent` — o executor dirige o protocolo por
comandos determinísticos com saída JSON. As skills sobem de "v0 file-driven" para
"v1 control-backed". O **control guarda ESTADO; os arquivos guardam CONTEÚDO** (fonte
única: o checkpoint vive SÓ no control; `SUSPENSION.md` deixa de existir em hosts v1).

## Escopo

**Dentro:** camada de aplicação `activity.py` (operações compostas com recuperação);
subcomandos `regent status|activity|stop`; upgrade v0→v1 do `init` por manifesto de
versões; skills v1; matrizes normativas (control×lock, control×arquivos,
comando×capacidade); errata do PLAN-001 (lock file do ControlStore no XDG).

**Fora:** daemon/condução, confinamento, adapter do advisor via CLI, `--abort` real,
migração de artefatos de CONTEÚDO, publicação PyPI.

## Contratos normativos

### Token e P-01
Token autoritativo de fencing = `control.activity.turn.token`. XDG `turn.json` = cópia
local de conveniência do CLI. `TurnLock.acquire()` continua tocando SÓ o XDG (P-01
intacto); `activity start` é a operação COMPOSTA que também muta o control.json.

### JSON e erros (todos os subcomandos)
stdout = SEMPRE JSON puro (sucesso ou erro; erro de argparse incluso); stderr = dica
humana opcional. Envelope de erro: `{"error": "<CODE>", "detail": <por código, abaixo>}`.
Catálogo (código → exit → tipo de detail):
`USAGE`→64→str (mensagem do parser) · `UNINITIALIZED`→2→{"root": str|null} ·
`NO_ACTIVITY`/`NOT_ACTIVE`/`NOT_SUSPENDED`→2→{"state": str} · `ACTIVITY_OPEN`→2→
{"activity": ActivityObj} · `TOKEN_MISMATCH`→3→{"control_token": str, "held_token":
str|null} · `LOCK_HELD`/`LOCK_SUSPECT`/`BUSY`→3→{"lock": LockObj} · `CONFLICT`→3→
{"paths": [str]} · `CORRUPT_CONTROL`→4→{"reason": str} · `IO`→5→{"errno": int|null,
"path": str}. Exit 0 = sucesso.

Schemas exatos de sucesso (`ActivityObj` = {"type","id","epoch","state"}; `LockObj` =
{"state": "free|held|suspect", "age_seconds": num|null}):
- `status` → `{"control": "uninitialized"|"corrupt"|{"version": int, "activity":
  ActivityObj|null, "stop_request": obj|null, "last_concluded": obj|null}, "lock":
  LockObj, "local_token_present": bool, "capabilities": {"executor": bool, "advisor":
  bool, "control": bool}}`.
- `start`/`resume` → `{"ok": true, "activity": ActivityObj, "token": hex32,
  "checkpoint": str|null}` (checkpoint só no resume).
- `suspend` → `{"ok": true, "activity": ActivityObj, "checkpoint": str}`.
- `conclude` → `{"ok": true, "last_concluded": {"type","id","status","epoch","at"}}`.
- `heartbeat` → `{"ok": true, "heartbeat_at": ts}`.
- `takeover` → `{"ok": true, "token": hex32, "previous_owner": hex32|null}`.
- `stop request` → `{"ok": true, "request": obj, "noop": bool}`.
- `stop check` → `{"stop_requested": bool, "request": obj|null}`.

**Redaction: nenhuma** (declarado): não há segredos no domínio — tokens são
identificadores locais de fencing sem valor de autenticação. Root: cwd para cima até
achar `.regent/`, ou `--project`; sem root = `UNINITIALIZED`. XDG state dir =
`$XDG_STATE_HOME (default ~/.local/state)/regent/<sha256(root canônico)[:16]>/`.

### Subcomandos
- `regent status` → `{"control": {…|"uninitialized"|"corrupt"}, "lock":
  {"state": free|held|suspect, …}, "local_token_present": bool, "capabilities": {…}}`.
  Nunca falha por estado (reporta); falha só por `IO`.
- `regent activity start --type T --id ID` | `resume --id ID` (epoch INCREMENTA no
  resume — "(re)início" do PLAN-001; devolve checkpoint) | `suspend --checkpoint C
  --reason R [--in-flight F]` | `conclude --status S` | `heartbeat` |
  `takeover --reason R` (mediado, auditado, rotaciona o control) — todas via camada de
  aplicação (abaixo), nunca compondo primitivas no handler.
- `regent stop request` (mediador; atividade SUSPENDED = no-op normalizado com aviso) |
  `regent stop check` → `{"stop_requested": bool, "request": …}` (descarte auditado de
  obsoletos incluso).

### Camada de aplicação (`activity.py`) — operações compostas com recuperação
Cada operação tem ordem canônica e recuperação idempotente; a recuperação SEMPRE inspeciona
(control, lock, turn.json local) e age pela tabela:

| # | control | lock | token local | diagnóstico | recuperação |
|---|---|---|---|---|---|
| 1 | ACTIVE(tok) | held(tok) | tok | são | prosseguir |
| 2 | ACTIVE(tok) | held(tok) | ausente | cópia local perdida | reescrever turn.json do lock |
| 3 | ACTIVE(tok) | free | – | takeover crashado pós-rotação/pré-acquire (fenced-sem-lock, PLAN-001) ou lock removido fora do protocolo | `takeover --reason` (rotaciona p/ token novo) |
| 4 | ACTIVE(tok) | suspect | – | executor morto | `takeover --reason` |
| 5 | ACTIVE(tokA) | held(tokB) | qualquer | divergência de fencing | erro `TOKEN_MISMATCH`; mediador decide (takeover) |
| 6 | SUSPENDED | held | – | crash pós-suspender/pré-release | release do lock (token da suspensão) e seguir |
| 7 | SUSPENDED | free | ausente | são (suspenso) | `resume` disponível |
| 8 | null | held | – | crash pós-concluir/pré-release | release; seguir |
| 9 | null | free | ausente | são (ocioso) | `start` disponível |
| 10 | SUSPENDED | free | PRESENTE | crash pós-release/pré-limpeza do token | limpar turn.json (idempotente) |
| 11 | null | free | PRESENTE | idem, pós-conclude | limpar turn.json (idempotente) |
| 12 | ACTIVE(tok) | held(tok) | OUTRO token | cópia local corrompida/antiga | reescrever turn.json do lock (lock é a verdade local; control é o autoritativo) |

Ordens canônicas: **start** = acquire lock → CAS ACTIVE(epoch=piso+1, token) → gravar
turn.json; **suspend** = evidência já persistida pelo chamador → CAS SUSPENDED(payload) →
release lock → limpar turn.json; **resume** = acquire → CAS ACTIVE(epoch+1, token novo) →
turn.json; **conclude** = CAS(last_concluded{epoch}=atividade, activity=null) → release →
limpar turn.json. Crash entre passos cai numa linha da tabela; reexecução é idempotente.

### Matriz control×arquivos (default-deny; "control manda" qualificado)
| control | arquivos | desfecho |
|---|---|---|
| ACTIVE(X, tipo T) | dir X aberto, tipo coerente | prosseguir |
| ACTIVE(X, tipo T) | dir X aberto de TIPO incompatível | erro: incoerência de tipo; mediador decide |
| ACTIVE(X) | dir X INEXISTENTE | erro: estado órfão; mediador decide (conclude/takeover) |
| ACTIVE(X) | dir X inexistente E dir Y aberto | erro: órfão + artefato alheio; mediador decide (nunca adotar Y) |
| ACTIVE(X) | artefato terminal de X já existe | erro: incoerência; mediador decide |
| ACTIVE(X) | dir Y TAMBÉM aberto | erro: segundo artefato; nunca adotar |
| SUSPENDED(X) | dir X presente coerente | são: `resume` disponível |
| SUSPENDED(X) | dir X INEXISTENTE | erro: suspenso órfão; mediador decide |
| idle/SUSPENDED≠X | dir X aberto (legado pré-v1) | reportar e PERGUNTAR ao mediador; nunca adotar silenciosamente |
| qualquer | >1 dir aberto | erro |
| corrupt | – | erro `CORRUPT_CONTROL`; nada é mutado |

### Coreografia de commits do control.json (emenda declarada ao REQ-005 §3)
`control.json` e `protocol/audit.jsonl` são estado operacional versionado:
- **BASELINE:** o build começa com um commit operacional que descarrega qualquer mutação
  pendente desses arquivos; o `BASE-SHA` do `BASELINE.md` é tomado DEPOIS dele — o
  baseline é limpo inclusive nos exceptuados.
- **Atribuibilidade verificada (default-deny preservado):** a exceção NÃO é cega — o
  registro de cada etapa guarda a `control.version` no início e no fim; antes do commit
  deliberado, o diff dos exceptuados é conferido contra as mutações que a própria
  operação explica (heartbeats, stop check, appends de audit da etapa). Mudança nesses
  arquivos que a operação corrente NÃO explica (ex.: atividade trocada) = unattributable
  → falha sem commit, como qualquer outro path.
- **Stop concorrente não contamina o commit deliberado:** os exceptuados são staged, o
  commit deliberado fecha, e SÓ ENTÃO a fronteira roda `regent stop check`; mutações
  posteriores ao staging pertencem ao próximo commit operacional (da suspensão).

### Fronteiras de stop/heartbeat e sequência canônica recuperável (skills v1)
`/regent` DEVE executar `regent stop check` + `regent activity heartbeat` em toda
fronteira nomeada: antes de produzir cada artefato de rodada/plano, e entre as fases de
cada etapa de build (implement→gate→record→commit). Stop presente → sequência canônica do
REQ-004 §4, cujos passos têm **checkpoints OBSERVÁVEIS** (sem journal separado — o estado
É o journal): (1) stop-request durável no control; (2/3) evidência do sub-passo = os
próprios artefatos no worktree/`.regent/` (o payload da suspensão ganha
`evidence: [paths]`, e o `resume` verifica a existência deles — ausência é reportada);
(4/5) checkpoint+SUSPENDED = um único CAS (`activity suspend`); (6) release = linha 6 da
tabela de recuperação; (7) confirmação = saída do comando. Retomada após crash = inspecionar
esses checkpoints em ordem e reexecutar do primeiro incompleto — cada um é idempotente.

### Matriz comando×capacidade (REQ-003 §6)
| comando | exige |
|---|---|
| `status`, `stop check` | – (leitura) |
| `activity *`, `stop request` | control inicializado |
| `/regent` modos brainstorm/plan | executor + advisor utilizáveis |
| `/regent build` | executor + advisor + control |
| `doctor` | – (é quem mede; control corrupto ⇒ exit ≠0) |

## Etapas

### STEP-01 — Errata do lock file + camada de aplicação (`src/regent/activity.py`)
ControlStore ganha parâmetro do local do lock file; produto o coloca no XDG (errata
PLAN-001; teste: nenhum `*.lock` sob `.regent/` após operações). `activity.py` implementa
start/resume/suspend/conclude/heartbeat/takeover com as ordens canônicas + tabela de
recuperação (test hooks de crash por fronteira).
- **Testes:** `test_no_lock_files_under_regent_dir`, `test_start_resume_suspend_conclude_epochs`,
  `test_recovery_row_{2,3,4,5,6,8,10,11,12}` (TODAS as linhas não-sãs, TOKEN_MISMATCH
  incluso), fault injection em CADA fronteira composta:
  `test_crash_start_between_lock_and_cas`, `test_crash_start_before_local_token`,
  `test_crash_suspend_between_cas_and_release`, `test_crash_resume_between_lock_and_cas`,
  `test_crash_conclude_between_cas_and_release`, `test_crash_before_local_token_cleanup`,
  `test_double_start_concurrent_one_wins`, `test_resume_increments_epoch`,
  `test_takeover_rotates_and_writes_local_token`, `test_suspend_records_evidence_paths`.
- **Gate:** `PYTHONPATH=src python3 -m unittest discover -s tests`

### STEP-02 — Subcomandos CLI (`src/regent/activity_cli.py`)
`status`/`activity *`/`stop *` sobre a camada de aplicação; contrato JSON/erros/exit
codes/root/XDG conforme acima; wiring no `cli.py`.
- **Testes:** `test_status_shapes_{uninitialized,idle,active,corrupt}`,
  `test_error_envelope_and_exit_codes`, `test_json_purity_on_usage_error`,
  `test_root_discovery_upward_and_project_flag`, `test_stop_request_suspended_is_noop`,
  `test_takeover_via_cli_audited`.
- **Gate:** `PYTHONPATH=src python3 -m unittest discover -s tests`

### STEP-03 — Upgrade v0→v1 no init + doctor
`templates/MANIFEST.json` (sha256 de todas as versões conhecidas por skill; gerado por
script versionado). Regra: hash conhecido = upgrade atômico da skill + semeadura do
control; hash desconhecido = conflito preservado; re-init sobre v1 com control evoluído =
no-op. Doctor reporta control (initialized/uninitialized/corrupt⇒exit≠0) e a matriz de
capacidades.
- **Testes:** `test_upgrade_v0_host_to_v1`, `test_unknown_skill_content_is_conflict`,
  `test_upgrade_failure_rolls_back_without_temps`,
  `test_reinit_v1_with_evolved_control_noop`, `test_init_seeds_valid_control`,
  `test_doctor_corrupt_control_nonzero`.
- **Gate:** `PYTHONPATH=src python3 -m unittest discover -s tests`

### STEP-04 — Skills v1 control-backed (templates)
Reescrita de `/regent` e `/regent-stop`: detecção = `regent status`; transições = os
subcomandos; fronteiras de stop/heartbeat; matrizes control×arquivos e argumento×estado
(REQ-004 §2) reescritas sobre `status`; capability v1 declarada (sem daemon/--abort);
`SUSPENSION.md` removida do fluxo v1 (hosts legados PT sem control seguem file-driven até
upgrade).
- **Testes:** `test_skill_templates_reference_real_subcommands` (anti-drift: todo comando
  citado existe no CLI), `test_skill_templates_error_codes_exist` (códigos citados ∈
  catálogo), `test_control_files_matrix_rows` (cada linha da matriz control×arquivos com
  fixture própria e desfecho assertado — a detecção é executável via `status`+listagem,
  testável sem LLM).
- **Gate:** `PYTHONPATH=src python3 -m unittest discover -s tests`

### STEP-05 — Consolidação 0.4.0
Versão 0.4.0; README (skills v1 + subcomandos); e2e REAL em venv+host fake: `regent init`
(host novo E host v0 upgradado), ciclo start→suspend→resume→conclude→takeover via CLI,
stop request/check honrado em fronteira — registrado no STEP.
- **Testes:** `test_cli_version_reports_040`,
  `test_build_choreography_base_sha_after_operational_flush`,
  `test_step_commit_attributability_of_exempted_files` (mutação explicada é staged;
  inexplicada = falha default-deny), `test_stop_after_staging_goes_to_next_operational_commit`.
- **Gate:** `bash scripts/gate-package.sh`

## Riscos
1. Drift skill↔CLI → testes anti-drift (comandos E códigos de erro).
2. Hosts em transição → matriz control×arquivos default-deny; upgrade só por manifesto.
3. Perda de turn.json/lock órfão → tabela de recuperação + `takeover` mediado.
4. Commits do control durante build → coreografia normativa (emenda REQ-005 §3 declarada).
5. Concorrência CLI (duas invocações) → serialização herdada do protocolo + teste dedicado.

## Idioma
Código/CLI/JSON em inglês (REQ-002 §1); este PLAN.md em PT (mediador PT-BR).
