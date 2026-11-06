# Briefing — Projeto: Previsão de Reajustes Contratuais


## 1. Problema e proposta de valor

Hoje, a discussão de reajuste tende a acontecer quando o fornecedor apresenta a solicitação. Isso cria algumas dores:
 * Área requisitante: dificuldade de prever o orçamento necessário para renovação;
 * Compras: menor antecedência para construir estratégia de negociação;
 * Gestão: pouca visibilidade sobre exposição futura a reajustes;
 * Negociação: dificuldade para diferenciar um reajuste aderente ao mercado de uma solicitação acima do esperado.
Proposta do projeto
Criar um modelo simples de Ciência de Dados que, a partir do histórico contratual, estime:
 * Faixa provável de reajuste;
 * Percentual provável de reajuste aprovado;
 * Delta esperado em relação ao IPCA;
 * Potencialmente, probabilidade de o reajuste ficar acima do IPCA.
Na prática:
"Este contrato vence/reajusta nos próximos meses. Considerando categoria, histórico, IPCA e características contratuais, esperamos um reajuste na faixa de 4% a 6%, próximo ao IPCA."
Isso permite atuar antes da solicitação formal do fornecedor.

## 2. Recorte das categorias

O estudo deve utilizar categorias suficientemente semelhantes para que o comportamento histórico seja comparável.
| Categoria | Incluir? | Justificativa |
|---|---|---|
| Consultoria de Gestão/Negócios | ✓ | Predominância de mão de obra especializada |
| Consultoria de Tecnologia | ✓ | Estrutura semelhante, embora possa ter particularidades |
| Auditoria / Asseguração | ✓ | Serviços profissionais e contratos recorrentes |
| Consultoria Tributária/Contábil | ✓ | Estrutura próxima de auditoria/consultoria |
| Jurídico | Fase 2 | Pode envolver êxito/honorários específicos |
| BPO / Call Center | Fase 2 | Maior influência de CCT, headcount e produtividade |
| Facilities | X | CCT, benefícios, insumos e estrutura operacional |
| Software/SaaS | X | Política global de preços, licenças e câmbio |
| Hardware | X | Câmbio, importação e obsolescência |
| Obras | X | Materiais e índices setoriais possuem maior relevância |
| Energia | X | Dinâmica regulatória/tarifária específica |
Recorte sugerido
Serviços profissionais, agrupando inicialmente:
Consultoria + Auditoria + Tributário/Contábil + Tecnologia consultiva.
Se o volume de dados for pequeno, podemos consolidar tudo em uma macro categoria chamada Serviços Profissionais e manter subcategoria para análise.

## 3. Índices e bases econômicas

Aqui eu simplificaria bastante em relação à proposta inicial.
Indicador principal: IPCA
O IPCA acumulado em 12 meses na data-base do reajuste será a referência econômica central.
| Estrutura |  |
|---|---|
| Variável | Utilização |
| IPCA 12m | ✓ Principal indicador macroeconômico |
| Índice previsto no contrato | ✓ Controle contratual |
| IGP-M | X Não utilizar inicialmente |
| INPC | X Não utilizar inicialmente |
| Selic | X Dispensável |
| PIB | X Dispensável |
| Câmbio | X Dispensável neste recorte |
Na construção de uma base real, o IPCA pode ser obtido a partir das séries oficiais do IBGE, tomando sempre o valor que estaria disponível na respectiva data de análise.
Por que isso é importante?
Imagine:
 * IPCA: 4,5%
 * Fornecedor solicita: 7,0%
 * Compras aprova após negociação: 5,2%
Temos:
 * Delta solicitado vs. IPCA = +2,5 p.p.
 * Delta aprovado vs. IPCA = +0,7 p.p.
Esse delta pode ser mais interessante para Compras do que prever isoladamente "5,2%".

## 4. Unidade de análise

A estrutura deve seguir uma regra simples:
1 linha = 1 evento de reajuste.
Portanto, um contrato reajustado em 2024, 2025 e 2026 produzirá três registros.
Isso permite que o modelo aprenda tanto com diferentes contratos quanto com o histórico de recorrência.

## 5. Estrutura final da base

