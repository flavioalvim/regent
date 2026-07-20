Você é o revisor adversarial (Codex/advisor) do produto regent — SEGUNDA REVISÃO FINAL DO
BUILD do PLAN-001, após correções (REQ-005 §6: sua reprovação anterior invalidou-se com os
fixes; esta é a nova consulta obrigatória). Leia: .regent/plans/PLAN-001/build/
ADVISOR-REVIEW.md (sua reprovação: 2 BLOQUEANTES + 3 ALTAS + 3 MÉDIAS + 1 BAIXA) e
STEP-05.md (mapa achado→correção). Revise o diff integral atualizado
(`git diff a7f0186d804b61d3179b5bc8a33b5d8a4a33ae1d..HEAD`) com foco no código final de
src/regent/protocol/ e tests/. Verifique especificamente: (1) detentor VIVO do micro-mutex
nunca é evitado + reivindicação por rename com token + verify_still_held antes do publish;
(2) heartbeat instance-bound via dir-fd e release claim-by-rename (usurpação/destruição
pós-takeover impossíveis); (3) takeover(control_store=) rotaciona o token no control;
(4) schema estrito por conjuntos exatos + epoch monotônico; (5) audit-intent-antes-de-agir;
(6) durabilidade do append (write parcial + fsync arquivo e diretório); (7) no-op
verdadeiro nas transições idempotentes + token no re-apply; (8) NotLockOwner unificado e
desvio declarado do MutationMutexBusy. Gates: 36 testes verdes 3×; gate-package OK. Aponte
o que restar com severidade. TERMINE obrigatoriamente com uma linha contendo apenas:
APROVADO, APROVADO COM RESSALVAS ou REPROVADO.
