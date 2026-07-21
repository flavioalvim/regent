Revisor adversarial (Codex) do regent — REVISÃO FINAL do BUILD do PLAN-006 (condução fase 4).
Rodadas 1–5 fecharam 12 achados reais; a rodada 6 já não encontrou bloqueador nem alto dentro
do escopo. Esta é a confirmação final. MÁXIMO ~6 min.

Confirme DIRETAMENTE em src/regent/conduction/{supervisor,loop,turn}.py + activity_cli.py:
- rehearse read-only; arm com pré-condições duras + config canônica absoluta + validação de
  esquema; read_arm rejeita token malformado e descarta obsoleto sob lock (CAS por arm_id);
  disarm/_unlink_durable com barreira de durabilidade (fsync do dir), sem sucesso falso;
- run_daemon: nunca age sem arm válido; guard revalida sinal/CONCLUSION.md/APPROVED/binding;
  toda condição terminal via finish()→_confirm_disarmed (DISARM_FAILED se não remover);
  IDLE via _confirm_absent_durable; COMPLETE→STEPS_COMPLETE (conclusão MEDIADA, não do daemon);
  emit() não deixa exceção de streaming escapar; exit codes coerentes; 1 linha JSON/transição;
- launch_precondition imediatamente antes do spawn (resíduo de linearização total = FASE 5,
  fora de escopo declarado).

Gates verdes: 259 testes, gate-package 0.8.0 OK, e2e real (arm→daemon --once dirige 2 STEPs→
STEPS_COMPLETE→desarma). Se não houver defeito real DENTRO do escopo da fase 4, aprove (a
linearização total de #2 é ressalva de FASE 5).

TERMINE obrigatoriamente com uma linha contendo APENAS uma destas frases EXATAS: APROVADO,
APROVADO COM RESSALVAS ou REPROVADO.
