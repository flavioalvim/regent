# PLAN-002 / build — CONCLUSION

status: ACCEPTED-WITH-RESERVATIONS
actor: executor, per advisor verdict APROVADO COM RESSALVAS (ADVISOR-REVIEW-4); owner
  mediating live (veto aberto)
date: 2026-07-21

## Resultado

Skills v1 control-backed ENTREGUES: camada de aplicação `activity.py` (operações compostas
serializadas sob ops flock, tabela de recuperação de 12 linhas, guards de corrida),
subcomandos CLI com contrato JSON fechado (status com matriz executável
`workspace.verdict`, activity start/resume/suspend/conclude/heartbeat/takeover, stop
request/check com reason, `control explain --since-version` com contabilidade de
transição casada), upgrade v0→v1 por manifesto (com journal, escapes de symlink
bloqueados), skills reescritas dirigindo o CLI. Versão **0.4.0**. **109 testes verdes 3×,
gate-package OK, e2e real registrado** (host novo + upgrade v0.2 genuíno + ciclo completo
com stop honrado).

Trajeto adversarial: 4 revisões finais (TIMEOUT registrado + REPROVADO ×3 → APROVADO COM
RESSALVAS), 8 etapas (5 planejadas + 3 de correção). Bloqueantes fechados no caminho:
corrida de composição (ops flock), atribuibilidade default-deny com contabilidade exata
por transição casada.

## Ressalvas registradas

1. BAIXO (diagnóstico): no rollback do init, falha de `.regent.rmdir()` com journal já
   removido atribui o caminho errado na mensagem (initcmd.py:180) — corrigir no próximo
   turno de manutenção.
2. Já aceitas como desenho: flock single-host; daemon/`--abort` = fases futuras;
   atomicidade de instalação por-arquivo + journal + re-run convergente.

## Rastreabilidade

Baseline `af59ca6` (BASELINE.md); diff aceito = `af59ca6..HEAD`; trailers
`Regent-Step: PLAN-002/STEP-0{1..8}`; evidência integral das 5 consultas
(ADVISOR-REVIEW-T1/-1..4 + prompts) com cabeçalhos REQ-003 §5.
