"""
Gerador v3 de base SINTETICA de contratos (CW) e aprovacoes financeiras (WS), formato Ariba.
Todos os contratos e fornecedores sao FICTICIOS. Escopo: servicos recorrentes, sem concorrencia
(fornecedor unico), com reajuste periodico no mes de aniversario de cada contrato.

Indices:
  - IPCA acumulado 12m (oficial, arquivo data/raw/ipca_mensal.csv)
  - Salario minimo (proxy publica do dissidio/repactuacao em servicos de mao de obra)
Regra: indice_aplicavel = w * dissidio_ref + (1 - w) * IPCA12m    (w = peso da mao de obra no contrato)
       reajuste = indice_aplicavel + spread  (spread >= 0; limitado por teto contratual quando existe)

Uso: python src/gerar_base_sintetica.py   (gera data/raw/contratos_cw.csv e aprovacoes_ws.csv)
"""
from pathlib import Path

import numpy as np
import pandas as pd

RAIZ = Path(__file__).resolve().parents[1]
RAW, DOCS = RAIZ / "data" / "raw", RAIZ / "docs"
RAW.mkdir(parents=True, exist_ok=True); DOCS.mkdir(exist_ok=True)

SEED = 42
rng = np.random.default_rng(SEED)
HOJE = pd.Timestamp("2026-10-25")

# ---------- 1) IPCA acumulado em 12 meses (arquivo oficial) ----------
def _num(x):
    return pd.to_numeric(x.astype(str).str.replace(",", "."), errors="coerce")


_raw = pd.read_csv(RAW / "ipca_mensal.csv", sep=";")
_raw["periodo"] = pd.to_datetime(_raw["DateTime"]).dt.to_period("M")
_raw["ocorrido"] = _num(_raw["IPCA ocorrido"])
IPCA_OCORRIDO = _raw.dropna(subset=["ocorrido"]).set_index("periodo")["ocorrido"]
FONTE_IPCA = f"OFICIAL ({IPCA_OCORRIDO.index.min()} a {IPCA_OCORRIDO.index.max()})"


def ipca_12m(periodo):
    return float(IPCA_OCORRIDO.loc[periodo])


# ---------- 2) Salario minimo (data/raw/salario_minimo.csv; conferir contra os decretos) ----------
_sm = pd.read_csv(RAW / "salario_minimo.csv")
SALARIO_MINIMO = dict(zip(_sm["ano"], _sm["salario_minimo_rs"]))
DISSIDIO_REF = {a: (SALARIO_MINIMO[a] / SALARIO_MINIMO[a - 1] - 1) * 100 for a in range(2016, 2027)}

# ---------- 3) Categorias (servicos recorrentes) ----------
# idx: indexador | w: peso medio da mao de obra | markup: spread medio acima do indice (p.p.)
# escala: valor anual tipico (R$) | p_teto: probabilidade de o contrato ter clausula de teto
CATEGORIAS = {
    "Limpeza e Conservacao":              dict(cod="LIM", w=0.80, markup=0.2, escala=2.5e6, n_forn=12, p_teto=0.10,
                                               just="Mao de obra intensiva; repactuacao por convencao coletiva"),
    "Seguranca e Portaria":               dict(cod="SEG", w=0.80, markup=0.3, escala=4.0e6, n_forn=12, p_teto=0.10,
                                               just="Vigilancia, portaria e controle de acesso; sensivel a piso salarial"),
    "Call Center":                        dict(cod="CAL", w=0.70, markup=0.3, escala=3.0e6, n_forn=10, p_teto=0.10,
                                               just="Atendimento terceirizado; custo dominado por pessoal"),
    "BPO":                                dict(cod="BPO", w=0.65, markup=0.4, escala=4.0e6, n_forn=10, p_teto=0.15,
                                               just="Back-office terceirizado; mao de obra com salarios acima do piso"),
    "TI - Suporte e Help Desk":           dict(cod="TIS", w=0.60, markup=0.5, escala=2.0e6, n_forn=10, p_teto=0.20,
                                               just="Suporte continuo com SLA; custo principal e equipe"),
    "TI - SaaS e Cloud":                  dict(cod="SAA", w=0.0,  markup=0.9, escala=2.5e6, n_forn=12, p_teto=0.55,
                                               just="Mensalidade recorrente; reajuste por IPCA, usualmente com teto negociado"),
    "Telecom e Links":                    dict(cod="TEL", w=0.0,  markup=0.3, escala=3.0e6, n_forn=8,  p_teto=0.45,
                                               just="Links dedicados e telefonia corporativa; indice de precos"),
    "Manutencao Predial":                 dict(cod="MAN", w=0.50, markup=0.5, escala=1.5e6, n_forn=12, p_teto=0.30,
                                               just="HVAC, elevadores, geradores; mistura de mao de obra e materiais"),
    "Locacao de Ativos":                  dict(cod="LOC", w=0.0,  markup=0.4, escala=2.0e6, n_forn=10, p_teto=0.40,
                                               just="Frota e equipamentos de escritorio; indice de precos"),
    "Juridico e Auditoria (retainer)":    dict(cod="JUR", w=0.0,  markup=0.6, escala=0.8e6, n_forn=10, p_teto=0.45,
                                               just="Honorarios mensais recorrentes; so contratos continuos"),
    "Marketing e Comunicacao (retainer)": dict(cod="MKT", w=0.0,  markup=0.6, escala=1.5e6, n_forn=10, p_teto=0.45,
                                               just="Agencias com fee mensal; so contratos continuos"),
}
FORA_DO_ESCOPO = {
    "Consultoria": "contratos pontuais, sem reajuste recorrente",
    "Treinamento": "contratos majoritariamente pontuais (cursos e turmas avulsas)",
    "Seguros e Planos de Saude": "reajuste por sinistralidade e renovacao, nao por indice contratual",
    "Manutencao industrial": "fora do perfil de servicos do banco",
}
PESO_MES = [0.16, 0.06, 0.07, 0.07, 0.07, 0.10, 0.09, 0.06, 0.09, 0.08, 0.06, 0.09]

