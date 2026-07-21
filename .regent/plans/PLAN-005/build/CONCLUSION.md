# PLAN-005 / build — CONCLUSION

status: ACCEPTED-WITH-RESERVATIONS
actor: executor, per advisor verdict APROVADO COM RESSALVAS (ADVISOR-REVIEW-8, sem bloqueio
  alcançável na fase); owner mediating live
date: 2026-07-21

## Resultado

Condução fase 3 ENTREGUE (0.7.0): `regent loop run` encadeia turnos supervisionados
(PLAN-004) sobre um plano de build aprovado até uma condição terminal (COMPLETE / HALTED /
STOPPED / ABORTED / MAX_TURNS / LOOP_*), com loop lock (exclusão de processos), revalidação
de APPROVAL por turno, avanço NÃO-falsificável (trailer exato + arquivo em HEAD),
identidade de tentativa para retry, e resumo por índice privado + CAS. `regent loop abort`
+ `--abort` real: cancelamento IMEDIATO do turno em voo (runner cancelável, killpg),
honrado em TODAS as janelas (launch, gate, verify/evidência), com suspensão via camada de
aplicação que LIBERA o turn lock (emenda ao PLAN-004) e recuperação idempotente. 213 testes
verdes 3×; e2e real (loop 2 STEPs→COMPLETE; abort→ABORTED+SUSPENDED sem commit).

## Marco: a revisão mais profunda do projeto

8 revisões finais, TODAS pelo próprio `regent advisor consult` (dogfood): REPROVADO ×7 →
APROVADO COM RESSALVAS. O advisor perseguiu o abort através de CADA janela de execução do
turno (launch → gate → verify/evidência) e cada corrida de recuperação (op-commit
mascarando .claimed, token pós-suspensão em owning_turn, clear de marcador alheio,
fencing do resumo), até o cancelamento ser honrado em todas. 11 STEPs (4 planejados + 7 de
correção). Cada reprovação estreitou; a última só deixou a janela teórica mínima
(análoga à fencing→update-ref já aceita) e itens de fase 4.

## Ressalvas registradas (fase 4, declaradas)

daemon background contínuo, ativação automática, ensaio, decisão automática de iniciar um
build; e a corrida teórica mínima após a última checagem de cancel (aceitável no contrato
single-host).

## Rastreabilidade

Baseline `3a379246`; trailers `Regent-Step: PLAN-005/STEP-0{1..11}`; evidência das 9
consultas (ADVISOR-REVIEW{,-2..8}.md + prompts) geradas pelo próprio regent advisor consult.
