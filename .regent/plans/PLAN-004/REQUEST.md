# PLAN-004 — Pedido do dono (2026-07-21, verbatim)

> prossiga

Interpretação registrada (contexto): próxima fronteira anunciada e aceita — **condução
fase 2: o executor confinado**. Fatiamento: PLAN-004 entrega o TURNO SUPERVISIONADO
(`regent turn run`): lançar um `claude -p` CONFINADO (composição privada de settings +
hooks PreToolUse/PostToolUse com segredo HMAC por turno, sem Bash, escrita restrita ao
envelope declarado — o desenho provado no LOTE-02 da IMP-003), verificar o log de eventos
autenticado, rodar o gate mecanizado e commitar PELO SUPERVISOR. O loop/daemon completo
(agendamento, decisão de próximo turno, --abort, ensaio) fica para a fase 3.
