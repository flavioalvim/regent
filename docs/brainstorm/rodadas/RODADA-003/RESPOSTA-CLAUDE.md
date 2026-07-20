# RODADA-003 — Resposta do Claude

**Proposta: dois comandos, um de entrada única dirigida por estado e um de parada segura.**
A chave é que "acionar" NÃO deve exigir que o dono diga o que está em andamento — o sistema
sabe. É o padrão já provado pela skill `continuar` do ArtNFT: uma entrada única que detecta o
estado e retoma a atividade certa (brainstorm, planejamento ou implantação).

## `/regent` — acionar/retomar (entrada única, dirigida por estado)

- Lê o estado (`.regent/control.json` quando extraído; hoje, os artefatos de
  `docs/brainstorm/`) e **retoma o que estiver aberto**: rodada de brainstorm pendente,
  plano em curso, lote de implantação ativo.
- Se nada está aberto: `/regent brainstorm "<pergunta>"` | `/regent plan` | `/regent build`
  iniciam a atividade; `/regent` sem argumento reporta o estado e pergunta o que iniciar.
- Nunca adivinha: se o estado está ambíguo/corrompido, reporta e para (default-deny, P-03).

## `/regent-stop` — parada segura (nunca perde evidência)

- **Default = parada graciosa em fronteira consistente:** termina o sub-passo corrente
  (ex.: consulta ao advisor em andamento), persiste evidência, marca o estado como
  `SUSPENDED` no controle, libera o lock, commita. Sempre retomável por `/regent`.
- **`/regent-stop --abort` = cancelamento imediato:** consulta em voo vira `CANCELLED`
  (REQ-003 §5 — desfecho terminal COM evidência), estado `SUSPENDED`, lock liberado.
- Com daemon/loop em background: o stop grava uma **solicitação de parada** que o supervisor
  honra na próxima fronteira (mecânica já existente na condução da IMP-003); o comando espera
  a confirmação e reporta onde parou.
- Invariantes: nenhum desfecho perde evidência; o lock nunca fica retido; `SUSPENDED` guarda
  o ponto de retomada.

## Por que 2 comandos e não 6

Um par acionar/parar por atividade (`/brainstorm-start`, `/plan-stop`…) multiplicaria
superfície e criaria o erro "parei a atividade errada". Estado é um só; o par único
opera sobre ele. Os modos são argumento do `/regent`, não comandos.

## Enquadramento no produto

- Vira **REQ-004**: os dois comandos são a interface de controle de atividade no Claude Code,
  semeados pelo `regent init` como managed integrations (REQ-001 §2), nomes e conteúdo em
  inglês (REQ-002), operando sob os papéis do REQ-003 (o comando roda no executor; parar
  jamais depende do advisor).
- **Execução imediata (dogfood-lite):** criar as duas skills JÁ no repo regent
  (`.claude/skills/regent/` e `.claude/skills/regent-stop/`) codificando a fase atual
  (o loop de brainstorm das REGRAS.md), para o dono usar hoje; elas evoluem junto com a
  extração até serem as versões semeadas pelo init.

## Execução proposta (se houver concordância)

1. REQ-004 no PRD (interface de controle de atividade: `/regent` + `/regent-stop`).
2. Skills criadas no repo regent cobrindo o loop de brainstorm atual.
3. Fechar a rodada.