Eu reduziria a base para aproximadamente 20 a 25 variáveis, evitando complexidade desnecessária.
| Coluna | Tipo | Exemplo |
|---|---|---|
| id_evento | Texto | EVT0001 |
| id_contrato | Texto | CTR0150 |
| fornecedor_id | Texto anonimizado | FORN_018 |
| categoria | Categorico | Consultoria |
| subcategoria | Categorico | Estratégia |
| data_inicio_contrato | Data | 2024-04-01 |
| data_base_reajuste | Data | 2026-04-01 |
| valor_anual_antes | Decimal | 1.200.000 |
| modelo_remuneracao | Categorico | Preço fixo |
| indice_contratual | Categorico | IPCA |
| ipca_12m_pct | Decimal | 4,60 |
| reajuste_solicitado_pct | Decimal | 7,00 |
| reajuste_aprovado_pct | Decimal | 5,20 |
| delta_solicitado_ipca_pp | Decimal | +2,40 |
| delta_aprovado_ipca_pp | Decimal | +0,60 |
| meses_desde_ultimo_reajuste | Inteiro | 12 |
| numero_reajuste_contrato | Inteiro | 2 |
| escopo_alterado | Booleano | 0 |
| renovacao_concomitante | Booleano | 1 |
| houve_negociacao | Booleano | 1 |
| quantidade_rodadas | Inteiro | 2 |
| resultado_negociacao | Categorico | Redução parcial |
| economia_negociacao_pp | Decimal | 1,80 |
| faixa_reajuste_aprovado | Categorico | Moderado |
Campos derivados
Não precisam ser manualmente gerados:
 * delta_solicitado_ipca = reajuste_solicitado - IPCA
 * delta_aprovado_ipca = reajuste_aprovado - IPCA
 * economia_negociacao = reajuste_solicitado - reajuste_aprovado

## 6. Exemplo sintético

| Categoria | Valor anual | IPCA | Solicitado | Aprovado | Delta vs. IPCA | Negociação | Faixa |
|---|---|---|---|---|---|---|---|
| Consultoria Gestão | R$ 1,2 mi | 4,5% | 7,0% | 5,2% | +0,7 p.p. | Sim | Moderado |
| Auditoria | R$ 850 mil | 4,8% | 4,8% | 4,8% | 0,0 p.p. | Sim | Moderado |
| Tributária | R$ 420 mil | 4,6% | 6,5% | 5,0% | +0,4 p.p. | Sim | Moderado |
| Consultoria Tech | R$ 2,6 mi | 5,0% | 8,0% | 6,2% | +1,2 p.p. | Sim | Alto |
| Consultoria Gestão | R$ 700 mil | 4,7% | 4,7% | 3,5% | -1,2 p.p. | Sim | Moderado |
| Auditoria | R$ 980 mil | 4,6% | 6,2% | 4,6% | 0,0 p.p. | Sim | Moderado |
Importante: esses números são apenas exemplos sintéticos, não indicam padrões comprovados dessas categorias.

## 7. Como gerar uma base sintética coerente com IA

Como o projeto é acadêmico, faz sentido gerar uma base sintética caso não seja possível disponibilizar dados internos.
Mas há uma regra importante:
A IA não deve simplesmente sortear valores independentes.
Caso contrário, o dataset terá 4,5% de IPCA, 3% solicitado e 9% aprovado sem nenhuma razão, produzindo relações pouco realistas.
Prompt sugerido para geração
Gere uma base sintética com 500 eventos de reajustes contratuais de serviços profissionais, distribuídos entre Consultoria de Gestão, Consultoria de Tecnologia, Auditoria e Consultoria Tributária/Contábil.
Cada linha deve representar um evento de reajuste contratual.
Crie as seguintes colunas: [colar lista das colunas acima].
Regras de coerência:
 * Os dados devem ser inteiramente sintéticos, sem representar empresas ou contratos reais.
 * Os contratos devem representar serviços profissionais predominantemente baseados em mão de obra especializada.
 * Utilize IPCA como principal referência econômica.
 * Gere valores de IPCA plausíveis para cada período e mantenha consistência temporal entre contratos com mesma data-base.
 * O reajuste solicitado deve apresentar relação estatística com o IPCA, mas não ser simplesmente igual a ele.
 * Fornecedores podem solicitar reajustes acima, iguais ou ocasionalmente abaixo do IPCA.
 * Quando houver negociação, o percentual aprovado deverá normalmente ser igual ou inferior ao solicitado.
 * Não permita reajuste aprovado superior ao solicitado, salvo em casos excepcionais explicitamente identificados.
 * Contratos sem alteração de escopo devem constituir a maioria da base.
 * Eventos com alteração relevante de escopo devem ser identificados para posterior exclusão do modelo.
 * Contratos de um mesmo fornecedor devem apresentar alguma consistência histórica, sem valores idênticos.
 * Contratos de maior valor podem apresentar maior pressão ou oportunidade negocial, sem criar uma relação determinística.
 * Inclua casos de reajuste zero e solicitações recusadas.
 * Evite relações perfeitas entre as variáveis. Os dados devem conter variabilidade e ruído compatíveis com uma negociação real.
 * Calcule corretamente todos os campos derivados.
 * Não gere valores ausentes nas variáveis obrigatórias.
 * Utilize uma semente fixa para permitir reprodutibilidade.