# ---------- 4) Fornecedores e contratos ----------
fornecedores = [dict(fornecedor=f"FORN_{p['cod']}_{i+1:02d}", categoria=cat, porte=rng.lognormal(0, 0.8))
                for cat, p in CATEGORIAS.items() for i in range(p["n_forn"])]
cws, n = [], 0
for f in fornecedores:
    p = CATEGORIAS[f["categoria"]]
    for _ in range(rng.integers(1, 5)):
        n += 1
        ano = int(rng.integers(2017, 2026))
        mes = int(rng.choice(12, p=PESO_MES)) + 1
        inicio = pd.Timestamp(year=ano, month=mes, day=int(rng.integers(1, 29)))
        if inicio > HOJE:
            inicio = inicio - pd.DateOffset(years=1)
        w = float(np.clip(p["w"] + rng.normal(0, 0.05), 0, 0.95)) if p["w"] > 0 else 0.0
        tem_teto = rng.random() < p["p_teto"]
        cws.append(dict(id_cw=f"CW{n:05d}", fornecedor=f["fornecedor"], categoria=f["categoria"],
                        indexador="Hibrido (dissidio + IPCA)" if w > 0 else "IPCA",
                        peso_mao_de_obra=round(w, 2), data_inicio=inicio, mes_reajuste=inicio.month,
                        valor_inicial=round(p["escala"] * f["porte"] * rng.lognormal(0, 0.4), 2),
                        tem_teto=int(tem_teto),
                        teto_pct=float(rng.choice([6.0, 7.0, 8.0])) if tem_teto else np.nan,
                        tipo_contratacao="Fornecedor unico (sem concorrencia)"))
cw = pd.DataFrame(cws)
cw_idx = cw.set_index("id_cw")

# ---------- 5) Eventos (aniversarios) e simulacao cronologica ----------
eventos = []
for r in cw.itertuples():
    k = 0
    while k <= 8:
        d = r.data_inicio + pd.DateOffset(years=k)
        if d > HOJE:
            break
        eventos.append((d, r.id_cw, k))
        k += 1
eventos.sort()

valor_atual, reaj_ant, spread_ant, indice_ant = {}, {}, {}, {}
ledger, ws_rows = [], []
for d, id_cw, k in eventos:
    c = cw_idx.loc[id_cw]
    p = CATEGORIAS[c.categoria]
    if k == 0:
        valor = c.valor_inicial
    else:
        prev = valor_atual[id_cw]
        janela = [(v, f) for (dt, f, v) in ledger if d - pd.Timedelta(days=370) < dt < d]
        spend_forn = sum(v for v, f in janela if f == c.fornecedor)
        spend_total = sum(v for v, _ in janela)
        ipca12 = ipca_12m(pd.Period(d, "M") - 1)
        dis = DISSIDIO_REF[d.year]
        w = c.peso_mao_de_obra
        indice = w * dis + (1 - w) * ipca12
        s_prev = spread_ant.get(id_cw, p["markup"])
        poder = -0.5 * (np.log10(max(spend_forn, 1.0)) - 6.2)       # mais gasto -> menos spread
        spread = max(0.7 * p["markup"] + 0.3 * s_prev + poder - 0.05 * k + rng.normal(0, 0.35), 0.0)
        reaj = indice + spread
        if c.tem_teto:
            reaj = min(reaj, c.teto_pct)
        valor = round(prev * (1 + reaj / 100), 2)
        reaj_ant[id_cw], indice_ant[id_cw], spread_ant[id_cw] = reaj, indice, reaj - indice
    valor_atual[id_cw] = valor
    ledger.append((d, c.fornecedor, valor))
    ws_rows.append(dict(id_ws=f"WS{len(ws_rows)+1:06d}", id_cw=id_cw, ordem=k,
                        data_aprovacao=d.date(), valor_aprovado=valor))

