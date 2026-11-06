# Previsão de Reajustes Contratuais — Serviços Profissionais

Protótipo de Ciência de Dados que estima o **reajuste contratual provável** antes e depois da solicitação do fornecedor. O objetivo é passar de uma atuação **reativa** ao reajuste para uma **gestão antecipada** dos contratos.

| Público | Pergunta respondida | Modelo |
|---|---|---|
| Área requisitante | Quanto reservar no orçamento para a renovação? | **A — Previsibilidade orçamentária** (antes da solicitação) |
| Compras | O % solicitado está aderente a contratos comparáveis? | **B — Alavanca de negociação** (após a solicitação) |

> **Aviso metodológico:** a base é **inteiramente sintética**. Ela demonstra o funcionamento da metodologia, mas não comprova capacidade preditiva sobre contratos reais. Os KPIs são **demonstrativos**, não ganhos obtidos pela empresa.

## Escopo

- **Categorias:** Consultoria de Gestão, Consultoria de Tecnologia, Auditoria/Asseguração e Consultoria Tributária/Contábil (serviços com predominância de mão de obra especializada). Jurídico e BPO ficam para a fase 2. Facilities, SaaS, hardware, obras e energia estão fora do escopo.
- **Referência econômica:** IPCA acumulado em 12 meses (série oficial do IBGE), usando o último valor divulgado na data-base.
- **Unidade de análise:** 1 linha = 1 evento de reajuste.

## Estrutura do repositório

```
├── data/
│   ├── base_reajustes_sinteticos.csv     # 1.000 eventos (2022–2026), separador ";" e vírgula decimal
│   └── dicionario_dados_reajustes.csv    # colunas, regras e uso em cada modelo (A/B)
├── docs/
│   └── briefing_projeto.md               # briefing metodológico do projeto
├── notebooks/
│   └── modelos_reajustes.ipynb           # modelos, KPIs, gráficos e simulação de uso
├── reports/
│   ├── real_vs_previsto_2025.csv         # backtest evento a evento
│   └── figures/                          # gráficos para a apresentação
├── src/
│   └── gerar_base_reajustes.py           # gerador da base sintética + validações (seed 42)
├── requirements.txt
└── README.md
```

## Como executar

```bash
pip install -r requirements.txt
python src/gerar_base_reajustes.py              # gera data/base_reajustes_sinteticos.csv e roda 11 validações
jupyter notebook notebooks/modelos_reajustes.ipynb
```

## Base sintética

- **Volume:** 1.000 eventos, cerca de 350 contratos e 69 fornecedores, com data-base entre jan/2022 e out/2026. Com 500 eventos, os resultados ficaram instáveis em testes com várias sementes.
- **Comportamento:** cada fornecedor tem um perfil latente estável (quanto costuma pedir acima do IPCA e quanto resiste a ceder). Isso garante consistência histórica sem valores idênticos entre contratos.
- **Coerência:** o valor anual evolui pelo reajuste aprovado e pelas mudanças de escopo.
- **Validações automáticas:**
  - aprovado ≤ solicitado, exceto 21 exceções identificadas;
  - deltas corretos;
  - datas coerentes;
  - percentuais plausíveis;
  - `id_evento` sem duplicidade;
  - mesmo IPCA para a mesma data-base;
  - ausência de valores nulos.
- **Exclusões:** eventos com alteração de escopo (cerca de 8%) são **excluídos** da modelagem.

## Modelos

| Modelo | Alvo | Variáveis |
|---|---|---|
| 0 — Baseline | % aprovado | Reajuste = IPCA 12m |
| 1A — Regressão Linear (orçamento) | % aprovado | IPCA, regime de inflação alta, categoria, valor, remuneração, índice contratual e histórico do fornecedor/contrato. **Sem** variáveis posteriores à solicitação |
| 1B — Regressão Linear (negociação) | % aprovado | Variáveis do 1A + % solicitado |
| 2 — Árvore de Decisão | Faixa vs. IPCA (Abaixo / Alinhado / Acima / Muito acima) | Variáveis do 1A |

- **Faixa provável:** previsão ± quantis de 10% e 90% dos resíduos de treino.
- **Histórico do fornecedor:** usa apenas reajustes anteriores, para não haver vazamento de informação.
- **Faixa da árvore:** relativa ao IPCA, porque as faixas absolutas concentram cerca de 74% de 2025 em "Moderado".

## Validação e resultados (backtest)

Treino com data-base em 2022–2024 e **teste em 2025**, ano fechado (real × previsto, 217 eventos).

| Modelo | Erro médio (MAE) | Erro ≤ 0,5 p.p. | Cobertura da faixa |
|---|---|---|---|
| 0 — Baseline IPCA | 0,73 p.p. | 47% | — |
| 1A — Orçamento | **0,59 p.p.** (−19%) | 57% | 80% |
| 1B — Negociação | **0,32 p.p.** | 85% | 89% |
| 2 — Árvore (faixa) | Acurácia de 53,9% (classe mais frequente: 47,5%) | — | — |

**Simulação 2026:** com o modelo retreinado em 2022–2025, o MAE do Modelo 1A é de 0,52 p.p., contra 0,64 p.p. do baseline.

### KPIs (demonstrativos, 2025)

| KPI | Resultado |
|---|---|
| Previsibilidade | Erro médio de 0,59 p.p., contra 0,73 p.p. assumindo o IPCA |
| Orçamento | Impacto previsto de R$ 18,4 mi contra R$ 17,7 mi efetivos (desvio de +3,7%; o baseline fica 9,0% abaixo) |
| Negociação | Quando o fornecedor pede acima da faixa prevista, a redução média é de 0,91 p.p. (contra 0,35 p.p. nos demais) |
| Benchmark | Aprovado em média +0,40 p.p. acima do IPCA (Tecnologia: +0,63 p.p.) |

## Limitações

- Os dados são sintéticos: as relações entre variáveis foram definidas no gerador, e não observadas em contratos reais.
- A árvore só prevê "Abaixo do IPCA" em regime de inflação alta. Em 2025, essa classe nunca foi prevista.
- O ganho do Modelo A é moderado por natureza: antes da solicitação, há pouca informação disponível.

## Próximos passos

Validar a metodologia com histórico anonimizado real de contratos de serviços profissionais e recalibrar as faixas a partir da distribuição observada.

---
*Projeto acadêmico — Ciência de Dados (Microsoft + Mackenzie).*
