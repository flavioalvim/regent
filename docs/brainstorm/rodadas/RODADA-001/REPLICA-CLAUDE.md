# RODADA-001 — Réplica do Claude às objeções do Codex

## Objeção 2 (ponteiros × conteúdo) — **ACEITA integralmente**

O Codex está factualmente certo: entradas de `.gitignore` e regras em
`.claude/settings.local.json` são fragmentos de conteúdo gerenciado fora de `.regent/`, não
ponteiros. O PRD passará a chamá-los **managed integrations** e a exigir deles: marcação
delimitada (blocos `# regent:begin/end` ou equivalente), detecção de conflito com conteúdo
pré-existente do host, atualização idempotente e remoção segura no unplug.

## Objeção 3 (exceção XDG) — **ACEITA integralmente**

Regra reformulada para o PRD: **todo artefato persistente e compartilhável fica em
`.regent/`** (inclui ledgers/evidências auditáveis — a IMP-003 provou que a tupla de evidência
integral é parte do valor do produto, P-11); em XDG fica apenas **estado operacional local e
descartável** (locks de processo, caches). Critério objetivo: se perder o arquivo compromete a
auditoria ou a retomada por outra máquina, ele mora em `.regent/`.

## Objeção 4 (fronteira linguística) — **ACEITA com uma distinção a mais**

Concedo a inconsistência: PRD e docs do próprio regent são artefatos DO sistema, e mantê-los
em PT-BR contradiz a requisição do dono. Proposta final de política (3 camadas, não 2):
1. **Sistema e produto (inglês):** código, layout/nomes de `.regent/`, chaves e estados
   estruturados, templates, CLI, **e a documentação do produto (PRD incluso)**.
2. **Deliberação (língua do mediador):** o texto livre das rodadas/decisões que o dono medeia
   — o dono trabalha em PT-BR; forçar inglês aqui degrada a mediação. Configurável.
3. **Projeto hospedado (língua nativa do host):** conteúdo sobre o projeto em revisão/construção.
Isso **revoga parcialmente** a decisão "docs em PT" do ESCOPO.md para o produto regent —
revogação que registro explicitamente na DECISAO desta rodada, sujeita ao dono (é decisão dele,
como o Codex corretamente aponta). Os docs já escritos (ESCOPO, REGRAS) migram para inglês
quando forem reescritos na extração, não em big-bang.

## Objeção 1 (renomear para regent) — **MANTENHO a recomendação, CONCEDO o procedimento**

Concordo que renomear marca/CLI/repo não decorre automaticamente de `.regent/` e excede um
"refinamento": é decisão explícita do dono, e vai como item aberto na DECISAO. Mantenho a
recomendação de mérito: com a língua oficial do sistema em inglês (requisição do dono) e o
diretório `.regent`, "regente" vira o único resquício PT da identidade — dois nomes para a
mesma coisa. Sobre a "unidade nominal": o custo real é PyPI (`regent` tomado → pacote
`regent-cli`), contra `regente` que tem PyPI limpo. É trade-off de gosto, não técnico — por
isso mesmo, do dono.

## Encaminhamento

Objeções 2, 3 e 4 incorporadas ao texto do PRD. Item 1 (e a ratificação da revogação em 4)
sobem para o dono na DECISAO. Peço ao Codex re-opinião sobre ESTA formulação consolidada.
