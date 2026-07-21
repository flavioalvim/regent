# PLAN-003 — Pedido do dono (2026-07-21, verbatim)

> siga para proxima fase

Interpretação registrada (contexto): com PLAN-001 (protocolo) e PLAN-002 (skills
control-backed) concluídos e a 0.4.0 publicada, a próxima fase declarada é a CONDUÇÃO.
Fatiamento proposto: **PLAN-003 = condução fase 1 — mecanizar os dois sub-passos mais
repetitivos e sujeitos a erro do loop como comandos com evidência automática**: a consulta
ao advisor (`regent advisor consult`, portando o CodexConsultAdapter provado na IMP-003
com a tupla REQ-003 §5 automatizada) e o gate de testes (`regent gate run`). O daemon com
executor confinado (hooks HMAC) fica para a fase 2 da condução (plano futuro).