Antes de gerar o arquivo final, valide automaticamente que:
 * aprovado ≤ solicitado, exceto exceções justificadas;
 * deltas foram calculados corretamente;
 * datas são cronologicamente consistentes;
 * percentuais estão dentro de faixas plausíveis;
 * não existem duplicidades de id_evento;
 * não existem valores impossíveis;
 * contratos do mesmo período utilizam IPCA temporalmente consistente.
Gere 500 registros em CSV e apresente também um dicionário de dados.
Melhor prática metodológica
Eu acrescentaria ao trabalho uma observação explícita:
A base sintética permite demonstrar o funcionamento da metodologia, mas não comprova capacidade preditiva sobre contratos reais.
Isso protege academicamente o estudo. O modelo poderá demonstrar como a solução funcionaria, e uma etapa futura poderia validar sua performance utilizando histórico anonimizado real.

## 8. O que excluir da primeira versão

Para manter o projeto executivo, eu não levaria inicialmente:
 * CNPJ e razão social;
 * Nome do fornecedor;
 * Comprador/requisitante;
 * Centro de custo;
 * CW/49/pedido;
 * Dados fiscais;
 * Notas fiscais;
 * E-mails;
 * Texto integral dos contratos;
 * Texto integral das propostas;
 * Análise de sentimento;
 * Notícias do fornecedor;
 * Selic, PIB e risco-país;
 * Redes neurais;
 * LLMs;
 * Forecast complexo de séries temporais.
Também excluiria do treinamento eventos com alteração substancial de escopo, porque o modelo poderia interpretar aumento de volume/escopo como reajuste de preço.

## 9. Modelos de Ciência de Dados

Eu usaria somente modelos interpretáveis.
 * Modelo 0: baseline
   * Reajuste esperado = IPCA 12m
   * É fundamental porque responde à pergunta:
     "Nosso modelo consegue prever melhor do que simplesmente assumir IPCA?"
 * Modelo 1: Regressão Linear
   * Target: reajuste_aprovado_pct
   * Possíveis variáveis:
     * IPCA;
     * Categoria;
     * Valor anual;
     * Modelo de remuneração;
     * Meses desde último reajuste;
     * Histórico do fornecedor;
     * Número do reajuste.
 * Modelo 2: Árvore de Decisão
   * Target: faixa_reajuste_aprovado
   * Inicialmente:
     * Sem reajuste: 0%;
     * Baixo: > 0% até 3%;
     * Moderado: >3% até 6%;
     * Alto: >6% até 10%;
     * Muito alto: >10%.
   * Esses intervalos podem ser ajustados após avaliarmos a distribuição da base.

## 10. Um cuidado importante com o modelo

Há uma distinção fundamental entre previsão antecipada e apoio à negociação.
Se o objetivo é prever antes de o fornecedor solicitar o reajuste, não podemos utilizar reajuste_solicitado_pct como variável explicativa.
Caso contrário, teremos vazamento de informação.
Portanto, eu criaria duas visões:
 * Modelo A: Previsibilidade orçamentária
   * Executado antes da solicitação do fornecedor.
   * Entradas: Contrato + categoria + histórico + IPCA + valor + características contratuais -> reajuste esperado
   * Uso: Apoiar orçamento das áreas.
 * Modelo B: Alavanca de negociação
   * Executado após o fornecedor solicitar reajuste.
   * Acrescenta: reajuste_solicitado_pct
   * Uso: "Fornecedor solicita 8,0%, enquanto contratos comparáveis apresentam expectativa de 5,1% e o IPCA está em 4,7%."
