A formulação consolidada resolve adequadamente as sete objeções:

- define canais operacionais viáveis e limitações do modo interativo;
- estabelece protocolo idempotente de parada e recuperação;
- separa estado da atividade de desfecho da consulta;
- fixa precedência determinística dos comandos;
- mantém skills canônicas em `.regent/skills/`, usando symlinks gerenciados;
- restringe honestamente as capacidades da v0 file-driven;
- separa suspensão durável de commit Git, tratando o commit como tentativa não bloqueante.

Os detalhes remetidos às futuras rodadas de protocolo e CLI são refinamentos compatíveis com o REQ-004, não lacunas que impeçam sua criação.

CONCORDA