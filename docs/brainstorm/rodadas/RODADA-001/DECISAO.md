# RODADA-001 — DECISÃO (2026-07-20)

**Resultado: APROVADO por consenso após 1 réplica** (Codex: DISCORDA na opinião 1 →
CONCORDA na opinião 2 sobre a formulação consolidada) **+ ratificação do dono** nos 2 itens
que subiram para ele.

## O que ficou decidido (vira REQ no PRD)

1. **REQ-001 — raiz `.regent/`:** todo artefato do sistema regent no projeto host vive sob
   `.regent/`. Fora dele, apenas **managed integrations** (fragmentos gerenciados: symlinks
   `.claude/skills/*`, regras em `.claude/settings.local.json`, entradas de `.gitignore`) com
   marcação delimitada, detecção de conflito, atualização idempotente e remoção segura.
   Persistente/compartilhável (inclusive ledgers/evidência auditável) = `.regent/`;
   XDG = só estado operacional local descartável (locks, caches).
2. **REQ-002 — política de idioma em 3 camadas:** (i) sistema e produto — inglês (código,
   layout de `.regent/`, chaves/estados, templates, CLI, documentação do produto incl. PRD);
   (ii) deliberação — língua do mediador (configurável; PT-BR aqui); (iii) projeto hospedado —
   língua nativa do host (configurada em `.regent/config`).
3. **Nome do produto: `regent`** (ratificado pelo dono): repo `flavioalvim/regent`, CLI e
   import `regent`, diretório `.regent/`, pacote PyPI `regent-cli` (quando publicar).
4. **Revogação parcial ratificada:** a decisão do ESCOPO "documentação em PT-BR" deixa de
   valer para docs do PRODUTO (nascem em inglês; ESCOPO/REGRAS migram quando reescritos, sem
   big-bang). Rodadas de brainstorm permanecem em PT-BR.

## Execução

- Repo renomeado `regente`→`regent` (GitHub + diretório local `~/projetos/regent`).
- `docs/PRD.md` criado em inglês com REQ-001/REQ-002 e o registro do nome.
- README reescrito em inglês; ESCOPO.md anotado com as supersessões desta rodada.