Essa separação, na minha opinião, melhora muito o projeto.

## 11. Resultado de negócio esperado

O produto final pode ser extremamente simples:
Para a área requisitante:
 * Contrato: CTR0150
 * Valor atual: R$ 1,2 mi
 * Data-base: abr/2027
 * IPCA utilizado: 4,5%
 * Reajuste estimado: 4% a 6%
 * Impacto orçamentário estimado: R$ 48 mil a R$ 72 mil
Para Compras:
 * Após uma solicitação de 7%:
   * Solicitação: 7,0%
   * IPCA: 4,5%
   * Faixa esperada pelo modelo: 4% a 6%
   * Premium solicitado: +2,5 p.p.
   * Indicação: oportunidade de negociação
Assim, o mesmo modelo atende dois públicos.

## 12. KPIs que valem a pena mostrar

Eu manteria apenas quatro:
 * Previsibilidade: Erro médio entre reajuste previsto e realizado.
 * Orçamento: Diferença entre impacto previsto e efetivo em R$.
 * Negociação: Delta entre solicitado e aprovado.
 * Benchmark: Delta aprovado vs. IPCA.
Se houver base sintética somente, devem ser apresentadas como métricas demonstrativas do modelo, e não como ganhos reais obtidos pela empresa.

## 13. Narrativa para apresentação de aproximadamente 5 minutos

Eu estruturaria em 5 slides:
 * Slide 1 | A dor
   * Reajustes são conhecidos tarde demais.
   * Explique: As áreas têm dificuldade de antecipar impactos no orçamento e Compras inicia a negociação muitas vezes após receber a solicitação do fornecedor.
 * Slide 2 | A solução
   * Antecipar o reajuste antes da negociação.
   * Fluxo conceitual: Histórico contratual + IPCA + características do contrato -> Modelo preditivo -> Faixa esperada de reajuste
   * Duas aplicações: Área → previsibilidade orçamentária; Compras → alavanca de negociação.
 * Slide 3 | Dados e recorte
   * Serviços profissionais comparáveis (Consultoria, Auditoria, Tributário/Contábil, Tecnologia consultiva).
   * 1 evento de reajuste = 1 linha.
   * Base inicial: ~500 eventos sintéticos.
   * IPCA como principal referência econômica.
 * Slide 4 | Modelo
   * Mostrar somente: Baseline IPCA -> Regressão Linear -> Árvore de Decisão
   * E um exemplo: IPCA: 4,5% | Modelo: 4% a 6% | Fornecedor solicita: 7,0% → oportunidade de negociação.
 * Slide 5 | Valor para o negócio
   * Três grandes benefícios:
     * 📊 Previsibilidade: Áreas conseguem antecipar impacto orçamentário.
     * 🤝 Negociação: Compras entra na discussão com uma referência quantitativa.
     * 💡 Inteligência: Histórico contratual deixa de ser apenas registro e passa a apoiar decisões futuras.
   * Fechamento: De uma atuação reativa ao reajuste para uma gestão preditiva dos contratos.

## 14. Desenho final que eu recomendo

O projeto pode ser resumido assim:
 * Problema: Baixa previsibilidade dos reajustes e atuação reativa.
   ↓
 * Dados: Histórico de serviços profissionais + IPCA + contrato + negociação.
   ↓
 * Ciência de Dados: Baseline IPCA + Regressão Linear + Árvore de Decisão.
   ↓
 * Resultado: Faixa e percentual esperado de reajuste.
   ↓
 * Aplicação 1: Antes da solicitação: previsão de orçamento.
   ↓
 * Aplicação 2: Após a solicitação: benchmark para negociação.
   ↓
 * Valor: Maior previsibilidade financeira + maior alavanca de Compras + decisões orientadas por dados.
Esse desenho mantém o projeto acadêmico e tecnicamente defensável, mas principalmente conecta Ciência de Dados a uma dor real da rotina de Compras.
Eu colocaria a base sintética e o modelo como meios, enquanto o verdadeiro protagonista da apresentação seria a transformação de uma negociação hoje reativa em uma gestão antecipada dos reajustes contratuais.
