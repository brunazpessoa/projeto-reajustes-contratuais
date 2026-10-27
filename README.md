# Predição de reajustes contratuais

Protótipo de ciência de dados para **estimar o reajuste anual de contratos de serviços recorrentes**
(limpeza, segurança, call center, TI, telecom, manutenção, locação e retainers) e apoiar o planejamento de custos e a
priorização de negociações em Compras.

> **Aviso:** os contratos e fornecedores são sintéticos. Os resultados demonstram o método e o fluxo de ponta a ponta;
> não são evidência de desempenho em contratos reais.

## Pergunta e alvo
Dado o contexto de um contrato na data do reajuste (IPCA, referência salarial, peso da mão de obra, gasto do
fornecedor e histórico), qual será o `reajuste_pct`?
Impacto financeiro (cálculo, não previsão): `impacto = valor_base × reajuste_pct / 100`.

## Como funciona
1. `src/gerar_base_sintetica.py` cria contratos (CW) e aprovações financeiras (WS) fictícios, só fornecedor único.
2. `src/prepare_data.py` valida os dados e monta a base analítica: o reajuste é o WS atual contra o WS anterior,
   somado a índices externos (IPCA 12m e salário mínimo) e ao gasto do fornecedor nos 12 meses anteriores.
3. `src/train_model.py` treina até 2024, testa de 2025 em diante (sem embaralhar o tempo) e compara com baselines.

## Como executar
```bash
python -m venv .venv
.venv\Scripts\activate            # Windows  (macOS/Linux: source .venv/bin/activate)
pip install -r requirements.txt
python src/gerar_base_sintetica.py   # opcional: os dados de data/raw já estão no repositório
python src/prepare_data.py
python src/train_model.py
```
Testado com Python 3.13, pandas 3.0, scikit-learn 1.9.

## Resultados (teste: 2025 em diante, erro médio absoluto em pontos percentuais)
| Modelo | MAE |
|---|---|
| Baseline: média do treino | 0,79 |
| Baseline: reajuste = IPCA 12m | 1,08 |
| Baseline: índice da cláusula | **0,14** |
| Regressão linear só com IPCA | 0,41 |
| **Regressão linear + índice salarial** | **0,34** |
| Ridge + índice salarial | 0,34 |

O modelo supera a média histórica e o IPCA puro, mas **não supera o índice da cláusula** contratual. Detalhes em
`reports/model_metrics.csv`, `reports/erro_por_categoria.csv` e `reports/figures/`.

## Limitações
- Dados sintéticos: o spread de negociação foi definido por regras e não por observação real.
- O reajuste depende quase por completo do índice previsto (IPCA e referência salarial); o ganho está em estimar o spread, que ainda não é previsível nesta base.
- O modelo linear não captura o corte do teto contratual.
- O salário mínimo é uma proxy de dissídio; convenções coletivas reais variam por categoria e região.
- A projeção de 2027 e 2028 depende do Focus e de uma premissa para o salário mínimo.

## Próximos passos
Calibrar o spread com estatísticas agregadas reais; variável de folga do teto; função `prever()` e `simular_impacto()`
com cenários (central, estresse, otimista); validação com dados representativos da organização antes de qualquer uso operacional.
