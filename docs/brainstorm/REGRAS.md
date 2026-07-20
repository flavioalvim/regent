# Brainstorm adversarial — regras do loop (regente)

Definido pelo dono em 2026-07-20. Modo híbrido da extração: deliberação adversarial ao vivo,
execução livre (sem trilha/protocolo completo).

## O loop

1. **Dono pergunta** (uma questão de desenho/escopo por rodada).
2. **Claude responde** — posição fundamentada, com proposta concreta.
3. **Codex dá opinião** — consulta headless read-only sobre a pergunta + resposta do Claude
   (comando abaixo). Veredicto explícito: **CONCORDA** ou **DISCORDA** (com objeções).
4. **Se CONCORDA** → Claude executa a proposta.
5. **Se DISCORDA** → mais UMA rodada: Claude replica às objeções, Codex re-opina.
   Persistindo a divergência após a réplica, o **dono arbitra** (ele está presente mediando).

## Artefatos por rodada

`docs/brainstorm/rodadas/RODADA-NNN/`:
- `PERGUNTA.md` — a pergunta do dono, verbatim.
- `RESPOSTA-CLAUDE.md` — posição + proposta.
- `OPINIAO-CODEX-1.md` — última mensagem do codex, integral (evidência).
- `REPLICA-CLAUDE.md` + `OPINIAO-CODEX-2.md` — só se houve DISCORDA.
- `DECISAO.md` — o que ficou decidido, quem fechou (consenso/arbitragem) e o que foi executado.

Rodada fechada = commit na main do regente.

## Invocação do Codex (a mesma da camada de condução do ArtNFT)

```bash
codex --ask-for-approval never --sandbox read-only exec \
  --cd ~/projetos/regente -o /tmp/<msg>.txt "<prompt>"
```

O prompt instrui o Codex a ler `docs/ESCOPO.md` + os arquivos da rodada corrente e a terminar
com veredicto `CONCORDA` ou `DISCORDA` seguido das objeções. Read-only: o Codex nunca escreve
no repo; quem registra a opinião nos artefatos é o Claude (cópia integral, sem edição).
