Revisor adversarial (Codex) do regent — RE-REVISÃO do BUILD do PLAN-006 (condução fase 4),
6ª rodada. Rodada 5: 2 bloqueadores + 1 alto. #1 (IDLE contornava a durabilidade) e #3
(read_arm sem validar esquema) eram defeitos claros — CORRIGIDOS. #2 (linearização total
guard→lançamento) foi MITIGADO ao limite prático. Ver
.regent/plans/PLAN-006/build/ADVISOR-REVIEW-5-FIXES.md. MÁXIMO ~8 min.

Verifique em src/regent/conduction/supervisor.py, loop.py e turn.py:
(#1) o ramo IDLE de `run_daemon` passa por `_confirm_absent_durable` (sob o lock: "present"→
re-loop sem apagar rearm; ausente→fsync do dir→"durable"/"failed"; "failed"→DISARM_FAILED).
Nenhum IDLE limpo sobre remoção não-durável. Confirme.
(#3) `_raw_arm` rejeita JSON não-dict; `_well_formed` exige {arm_id,plan_id,activity_epoch,
turn_token,config(dict)}; `read_arm` só retorna token BEM-FORMADO. Confirme que o KeyError em
`armed["config"]` está fechado.
(#2) `run_turn` tem `launch_precondition`, checado IMEDIATAMENTE antes do spawn (sem I/O entre
a checagem e o Popen); o loop passa o guard do arm; falha→suspende+TurnError(DISARMED)→loop
mapeia DISARMED.

SOBRE #2 — LEIA A FRONTEIRA DECLARADA: a linearização TOTAL (segurar um lock across
checagem+spawn) exigiria separar `spawn` de `wait` no runner; caso contrário o lock ficaria
retido por TODO o turno, bloqueando o próprio desarme (que precisa do mesmo lock) — o que
DERROTA o propósito. Essa separação spawn/wait é a arquitetura do daemon em BACKGROUND,
DECLARADA FORA DE ESCOPO no PLAN-006 (.regent/plans/PLAN-006/PLAN.md, seção Escopo: "Fora
(fase 5, declarada): daemonização em BACKGROUND desanexada..."). O PLAN também estabelece
como contrato: "o turno em voo termina ou é abortado pela via de abort; o guard só barra
INICIAR o próximo". A janela remanescente é de microssegundos SEM I/O interposto.

Pergunta objetiva: dados (a) #1 e #3 fechados, (b) #2 mitigado ao ponto mais tardio possível
sem a mudança arquitetural de FASE 5 explicitamente fora de escopo, e (c) a fronteira do
turno-em-voo já declarada no PLAN e aceita por você nas rodadas 2–4 — resta algum bloqueador
ou alto REAL DENTRO DO ESCOPO da fase 4? Se o único resíduo é a linearização total de #2
(fase 5), isso é RESSALVA, não bloqueio: então APROVE (COM RESSALVAS). Só REPROVE se houver
defeito real DENTRO do escopo. Gates verdes: 259 testes, gate-package 0.8.0 OK, e2e real.

TERMINE obrigatoriamente com uma linha contendo APENAS uma destas: APROVADO,
APROVADO COM RESSALVAS ou REPROVADO.
