# ESCOPO — regent v1

> ⚠️ **Supersessões (RODADA-001, 2026-07-20, ver `docs/PRD.md`):** nome do produto agora é
> **regent** (repo `flavioalvim/regent`, CLI `regent`, PyPI `regent-cli`, raiz no host
> `.regent/`); documentação do PRODUTO passa a nascer em inglês (revogação parcial ratificada
> pelo dono — este arquivo migra quando for reescrito); política de idioma completa = REQ-002.
>
> ⚠️ **Supersessões (RODADA-002, 2026-07-20, REQ-003):** runtime de execução = **Claude Code
> CLI** (obrigatório, não-configurável no v1); **Codex = sempre Advisor** (read-only, nunca
> detém turno; fluxo Codex→Claude proibido). Onde este arquivo descreve deliberação
> Claude×Codex **simétrica**, turno do Codex ou "outros pares" como opção de v1, vale o
> REQ-003: do inventário da camada DELIBERAÇÃO/CONDUÇÃO, **não migram** `run_codex.py`, a
> skill `$responda-claude` e a identidade dual `AGENTS=("claude","codex")` no turn lock;
> **migra** o adapter unidirecional de consulta headless (`CodexConsultAdapter`). Ports
> executor/advisor ficam como costura interna, sem configuração exposta.

Fechado com o dono em 2026-07-20. Este documento é a referência da extração: o que o
produto é, o que sai do ArtNFT, o que se corrige no caminho e o que fica para depois.

## Decisões estruturais (batidas com o dono)

| Decisão | Escolha |
|---|---|
| Nome | **regente** (PyPI e GitHub livres em 2026-07-20; CLI `regente`) |
| Distribuição | Repo próprio + pacote Python instalável (pip/pipx) com comando `regente init` que semeia os artefatos no projeto host |
| Escopo v1 | As **três camadas juntas** (deliberação + protocolo + condução), com o protocolo como núcleo e módulos separáveis — sem split em pacotes por ora |
| Trilha da extração | **Repo novo sem trilha** (velocidade); o 1º dogfood real será uma IMP conduzida dentro do próprio regente, depois que o `init` existir |
| Idioma | Código **100% inglês** (identificadores migram na extração, com testes garantindo equivalência); documentação markdown em PT-BR |
| Licença | **Nenhuma por ora** — repo privado, todos os direitos reservados; licença aberta só se/quando publicar |
| Repo | `~/projetos/regente`, GitHub privado `flavioalvim/regente` |

Nomes considerados e descartados: `baton`/`baton-cli`/`batuta`/`maestro-loop` (tomados no
PyPI). Livres além de regente: condutor, turnlock, turnkeeper, revezo, estafeta.

## O ativo a extrair (fonte: repo ArtNFT, `docs/brainstorm-mvp/` e `skills/`)

### Camada PROTOCOLO (núcleo)
- `scripts/turn_lock.py` + `control_domain.py` — mutex atômico de turno + CAS do `CONTROLE.json`.
- IMP-000 (protocolo congelado) + EMENDAS 001/002/003 (severidade de findings, rodadas de
  fechamento, modo Claude-decide/Codex-aconselha com cap de 4 rodadas — exercido ao vivo na IMP-003).

### Camada DELIBERAÇÃO
- Rodadas Claude×Codex mediadas pelo dono: skills `responda-codex`/`$responda-claude`,
  `REGRAS.md`, `PROPOSTA-DE-CONSENSO`/`ACEITE`s versionados, `find_next.py`.

### Camada CONDUÇÃO
- `skills/continuar/`: `supervisor_{domain,adapters,confinement,loop,decision,activation,daemon,daemon_domain}.py`
  + `plano_producao.py` (plano de turno de produção: agente confinado com hooks HMAC, gate de
  testes, prova de 6 pontos, revisor headless).
- Suítes: 343 testes / 10 suítes + ensaio opt-in.
- Motor `skills/continuar-artnft/`: `lote_domain` (parsers de ESCOPO/LOTE/ETAPAS, subset checker).

### Mediações que viram correções de 1ª classe (hoje são wrapper de runtime no ArtNFT)
P-05 `sys.modules` no load · P-06 observabilidade (final_message/rc/gate no ledger) ·
P-07 `attributed_set` last-write-wins · P-08 governança×`write_exact` na correção ·
P-09 canal de feedback do mediador · P-10 ratificação de commits do mediador na semeadura ·
P-11 tupla com evidência integral · P-01 acquire sem mutação não-commitada ·
P-03 default-deny · P-04 consolidação de suítes.

## Acoplamentos a desfazer (agnosticismo)

1. Paths fixos `docs/brainstorm-mvp/implementacoes/<IMP>/` e premissa repo=cwd → raiz de
   artefatos configurável pelo `init`.
2. Prefixo de env `ARTNFT_*` (`PLANO_PROCESSO`, `PRODUCAO_TIMEOUT_*`, `ENSAIO_PRODUCAO`) →
   prefixo `REGENTE_*`.
3. State dir XDG `continuar/<slug>` → `regente/<slug>`.
4. Regras de ativação em `.claude/settings.local.json` (3 regras do dono) + CLIs `claude`/`codex`
   presentes na máquina → documentar como pré-requisitos; `init` verifica e orienta.
5. Exigência de `.gitignore` do repo host cobrir settings locais (o git hermético ignora config
   global) → `init` semeia/verifica as entradas.
6. Tokens de gate mapeados a alvos do Makefile por LOTE (já genérico: token→comando no LOTE.md)
   → manter o contrato token→comando, sem premissa de Makefile.
7. Symlinks `.claude/skills/*` → o `init` cria/gerencia.
8. Identificadores PT (`plano_producao`, `lote_domain`, ESCOPO/LOTE/CONTROLE) → inglês; o
   vocabulário de artefatos do host também migra (mapa de renomes a produzir na extração).

## Interface de plug (v1, esboço)

`regente init` num repo host: semeia CONTROLE/ESCOPO iniciais + skills (symlinks ou cópia) +
entradas de `.gitignore` + verificação de pré-requisitos (CLIs dos agentes, settings de
ativação). O host guarda só dados/config; o código vive no pacote instalado.

## Fora do v1

- Split em pacotes separados por camada (só se houver demanda).
- Outros pares de agentes além de Claude×Codex (o desenho deve permitir, sem implementar).
- Publicação no PyPI e escolha de licença.
- Tradução da documentação para inglês.

## Próximos passos

1. Desenhar a árvore do pacote (`src/regente/…`) e o mapa de renomes PT→EN.
2. Extrair camada PROTOCOLO com suítes verdes no repo novo.
3. Extrair CONDUÇÃO + DELIBERAÇÃO, incorporando P-01..P-11 como 1ª classe.
4. Implementar `regente init` e validar plugando num repo de teste.
5. Dogfood: 1ª IMP conduzida pelo próprio regente.
