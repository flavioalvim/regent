# PLAN-001 / build — CONCLUSION

status: ACCEPTED-WITH-RESERVATIONS
actor: executor, per advisor verdict APROVADO COM RESSALVAS (ADVISOR-REVIEW-5); owner
  mediating live (veto aberto — a ratificação tácita fecha no próximo turno)
date: 2026-07-20

## Resultado

A camada `regent.protocol` está implementada e aceita: ControlStore (CAS real sob flock),
TurnLock (ciclo de vida serializado, takeover com fence-before-handover), stop-request
(vínculo id/epoch/token com obsolescência normativa), AuditLog (flock+fsync), façade
nominal. **38 testes dirigidos verdes (3 execuções), gate-package OK.**

Trajeto adversarial: 5 revisões finais do advisor (REPROVADO ×4 → APROVADO COM RESSALVAS),
8 etapas de build (4 planejadas + 4 de correção), cada rodada estreitando os achados até a
troca de primitiva (mutex-diretório → flock do kernel) eliminar a família TOCTOU na raiz.
Registro fiel: o gate do STEP-02 pegou um bug ABA real vermelho→verde; as revisões 1–4
derrubaram lost-update, usurpação pós-takeover, fence não serializado, piso de epoch
apagável e janelas de recuperação — todas corrigidas com teste dirigido.

## Ressalvas registradas (pendências do próximo turno)

1. `release()` deve usar `_remove_tree_strict` (hoje engole OSError — fail-closed em
   segurança, mas o chamador pode acreditar que liberou sem ter liberado) + teste de
   regressão por injeção de falha.
2. Teste dirigido injetando falha de remoção no takeover provando que o control NÃO é
   rotacionado.
3. Docs desatualizadas pela troca de primitiva: README §Protocol layer, PLAN.md (menções a
   mkdir-mutex/recuperação) e docstring de audit.py.

## Rastreabilidade

- Baseline: `a7f0186` (BASELINE.md); diff aceito = `a7f0186..HEAD`.
- Etapas: trailers `Regent-Step: PLAN-001/STEP-0{1..8}` no git log.
- Evidência integral das 5 consultas: `ADVISOR-REVIEW[-N].md` (+ prompts), com cabeçalho
  estruturado (outcome/exit_code/timestamp/linkage) conforme REQ-003 §5 / REQ-005 §7.
