# RODADA-001 — Resposta do Claude

**Veredicto: CONCORDO** com as duas requisições, com 3 refinamentos que proponho incorporar
ao PRD junto com elas.

## Sobre a requisição 1 — tudo do regent debaixo de `.regent/`

Concordo e considero a decisão estruturalmente correta: hoje os artefatos da ferramenta se
espalham pelo host (`docs/brainstorm-mvp/`, `scripts/`, symlinks `.claude/skills/*`, regras em
settings). Um único diretório-raiz `.regent/` no host (padrão `.git`/`.github`/`.claude`) torna
o plug/unplug limpo, o `regent init` idempotente e o diff de adoção auditável num único prefixo.

**Refinamento (a) — exceções documentadas como "managed pointers":** nem tudo *pode* fisicamente
morar em `.regent/`. Pontos de integração que os agentes exigem em caminhos próprios:
- `.claude/skills/*` → symlinks PARA dentro de `.regent/skills/` (o init cria/verifica);
- regras de ativação em `.claude/settings.local.json` (o init semeia/verifica);
- entradas de `.gitignore` do host.
Regra do PRD: `.regent/` é o lar canônico de TODO artefato do sistema; fora dele existem apenas
ponteiros gerenciados pelo `init`, nunca conteúdo.

**Esboço de layout** (detalhar em rodada própria): `.regent/config.*` (idioma nativo, paths,
agentes), `.regent/control.json` (CAS), `.regent/scope/`, `.regent/imps/<IMP>/`,
`.regent/rounds/`, `.regent/skills/`. Estado de máquina (locks/ledgers locais) permanece FORA
do repo (XDG `regent/<slug>`), como hoje.

## Sobre a requisição 2 — inglês no sistema, língua nativa no projeto

Concordo, e proponho tornar precisa a fronteira:

**Refinamento (b) — a fronteira é sistema×conteúdo, não arquivo×arquivo:**
- **Camada SISTEMA (inglês, sempre):** código, nomes de arquivo e diretório do `.regent/`,
  chaves/estados/valores de JSON (ex.: `control.json` com `state: BATCH_FROZEN`), nomes de
  skills, templates, mensagens do CLI. É o que hoje já decidimos migrar (CONTROLE→control,
  ESCOPO→scope, LOTE→batch, RODADA→round…).
- **Camada CONTEÚDO (língua nativa do host, configurável):** o texto livre dentro dos
  artefatos — perguntas, respostas, opiniões, PRD do projeto hospedado, decisões. Declarada em
  `.regent/config` (ex.: `native_language: pt-BR`), usada pelos agentes nas deliberações.
Sem essa fronteira explícita, arquivos mistos (JSON com chaves EN e textos PT) virariam zona
cinzenta e cada agente resolveria de um jeito.

## Refinamento (c) — coerência de nome: o produto vira **regent**

A requisição fixa `.regent` (EN) como identidade do sistema. Manter o produto batizado
"regente" (PT) com diretório `.regent` cria dois nomes para a mesma coisa. Proponho renomear o
produto para **regent**: repo GitHub `flavioalvim/regent` (livre, verificado 2026-07-20), CLI e
import `regent`, pacote PyPI `regent-cli` (livre; `regent` puro está tomado). Documentação do
produto continua em PT-BR (decisão anterior mantida — docs são conteúdo, não sistema).

## Execução proposta (se houver concordância)

1. Renomear repo/paths para `regent`; ajustar README/ESCOPO.
2. Criar `docs/PRD.md` do produto com REQ-001 (raiz `.regent/` + managed pointers),
   REQ-002 (política de idioma sistema×conteúdo) e o registro do nome.
3. Fechar a rodada (DECISAO.md + commit).
