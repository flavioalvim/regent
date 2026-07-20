# RODADA-002 — DECISÃO (2026-07-20)

**Resultado: APROVADO por consenso, sem arbitragem do dono.** Trajeto: Claude CONCORDO com a
premissa do dono → Codex DISCORDA (6 objeções) → réplica aceita as 6 → Codex re-opina
aceitando 4 e mantendo 2 residuais (semântica observável das consultas; contrato de saída de
`init`/`doctor`) → **Claude CONCEDE os 2 residuais definindo-os já no REQ-003** (abaixo).
Ambos os agentes concordam com a premissa do dono; divergências internas resolvidas por
convergência dentro do cap de rodadas.

## O que ficou decidido (REQ-003 no PRD)

1. **Runtime de execução = Claude Code CLI**, vínculo obrigatório e não-configurável no v1;
   **Codex = sempre Advisor** (read-only, nunca detém turno); **fluxo Codex→Claude proibido
   por requisito**. Ports executor/advisor são costura interna de extensão, sem superfície de
   configuração no v1.
2. Migra o **adapter unidirecional de consulta headless** (`--sandbox read-only`,
   `--ask-for-approval never`); NÃO migra o caminho de turno do Codex (`run_codex.py`,
   `$responda-claude`, identidade dual no lock).
3. Protocolo: mecanismo mutex/CAS preservado; **executor é o único detentor de turno**;
   mediador governa decisões/transições sem deter turno; consultas ao advisor = sub-passos
   do turno do executor.
4. **Semântica das consultas (residual 3 concedido):** desfechos terminais SUCCESS/TIMEOUT/
   FAILURE/CANCELLED; invariantes: turno inalterado durante a consulta; fail-closed (desfecho
   ≠SUCCESS nunca avança decisão que exija conselho); toda consulta persiste evidência
   (prompt integral, resposta integral ou saída parcial, exit code, timestamp, vínculo
   turno/rodada) sob `.regent/`; retomada = NOVA consulta evidenciada, nunca resume parcial.
   Máquina de estados detalhada fica para a rodada do protocolo.
5. **Contrato init/doctor (residual 5 concedido):** `regent init` = instalação/semeadura
   ATÔMICA — exit 0 só com semeadura completa; falha = exit ≠0 com rollback seguro, sem
   estado parcial; CLI de agente ausente = warning, não falha do init. `regent doctor` =
   diagnóstico de capacidades via sondas não-interativas seguras — exit 0 sse todas as
   capacidades utilizáveis; relatório estruturado por capacidade. Comando que exija
   capacidade indisponível falha com erro explícito nomeando a capacidade e apontando o
   doctor. Matriz comando×capacidade: rodada da interface CLI.
6. Critérios de aceitação testáveis: advisor nunca adquire turno; nenhum caminho aciona
   Claude do ambiente Codex; consulta sem evidência persistida falha; rollback do init não
   deixa estado parcial.

## Execução

- REQ-003 escrito no `docs/PRD.md` (descrição geral do produto ajustada para a assimetria).
- ESCOPO.md: supersessão explícita das passagens de deliberação simétrica/outros pares no
  v1/turno do Codex; inventário anotado.
