# RODADA-003 — DECISÃO (2026-07-20)

**Resultado: APROVADO por consenso.** Trajeto: proposta do Claude (2 comandos: entrada única
dirigida por estado + parada segura) → Codex DISCORDA (7 objeções: modelo operacional do
stop, atomicidade, modelo de estados, matriz estado×comando, dogfood×REQ-001, honestidade da
v0, política de commit) → réplica aceita as 7 com definições concretas → Codex **CONCORDA**
("resolve adequadamente as sete objeções"). Sem arbitragem do dono.

## O que ficou decidido (REQ-004 no PRD)

- **`/regent`**: entrada única dirigida por estado (retoma o que está aberto; modos como
  argumento; regras de precedência normativas; default-deny em ambiguidade; nunca inicia
  implicitamente nem ignora argumento em silêncio).
- **`/regent-stop`**: canal = stop-request durável no controle (CAS), honrado pelo daemon em
  fronteira (`--abort` mata consulta em voo → `CANCELLED`); em sessão interativa, normaliza
  na fronteira seguinte (interrupção imediata é o Esc do Claude Code); sequência canônica de
  7 passos idempotentes; `SUSPENDED` com payload obrigatório de retomada; commit não-bloqueante
  só de paths do regent.
- **Esclarecimento no REQ-001**: em symlinks, o marcador de ownership é o alvo apontar para
  dentro de `.regent/`.
- **v0 dogfood criada nesta rodada**: skills canônicas em `.regent/skills/{regent,regent-stop}/`
  com symlinks em `.claude/skills/` (instalação manual = o que o `init` automatizará),
  capability level v0 (file-driven) declarado no texto.

## Execução

- REQ-004 escrito no PRD; tabela de requisitos atualizada; REQ-001 §2 esclarecido.
- Skills v0 criadas e linkadas no repo regent — utilizáveis numa sessão Claude Code aberta
  em `~/projetos/regent` (`/regent`, `/regent-stop`).
