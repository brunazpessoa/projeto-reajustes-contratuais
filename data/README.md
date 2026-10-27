# Dados

Todos os dados de contratos e fornecedores são **sintéticos** (fictícios). Não há nenhum dado real de empresa neste repositório.

## data/raw/ (entradas)
| Arquivo | O que é | Origem |
|---|---|---|
| `contratos_cw.csv` | 1 linha por contrato (categoria, fornecedor, tipo de reajuste, peso da mão de obra, teto) | Sintético: `src/gerar_base_sintetica.py` (seed 42) |
| `aprovacoes_ws.csv` | 1 linha por aprovação financeira (valor anual aprovado e data) | Sintético: mesmo script |
| `ipca_mensal.csv` | IPCA acumulado em 12 meses (ocorrido) e projeção Focus | Banco Central do Brasil (confirmar termos de uso da fonte) |
| `salario_minimo.csv` | Salário mínimo nacional por ano, usado como referência pública de dissídio | Decretos federais (**conferir os valores, principalmente 2026**) |

## data/processed/ (gerado, não versionado)
- `base_analitica.csv`: 1 linha por reajuste, criada por `src/prepare_data.py`. É a única tabela usada pelo modelo.

Colunas e regras de geração: veja `docs/dicionario_dados.csv` e `docs/premissas_categorias.csv`.
