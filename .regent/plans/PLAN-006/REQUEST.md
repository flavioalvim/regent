# PLAN-006 — Pedido do dono (2026-07-21, verbatim)

> prossiga

Interpretação registrada: fase 4 (última fronteira da condução). Fatiamento proposto:
PLAN-006 entrega o SUPERVISOR com três capacidades — (1) ENSAIO (`regent rehearse`): prevê
os turnos que o loop faria (STEPs, gates) SEM lançar agentes; (2) ATIVAÇÃO explícita
(`regent arm`/`disarm`): um gate de segurança durável — o daemon SÓ age sobre um plano
ARMADO pelo dono (nunca inicia trabalho autônomo sem armar); (3) DAEMON (`regent daemon
run`): loop supervisor em PRIMEIRO PLANO que, enquanto armado, dirige builds aprovados até
conclusão (via loop run), um por vez, respeitando stop/abort/desarme. A daemonização em
BACKGROUND desanexada (processo detached, PID file, logs persistentes) fica para um
eventual PLAN-007 (declarado fora) por ser a parte mais arriscada.
