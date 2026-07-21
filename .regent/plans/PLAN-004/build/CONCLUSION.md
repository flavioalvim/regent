# PLAN-004 / build — CONCLUSION

status: ACCEPTED-WITH-RESERVATIONS
actor: executor, per advisor verdict APROVADO COM RESSALVAS (ADVISOR-REVIEW-6, sem bloqueio
  no escopo da fase); owner mediating live
date: 2026-07-21

## Resultado

Condução fase 2 ENTREGUE (0.6.0): `regent turn run` — UM turno de produção com `claude -p`
CONFINADO. O agente só escreve dentro do envelope (hook PreToolUse deny, default-deny por
allowlist, real-path canônico, exec negado); a prova de atribuição é PELO GIT (diff global
== conjunto atribuído, blob sha256 + modo conferidos por evento post correlacionado a um
pre ALLOW, deleção/symlink-swap = violação); o commit é do SUPERVISOR por índice privado +
CAS de HEAD + fencing de token; o HMAC é auditoria (selo terminal, cadeia). Vínculo REQ-005
rígido (build ativo, STEP corrente calculado, gate do step, build canônico sob root real).
Stop honrado em toda fronteira + pré-commit incondicional (suspende, não commita). 183
testes verdes 3×; e2e real (TURN_OK commita; TURN_VIOLATION/GATE_RED/stop não commitam
produto).

## Marco: o funil adversarial em profundidade máxima

6 revisões finais, TODAS pelo próprio `regent advisor consult` (dogfood da fase 1):
REPROVADO ×4 (9+9+4+2 achados de segurança/correção/atribuição — o advisor derrubou a
premissa HMAC-como-anti-forja na revisão do PLANO, e depois escapes de symlink, laundering
de evidência de gate, deleção, bypass de current-step, exit não-zero, cobertura de stop) →
APROVADO COM RESSALVAS. 9 STEPs (4 planejados + 5 de correção). Cada reprovação estreitou;
a última só deixou ressalvas de fase 3.

## Ressalvas registradas (fase 3, declaradas)

daemon/loop contínuo, --abort real, ensaio, decisão automática de próximo turno; e a janela
teórica mínima entre o fencing e o update-ref (aceitável no contrato single-host atual).

## Rastreabilidade

Baseline `63728914`; trailers `Regent-Step: PLAN-004/STEP-0{1..9}`; evidência das 7
consultas (ADVISOR-REVIEW{,-2..6}.md + prompts) geradas pelo próprio regent advisor consult.
