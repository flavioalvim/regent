# PLAN-005 — Pedido do dono (2026-07-21, verbatim)

> prossiga

Interpretação registrada: última fronteira anunciada — condução fase 3. Fatiamento
proposto: PLAN-005 entrega o LOOP DE TURNOS (`regent loop run`) que encadeia turnos
supervisionados automaticamente sobre um plano de build aprovado — decide o próximo STEP,
executa o turno (PLAN-004), para em conclusão/violação/gate-red/stop/cap — com `--abort`
real (cancelamento cooperativo do turno em voo). A daemonização em background contínua +
regras de ativação + ensaio ficam para um eventual PLAN-006 (declarado fora).
