Concordo com a decisão estratégica do dono, mas a formulação de REQ-003 ainda deixa lacunas normativas relevantes:

1. **A direção de controle não foi formalizada.** No v1, o vínculo `Executor = Claude Code` deve ser obrigatório, não apenas uma configuração substituível. O requisito também deve proibir explicitamente qualquer fluxo Codex→Claude. Ports podem existir como extensão interna futura, mas a configuração v1 não deve aceitar outro executor.

2. **A exclusão de `run_codex.py` está mal definida.** O v1 ainda precisa de um adapter unidirecional para consultar o Codex. Deve ficar claro se esse script será refatorado ou substituído; o que deve ser removido é o caminho em que Codex atua como executor ou detentor de turno, não necessariamente o mecanismo de invocação headless.

3. **O protocolo não “continua igual”.** Retirar a identidade dual altera atores autorizados, estados, CAS, recuperação e invariantes do lock. O executor deve ser o único agente que pode deter o turno; o mediador controla decisões/transições, mas não deveria ser apresentado automaticamente como detentor equivalente. Consultas ao advisor precisam de estados e comportamento definidos para timeout, falha, cancelamento e retomada.

4. **“Read-only” e “evidência” precisam de contratos verificáveis.** A proibição de escrita deve ser delimitada ao host e aos artefatos do regent, pois o Codex CLI pode manter estado próprio fora do repositório. A invocação deve impor sandbox read-only e ausência de aprovação, e a evidência deve registrar ao menos prompt integral, resposta integral, status/exit code, horário e vínculo com turno/rodada, persistidos sob `.regent/`.

5. **A degradação sem Codex está subespecificada.** É necessário definir quais comandos continuam disponíveis, quais bloqueiam e qual status o `init` retorna. Verificar apenas a presença do Codex é insuficiente: um CLI instalado mas não utilizável/autenticado falhará na primeira consulta. Convém separar instalação (`init`) de diagnóstico de capacidades (`doctor`), ou definir testes não interativos seguros para ambos os CLIs.

6. **A execução documental proposta é insuficiente.** Não basta anotar o inventário do `ESCOPO.md`: devem ser supersedidas explicitamente as passagens que ainda descrevem deliberação Claude×Codex simétrica, outros pares configuráveis no v1 e turnos de ambos. O PRD também deve refletir a assimetria em sua descrição geral e exigir testes que demonstrem que Codex não adquire turno nem aciona Claude.

DISCORDA