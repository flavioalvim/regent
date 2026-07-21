---
outcome: SUCCESS
exit_code: 0
timestamp: 2026-07-21T02:17:54+00:00
linkage: PLAN-004/build
verdict: REPROVADO
---

Há bloqueios reais remanescentes.

1. **ALTA — stop/checkpoint/recuperação ainda não cumprem o contrato.** O único `stop_check` após o agente ocorre antes do gate; um pedido durante o gate segue para VERIFIED e commit ([turn.py:190](/home/flavio/projetos/regent/src/regent/conduction/turn.py:190), [turn.py:204](/home/flavio/projetos/regent/src/regent/conduction/turn.py:204), [turn.py:235](/home/flavio/projetos/regent/src/regent/conduction/turn.py:235)). `STOPPED` apenas lança exceção, sem `service.suspend`, deixando a atividade ACTIVE. `_set_phase` usa replace atômico, mas continua fora do `control` e sem `fsync` do diretório; `recover_turn` não consulta checkpoint/log nem revalida uma fronteira recuperável—apenas classifica worktree sujo como `PARTIAL` ([turn.py:73](/home/flavio/projetos/regent/src/regent/conduction/turn.py:73), [turn.py:86](/home/flavio/projetos/regent/src/regent/conduction/turn.py:86)).

2. **ALTA — GATE/FULL podem ser “lavados” pela isenção.** Se o agente pré-criar `GATE-STEP-NN.md` ou `-FULL.log` sem post, `run_gate` detecta conflito, mas a exceção é convertida em `GATE_ERROR`; ambos continuam incondicionalmente isentos e, por existirem, entram no commit operacional ([turn.py:195](/home/flavio/projetos/regent/src/regent/conduction/turn.py:195), [turn.py:205](/home/flavio/projetos/regent/src/regent/conduction/turn.py:205), [turn.py:248](/home/flavio/projetos/regent/src/regent/conduction/turn.py:248)). Isso permite commitar conteúdo não produzido pelo supervisor e sem atribuição.

3. **ALTA — deleção e tipo ainda escapam da prova.** Qualquer path com um post anterior é aceito quando o status final é `D`, mesmo que a deleção tenha ocorrido depois, sem post de deleção ([turnlog.py:167](/home/flavio/projetos/regent/src/regent/conduction/turnlog.py:167)). Além disso, hook e verificador usam `read_bytes`/`stat`, que seguem symlinks: trocar após o post um arquivo regular por symlink para conteúdo/modo equivalentes é aceito, embora o Git commite outro tipo e outro blob ([hookscript.py:140](/home/flavio/projetos/regent/src/regent/conduction/hookscript.py:140), [turnlog.py:173](/home/flavio/projetos/regent/src/regent/conduction/turnlog.py:173)). O caso específico `chmod 0644→0755` foi fechado; “tipo/modo/deleção”, não.

4. **MÉDIA — o build “canônico” ainda aceita escape por symlink.** Tanto o argumento quanto `.regent/plans/<id>/build` são resolvidos antes da comparação; se `build` for symlink para fora do repositório, a igualdade passa ([turn.py:113](/home/flavio/projetos/regent/src/regent/conduction/turn.py:113), [turn.py:135](/home/flavio/projetos/regent/src/regent/conduction/turn.py:135)).

Fecharam no caminho nominal: índice privado/CAS/rechecagem imediata no commit operacional, inclusão normal do FULL.log, igualdade com o build esperado e deny para `tool_input` não-dict. A janela mínima entre fencing e `update-ref` é uma ressalva aceitável no contrato atual. A árvore contém 176 métodos de teste, mas os contraexemplos acima não estão cobertos. Daemon/loop/`--abort` não pesaram no veredito.

REPROVADO