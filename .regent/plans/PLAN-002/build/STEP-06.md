# PLAN-002 / STEP-06 — Correções da revisão final (serialização das operações compostas)

step_base_sha: 446f8cf (commit do registro do ADVISOR-REVIEW)
files_touched:
  - src/regent/activity.py (ops flock; guards; strict release; explain endurecido;
    ActivityObj com checkpoint/reason; MULTIPLE_SCHEMES)
  - src/regent/activity_cli.py (catálogo saneado; --reason; TOKEN_MISMATCH com detail
    real; regent control explain + UNATTRIBUTABLE)
  - src/regent/protocol/{control,stop}.py (stop_request.reason no schema)
  - src/regent/initcmd.py (symlink=conflito; escrita atômica tmp+replace; rollback idem)
  - src/regent/templates/skills/*/SKILL.md + MANIFEST (prescrições novas)
  - tests/test_step06_fixes.py (novo, 10) + ajustes em test_control/test_skills_v1

## Mapa achado→correção

- **BLOQUEANTE 1 (composição não serializada):** TODAS as operações públicas do
  ActivityService rodam sob um **ops flock por host** — recover→acquire→CAS→turn.json é
  UMA unidade; o cenário "B libera o lock de A no meio do start" é impossível
  (serializado). Callback do resume ganhou guard raced (não sobrescreve transição
  concorrente; perdedor desfaz o lock e erra explicitamente). Teste concorrente agora
  afirma o ESTADO FINAL coerente (control.turn.token == owner do lock).
- **BLOQUEANTE 2 (atribuibilidade não implementada):** `explain_control_diff`
  endurecido (schema_version=unexplained; stop_request só explicado na CHEGADA bem
  formada vinculada à atividade corrente; sumiço/troca=unexplained; audit_delta com
  allowlist) e agora é PRODUTO: `regent control explain` compara HEAD↔worktree
  (control + delta do audit) e sai `UNATTRIBUTABLE`/3 quando há mudança inexplicada;
  a skill de build prescreve o snapshot de control.version e o explain antes do staging.
  Teste e2e do hijack via CLI com git real.
- **ALTA (falha→sucesso):** suspend/conclude usam release ESTRITO (falha propaga; estado
  vira linha 6/8 recuperável — testado com chmod); _clear_local_token só engole ENOENT;
  _release_quietly restrito ao recovery (NotLockOwner/StaleLock auditados; OSError
  propaga).
- **ALTA (upgrade):** escrita por tmp+os.replace (atômica por arquivo; re-run completa o
  restante — hash novo já no manifesto); rollback restaura por replace; **symlink no
  lugar da skill = conflito** (teste com alvo externo preservado).
- **ALTA (takeover idle/suspended):** recusado com NO_ACTIVITY/NOT_ACTIVE (só recupera
  ACTIVE, linhas 3–5).
- **MÉDIA (contrato):** código "ACTIVITY" eliminado (USAGE/ACTIVITY_OPEN); CONFLICT
  detail = {paths}; TOKEN_MISMATCH preenche control_token/held_token reais; IO.path
  nunca null; UNATTRIBUTABLE adicionado ao catálogo (desvio declarado).
- **MÉDIA (dados p/ skills):** stop_request ganha `reason` (schema+CLI --reason+check);
  ActivityObj de SUSPENDED carrega checkpoint/reason no status (extensão declarada).
- **MÉDIA (dois esquemas):** rounds/ E rodadas/ com QUALQUER conteúdo → veredicto
  MULTIPLE_SCHEMES (REQ-005 §8), testado.

## Vermelho→verde: anti-drift pegou o subcomando novo `regent control explain` (teste
ensinado); fixture antiga de stop_request sem `reason` atualizada.

## Gates

PYTHONPATH=src python3 -m unittest discover -s tests → Ran 102 tests — OK (3 execuções)
bash scripts/gate-package.sh → 0.4.0 PASSED + gate-package: OK
