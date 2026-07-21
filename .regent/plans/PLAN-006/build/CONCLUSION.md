# PLAN-006 — CONCLUSÃO do build (condução fase 4)

- **status:** APROVADO COM RESSALVAS
- **ator:** condução dogfood (executor Claude Fable 5 + conselheiro Codex), mediada.
- **base:** 56592563811c18b87cf8473c8726a2ab4b76ce7a → HEAD
- **versão:** 0.8.0
- **gates:** suíte completa 259 OK (3×); `scripts/gate-package.sh` (build 0.8.0 +
  `twine check --strict`) OK; e2e real (fake-claude pela CLI: arm → daemon --once
  dirige STEP-01+STEP-02 → STEPS_COMPLETE → desarma, atividade permanece ACTIVE).

## Entregue (STEP-01..04)
- **STEP-01** — `supervisor.rehearse` (read-only) + arm/disarm durável (arm-token
  vinculado a plano/epoch/token; flock; CAS por arm_id; barreira de durabilidade).
- **STEP-02** — `supervisor.run_daemon` (foreground): nunca age sem arm válido;
  guard revalida sinal/CONCLUSION.md/APPROVED/binding; toda condição terminal
  desarma; COMPLETE→STEPS_COMPLETE (conclusão MEDIADA, não do daemon).
- **STEP-03** — CLI `rehearse|arm|disarm|daemon` (JSON, exit codes, streaming).
- **STEP-04** — consolidação 0.8.0: skill de build (via hands-off supervisionada),
  anti-drift, manifest, e2e real.

## Revisão adversarial (dogfood mecanizado — 6 rodadas)
`regent advisor consult` conduziu 6 rodadas; 12 achados REAIS de correção/
segurança/recuperação incorporados, um teste dirigido por achado
(ADVISOR-REVIEW-{1..5}-FIXES.md):
1. flock + CAS atômico + fsync do dir na remoção do arm-token;
2. guard barra INICIAR se CONCLUSION.md presente;
3. guard imediatamente antes de run_turn (+ launch_precondition antes do spawn);
4. validação/canonização da config no arm; run_daemon desarma em QUALQUER exceção;
5. exit codes + streaming JSON por transição;
6. `_unlink_durable` propaga falha; disarm nunca reporta sucesso falso;
7. guard revalida APPROVED;
8. config canônica absoluta (independe do CWD);
9. emit() não deixa exceção de streaming escapar;
10. todos os terminais confirmam o desarme (DISARM_FAILED se persistir);
11. IDLE roda a barreira de durabilidade (_confirm_absent_durable);
12. read_arm valida o esquema do token (fecha KeyError do daemon).

## Ressalva (fronteira DECLARADA — FASE 5)
A linearização TOTAL da janela guard→spawn exige separar `spawn` de `wait` no
runner (senão o lock ficaria retido por todo o turno, bloqueando o próprio
desarme). Isso é a arquitetura do daemon em BACKGROUND, declarada FORA DE ESCOPO
no PLAN-006 (Escopo: "Fora (fase 5, declarada)"). O contrato do PLAN já estabelece
que o turno EM VOO é responsabilidade da via de abort; o guard só barra INICIAR o
próximo. O `launch_precondition` reduz a janela a microssegundos SEM I/O
interposto. O revisor aceitou esta fronteira nas rodadas 2–4 e 6.

## Decisão pendente do DONO (mediada)
Este arquivo registra STEPs feitos + build aceito COM RESSALVAS pelo conselheiro.
A conclusão FORMAL da atividade (`regent activity conclude`) e a decisão de aceitar
a ressalva de FASE 5 permanecem do DONO. A fase 5 (daemon background desanexado,
ativação automática, notificações, linearização total) é o próximo plano (PLAN-007).