ws = pd.DataFrame(ws_rows)
tot = ws.groupby("id_cw").agg(valor_total_acumulado=("valor_aprovado", "sum"), qtd_ws=("id_ws", "count")).reset_index()
cw = cw.merge(tot, on="id_cw")
cw["data_inicio"] = cw["data_inicio"].dt.date
cw.to_csv(RAW / "contratos_cw.csv", index=False)
ws.to_csv(RAW / "aprovacoes_ws.csv", index=False)

# ---------- 6) Documentacao: premissas e dicionario ----------
prem = [dict(categoria=c, status="NO ESCOPO", codigo=p["cod"],
             indexador="Hibrido (dissidio + IPCA)" if p["w"] > 0 else "IPCA", peso_mao_de_obra_medio=p["w"],
             markup_medio_pp=p["markup"], prob_teto=p["p_teto"], valor_anual_tipico_rs=p["escala"],
             n_fornecedores=p["n_forn"], justificativa=p["just"]) for c, p in CATEGORIAS.items() for _ in [0]]
prem += [dict(categoria=c, status="FORA DO ESCOPO", justificativa=m) for c, m in FORA_DO_ESCOPO.items()]
pd.DataFrame(prem).to_csv(DOCS / "premissas_categorias.csv", index=False)

DIC = [
    ("contratos_cw", "id_cw", "Identificador do contrato (CW)", "Sintetico"),
    ("contratos_cw", "fornecedor", "Fornecedor ficticio; cada fornecedor atua em uma categoria", "Sintetico"),
    ("contratos_cw", "categoria", "Categoria de servico recorrente", "Sintetico"),
    ("contratos_cw", "indexador", "Clausula de reajuste: IPCA ou hibrido (dissidio + IPCA)", "Sintetico"),
    ("contratos_cw", "peso_mao_de_obra", "Peso da mao de obra no custo (0 a 1); pondera dissidio vs IPCA", "Sintetico"),
    ("contratos_cw", "data_inicio", "Inicio da vigencia; define o mes de aniversario do reajuste", "Sintetico"),
    ("contratos_cw", "mes_reajuste", "Mes (1-12) em que o contrato e reajustado", "Derivado"),
    ("contratos_cw", "valor_inicial", "Valor anual aprovado no primeiro WS (R$)", "Sintetico"),
    ("contratos_cw", "tem_teto / teto_pct", "Clausula de teto de reajuste (0/1) e percentual do teto", "Sintetico"),
    ("contratos_cw", "tipo_contratacao", "Constante: fornecedor unico (recorte sem concorrencia)", "Premissa"),
    ("contratos_cw", "valor_total_acumulado / qtd_ws", "Soma dos WS do contrato (R$) e quantidade de WS", "Derivado"),
    ("aprovacoes_ws", "id_ws / id_cw / ordem", "Aprovacao financeira, contrato de origem e sequencia (0 = inicial)", "Sintetico"),
    ("aprovacoes_ws", "data_aprovacao / valor_aprovado", "Data e valor anual aprovado (R$) no WS", "Sintetico"),
    ("base_analitica", "ordem_reajuste", "Numero do reajuste do contrato (1 = primeiro)", "Derivado"),
    ("base_analitica", "valor_anterior", "Valor do WS anterior (R$)", "Derivado"),
    ("base_analitica", "spend_fornecedor_12m", "Gasto aprovado do fornecedor nos 12 meses anteriores (R$)", "Derivado, sem vazamento"),
    ("base_analitica", "share_spend_fornecedor", "Participacao do fornecedor no gasto total dos 12 meses anteriores", "Derivado, sem vazamento"),
    ("base_analitica", "ipca_12m", "IPCA acumulado 12m no mes anterior ao reajuste (%)", "BCB/IBGE, ipca_mensal.csv"),
    ("base_analitica", "dissidio_ref_pct", "Reajuste do salario minimo do ano (%), proxy publica de dissidio", "Decretos federais (conferir)"),
    ("base_analitica", "indice_aplicavel_pct", "w x dissidio_ref + (1-w) x IPCA12m (%)", "Derivado da clausula"),
    ("base_analitica", "reajuste_anterior_pct / spread_anterior_pp", "Reajuste e spread do evento anterior do mesmo contrato", "Derivado"),
    ("base_analitica", "reajuste_pct", "ALVO: (WS atual / WS anterior - 1) x 100", "Derivado"),
    ("base_analitica", "spread_vs_indice_pp", "reajuste_pct - indice_aplicavel_pct (ganho/perda de negociacao)", "Derivado"),
]
pd.DataFrame(DIC, columns=["tabela", "coluna", "descricao", "origem"]).to_csv(DOCS / "dicionario_dados.csv", index=False)

print(f"IPCA: {FONTE_IPCA} | salario minimo: data/raw/salario_minimo.csv (conferir)")
print(f"Categorias: {len(CATEGORIAS)} | CW: {len(cw)} | WS: {len(ws)} ")
