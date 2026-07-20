# RODADA-002 — Resposta do Claude

**Veredicto: CONCORDO.** A requisição descreve o que a IMP-003 já provou na prática: a
condução rodou inteira no Claude Code (daemon supervisionando `claude -p` confinado com hooks
HMAC) e o Codex participou como revisor headless read-only (`codex exec --sandbox read-only`),
no modo Claude-decide/Codex-aconselha da EMENDA-003. Formalizar isso como requisito elimina a
metade simétrica do modelo de agentes, que era a parte menos usada e mais cara de manter.

Proponho registrar como **REQ-003 — papéis de agente e runtime de execução**, com 4 pontos:

## (a) Dois papéis formais: Executor e Advisor

- **Executor** = quem detém o turno de trabalho, escreve no repo e roda a condução. No v1,
  vinculado ao **Claude Code CLI** (skills, hooks PreToolUse/PostToolUse, settings — as
  managed integrations do REQ-001 são as do Claude Code).
- **Advisor** = consultado pelo executor ou pelo mediador; roda **sempre read-only, nunca
  detém turno, nunca escreve**. No v1, **Codex CLI** headless. Toda consulta vira evidência
  registrada (a mensagem integral, como nas rodadas deste brainstorm).

## (b) Papéis como abstração (ports), vínculos como configuração

O "pelo menos por hora" do dono vira barato de revisitar: `executor` e `advisor` são ports;
Claude Code e Codex são os adapters v1. Reverter, trocar ou adicionar conselheiros no futuro é
configuração/adapter novo, não redesenho — coerente com o ESCOPO ("outros pares de agentes:
o desenho deve permitir, sem implementar").

## (c) Consequência de extração: o maquinário simétrico NÃO migra

Simplificação concreta: `run_codex.py`, skill `$responda-claude`, a identidade dual
`AGENTS = ("claude", "codex")` no turn lock e os estados de turno em que o Codex é agente
pleno **ficam fora do v1**. O modelo de turnos vira **mediador ↔ executor**, com consultas ao
advisor como sub-passos evidenciados do turno — não turnos próprios. O protocolo (mutex/CAS)
continua igual; só encolhe o conjunto de detentores de turno.

## (d) Pré-requisitos de runtime verificados pelo `regent init`

`regent init` passa a verificar: Claude Code CLI presente e autenticado (runtime de execução)
e Codex CLI presente (advisor). Sem Codex, o sistema degrada explicitamente (sem conselho,
modos que exigem revisão adversarial bloqueiam) — nunca silenciosamente.

## Execução proposta (se houver concordância)

Adicionar REQ-003 ao PRD (com os 4 pontos acima), atualizar a tabela de requisitos e anotar
no ESCOPO.md que o inventário de extração exclui o maquinário simétrico. Fechar a rodada.
