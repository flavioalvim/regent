# PLAN-006 — Réplica do Claude às 6 objeções do advisor

**Aceito as 6.** A #6 é decisiva: COMPLETE do loop = "STEPs feitos", NÃO build concluído
(a revisão final + CONCLUSION.md + aceite são decisão MEDIADA do dono). O v2 reancora nisso.

1. **Vínculo do arm completo:** o arm-token ganha `arm_id` (uuid4) + `turn_token` (além de
   plan_id/epoch) — takeover troca o token → arm antigo é invalidado na leitura.
2. **Arm crash-safe:** escrita atômica (tmp+fsync+rename+fsync do dir); disarm/consumo
   terminal por CAS de `arm_id` — um daemon antigo (arm_id A) NUNCA apaga um rearm novo
   (arm_id B); leitura valida o vínculo e ignora+audita obsoleto.
3. **Revalidação por turno:** `run_loop` ganha um callback `guard` checado ANTES de cada
   turno; o daemon passa um guard que revalida o arm exato (arm_id/plan/epoch/token +
   APPROVED + não-concluído). Guard falho → o loop PARA com condição `DISARMED` (o turno em
   voo termina/aborta pela via de abort; o guard só barra INICIAR o próximo). Sinais
   (SIGINT/TERM) setam o guard para parar.
4. **arm com pré-condições duras:** recusa salvo atividade `build` ACTIVE cujo id == o
   plano, APPROVED, SEM `build/CONCLUSION.md`, workspace verdict executável e token
   corrente; NUNCA autoriza atividade futura (sem atividade = erro).
5. **arm captura a config do loop:** o arm-token guarda prompt_template, envelope,
   gate_envelope, declared_in, artifact_dir, max_turns, timeout — o daemon LÊ essa config
   canônica (nada de envelope amplo ad-hoc); a config é validada no arm (paths canônicos).
6. **COMPLETE ≠ build concluído:** `run_loop COMPLETE` (nenhum STEP pendente) → o daemon
   reporta `STEPS_COMPLETE` e DESARMA, deixando a revisão final do advisor + `CONCLUSION.md`
   + `activity conclude` para o MEDIADOR (/regent). O daemon NÃO auto-conclui nem auto-aceita
   (juízo humano). Declarado explicitamente. Toda condição não-STEPS_COMPLETE também desarma.
