# regente

Condução autônoma e deliberação mediada entre agentes de IA, plugável em qualquer projeto.

**regente** rege turnos entre agentes (Claude, Codex, humanos mediadores) sob um protocolo
congelado: mutex atômico de turno, estado versionado por CAS, rodadas de deliberação com
aceites versionados, e um daemon de condução que executa lotes de produção com agente
confinado, gates de teste e prova de evidência.

Extraído da ferramenta provada ponta a ponta no projeto ArtNFT (IMP-003: primeiro lote de
produto 100% conduzido pelo daemon, deliberado, aceito e deployado em produção).

- Escopo, decisões e inventário de extração: [`docs/ESCOPO.md`](docs/ESCOPO.md)
- Estado: **pré-extração** (escopo fechado em 2026-07-20; código ainda não migrado)

Uso previsto (v1):

```bash
pip install regente        # (nome livre no PyPI; repo privado por ora)
regente init               # semeia CONTROLE/ESCOPO/skills no projeto host
```

© Flavio Alvim. Todos os direitos reservados (licença a definir).
