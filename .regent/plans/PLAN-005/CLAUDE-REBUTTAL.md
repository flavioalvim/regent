# PLAN-005 — Réplica do Claude às 8 objeções do advisor

**Aceito as 8.** O v2 as incorpora nos contratos. Destaque: a #5 (runner bloqueante não
cancelável) e a #7 (sem exclusão entre loops) são arquiteturais e mudam o desenho.

1. **Revalidar executabilidade por turno:** o loop RECARREGA `APPROVAL.md` a cada volta e
   exige `status: APPROVED` (REJECTED/CANCELLED param o loop com `PLAN_NOT_EXECUTABLE`);
   além da atividade build ACTIVE.
2. **Avanço só com STEP commitado+trailer:** o "STEP corrente" passa a ser o menor STEP-NN
   SEM commit contendo `Regent-Step: PLAN-NNN/STEP-NN` (git log --grep), não a mera
   existência do arquivo. STEP file forjado/não-commitado NÃO avança nem gera COMPLETE.
3. **Identidade de tentativa (retry após HALTED):** o linkage do turno inclui um sufixo de
   TENTATIVA (`PLAN/STEP/tryK`, K = nº de `TURN-*try*` já presentes para o STEP + 1); os
   nomes dos artefatos do turno (TURN/GATE) carregam o try → sem EvidenceConflict ao
   re-rodar. run_turn ganha um parâmetro `attempt` que sufixa os artefatos.
4. **abort-request vinculado + atômico:** `abort.request` = {id, activity_id,
   activity_epoch, turn_token, requested_at, reason}; escrita atômica (tmp+rename);
   leitura VALIDA o vínculo (id/epoch/token) e DESCARTA obsoleto com auditoria; claim/
   consumo único (rename para `.claimed`); nunca mata turno futuro.
5. **Runner CANCELÁVEL:** `SubprocessRunner.run` ganha `cancel: threading.Event`; poll
   (~0.5s) em vez de communicate bloqueante; ao setar → killpg(SIGKILL) → RunResult com
   flag `aborted` (distinta de timeout). A keep-alive checa o abort-request a cada ~1s
   (não 120s) e seta o cancel — latência ~1s, não "até 120s".
6. **Máquina de recuperação do abort (ordenada, idempotente):** persistir evidência
   `ABORTED` → (o kill já ocorreu no runner) → SUSPENDER PELA CAMADA DE APLICAÇÃO
   (`service.suspend`, que TAMBÉM LIBERA o turn lock — corrige o gap de que suspend_activity
   do protocolo removia o token sem liberar o lock; **emenda declarada ao caminho de stop
   do PLAN-004**, que passa a rotear por service.suspend). `ABORTED` (turno) mapeia para
   `CANCELLED` (desfecho de consulta, REQ-003 §5) só onde há consulta; aqui é desfecho de
   TURNO. Crash entre passos: reexecução via recover_turn (worktree para o mediador).
7. **Exclusão entre loops:** um **loop lock** dedicado (flock em XDG `loop.lock`) — dois
   `loop run` no mesmo repo não coexistem (segundo recebe `LOOP_BUSY`). O turn lock
   representa a ATIVIDADE; o loop lock exclui PROCESSOS do driver.
8. **Estados terminais completos:** mapa exceção→condição: NOT_ACTIVE→`PLAN_NOT_EXECUTABLE`;
   CONFLICT→`LOOP_CONFLICT`; WORKTREE_DIRTY→`LOOP_DIRTY`; PROVENANCE/STEP_MISMATCH→
   `LOOP_MISCONFIGURED`; STOPPED→`STOPPED`; ABORTED→`ABORTED`; TURN_*/GATE_RED/FAILURE/
   TIMEOUT→`HALTED`. Estado de atividade/lock por condição: COMPLETE/HALTED/MAX_TURNS →
   atividade permanece ACTIVE com token (mediador decide conclude/continuar); STOPPED/
   ABORTED → SUSPENDED sem token. O resumo do loop é commitado por um **op-commit sem
   fencing quando não há token** (SUSPENDED) e COM fencing quando há (ACTIVE) — as duas
   vias declaradas.
