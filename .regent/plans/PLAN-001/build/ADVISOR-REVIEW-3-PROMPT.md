Você é o revisor adversarial (Codex/advisor) do produto regent — TERCEIRA revisão final do
BUILD do PLAN-001, após o STEP-06 (REQ-005 §6). Leia: .regent/plans/PLAN-001/build/
ADVISOR-REVIEW-2.md (sua 2ª reprovação) e STEP-06.md (mapa achado→correção), e revise o
código final de src/regent/protocol/{control,lock,stop,audit}.py + tests/ (diff
`git diff a7f0186..HEAD` se útil). Pontos-chave do STEP-06: verify_still_held DENTRO de
_publish imediatamente antes do os.replace; __exit__ do mutex token-condicional; re-check
pré-rename na evicção; combinação com "detentor vivo nunca é evitado" (evicção exige pid
morto); release verifica token ANTES de renomear; takeover rotaciona o token no control
ANTES de criar o lock novo (fence-before-handover; crash no meio = control cercado sem
lock, seguro; rotação com token divergente auditada); epoch com piso via
last_concluded.epoch e restart do ocioso estritamente maior; flock no append do audit;
no-op verdadeiro também em corrida (mutate compara e não publica corpo inalterado); tipos
estritos (bool≠int, timestamps tz-aware, tokens 32-hex). Gates: 37 testes verdes 3×,
gate-package OK. Considere o CONTEXTO v0 do produto (CLI single-host, PLAN-001 é fundação
dormente até a fase de condução): avalie se restam falhas REAIS de correção nos cenários
alcançáveis, distinguindo-as de refinamentos teóricos que podem ser ressalvas para a fase
de condução. TERMINE obrigatoriamente com uma linha contendo apenas: APROVADO, APROVADO
COM RESSALVAS ou REPROVADO.
