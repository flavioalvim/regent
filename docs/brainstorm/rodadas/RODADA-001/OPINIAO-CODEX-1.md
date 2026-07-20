Concordo com o núcleo das duas requisições, mas discordo da resposta do Claude nestes pontos:

1. **A renomeação para `regent` não decorre de `.regent/`.** O nome técnico do diretório não obriga a troca da marca, CLI, import, repositório e pacote já fixados no `ESCOPO.md`. Além de ampliar indevidamente a rodada, a proposta piora a unidade nominal ao exigir PyPI `regent-cli`. Essa mudança precisa de decisão explícita do dono, não de refinamento implícito.

2. **“Fora dele, apenas ponteiros, nunca conteúdo” está factualmente incorreto.** Entradas em `.gitignore` e regras em `.claude/settings.local.json` são conteúdo gerenciado fora de `.regent/`, não ponteiros. O PRD deve chamá-las de integrações ou fragmentos gerenciados e definir marcação, detecção de conflito, atualização e remoção segura.

3. **A exceção XDG enfraquece o significado de “tudo”.** É razoável manter locks e estado efêmero fora do repositório, mas a regra precisa dizer expressamente: todo artefato persistente e compartilhável do projeto fica em `.regent/`; estado operacional local pode ficar em XDG. Ledgers que sejam evidência auditável não devem ser classificados automaticamente como efêmeros.

4. **A fronteira linguística ainda é inconsistente.** O PRD e a documentação do próprio Regent são conteúdo sobre o sistema, não conteúdo do projeto hospedado. Mantê-los em PT-BR contradiz tanto a formulação “inglês para arquivos do sistema” quanto a classificação proposta. Isso também altera a decisão anterior do `ESCOPO.md`, que fixava documentação Markdown em PT-BR, portanto exige uma revogação explícita. O PRD deve distinguir: artefatos e documentação do produto em inglês; texto produzido sobre o projeto host na língua nativa; campos estruturados sempre em inglês.

DISCORDA — 1, 2, 3, 4