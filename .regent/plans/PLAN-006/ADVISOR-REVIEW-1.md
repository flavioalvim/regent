---
outcome: SUCCESS
exit_code: 0
timestamp: 2026-07-21T09:41:48+00:00
linkage: PLAN-006
verdict: DISCORDA
---

1. O vínculo `{plan_id, activity_epoch}` é insuficiente: `takeover` troca o `turn_token` sem incrementar o epoch. Um arm antigo sobreviveria ao takeover. Vincule também ao token corrente e a um `arm_id` único.

2. Falta recuperação crash-safe do arm. Crash após `HALTED` e antes do unlink permite que o próximo daemon repita o STEP automaticamente. Arm/desarm/consumo terminal precisam de CAS por `arm_id`, estado durável e `fsync` do arquivo/diretório; o daemon antigo nunca pode apagar um rearm novo.

3. `run_loop` executa vários turnos numa chamada e não conhece o arm-token. Portanto `disarm` ou sinal após a validação ainda permite iniciar turnos seguintes. O arm exato deve ser revalidado antes de cada turno, com semântica explícita para o turno em voo e sinais.

4. `arm` está inseguro/subespecificado quando não há atividade (“se houver”). Deve recusar salvo atividade `build` ACTIVE exatamente correspondente, APPROVED, sem `CONCLUSION.md`, workspace executável e fencing corrente; nunca criar autorização para uma atividade futura.

5. O daemon não define de onde vêm `prompt_template`, `envelope`, `gate_envelope`, `declared_in`, `artifact_dir` e timeout exigidos por `run_loop`. Sem contrato canônico, a implementação não é determinada e pode adotar envelope excessivamente amplo.

6. `run_loop COMPLETE` significa apenas “nenhum STEP pendente”; não executa a revisão final, não cria `CONCLUSION.md` nem conclui a atividade exigida por REQ-005 §6. Reportar `COMPLETED` como término do build é incorreto; deve ser “steps complete” aguardando conclusão mediada, ou a conclusão precisa entrar explicitamente no escopo.

DISCORDA