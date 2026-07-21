# PLAN-004 / STEP-01 — Hook confinante + cadeia autenticada + selo terminal

step_base_sha: bbb8d69 (baseline)
files_touched:
  - src/regent/conduction/hookscript.py (novo — hook standalone)
  - src/regent/conduction/turnlog.py (novo — verify_chain + attribute_changes)
  - tests/test_hookscript.py (novo, 15 testes)

## O que foi implementado

- Hook (semântica oficial): PreToolUse decide allow/deny (Write/Edit/MultiEdit/Notebook
  só dentro do envelope por REAL-PATH canônico — symlink/.. resolvidos; Bash e exec
  negados como defesa em profundidade; read-only allow); PostToolUse registra content_
  sha256 correlacionado por tool_use_id; falha FECHADA (erro → deny + hook_error).
- Cadeia: append sob flock, linha JSON canônica, seq monotônico, hmac encadeado
  (payload‖hmac_anterior). O HMAC é AUDITORIA (não anti-forja do agente — modelo de
  confiança do plano).
- verify_chain: recomputa a cadeia + exige SELO TERMINAL do supervisor (ausência = log
  truncado/removido). Detecta edição/remoção/injeção/reordenação/remoção-do-último.
- attribute_changes: a prova de fato (git) — implementada e usada no STEP-02.

## Gate (PYTHONPATH=src python3 -m unittest discover -s tests)

Ran 148 tests — OK (3 execuções). 15 novos incl. concorrência (4 procs × 10 appends =
40 eventos, seq 0..39 sem fork, cadeia verifica).
