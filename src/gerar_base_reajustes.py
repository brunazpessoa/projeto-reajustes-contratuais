"""Gera base sintética de eventos de reajuste contratual (Serviços Profissionais).
1 linha = 1 evento de reajuste. Semente fixa para reprodutibilidade."""
from pathlib import Path
import numpy as np
import pandas as pd

SEED = 42
N_EVENTOS = 1000
rng = np.random.default_rng(SEED)

# IPCA acumulado 12 meses (IBGE) - mês de referência -> %
IPCA_12M = {
    "2021-12": 10.06, "2022-01": 10.38, "2022-02": 10.54, "2022-03": 11.30, "2022-04": 12.13,
    "2022-05": 11.73, "2022-06": 11.89, "2022-07": 10.07, "2022-08": 8.73, "2022-09": 7.17,
    "2022-10": 6.47, "2022-11": 5.90, "2022-12": 5.79, "2023-01": 5.77, "2023-02": 5.60,
    "2023-03": 4.65, "2023-04": 4.18, "2023-05": 3.94, "2023-06": 3.16, "2023-07": 3.99,
    "2023-08": 4.61, "2023-09": 5.19, "2023-10": 4.82, "2023-11": 4.68, "2023-12": 4.62,
    "2024-01": 4.51, "2024-02": 4.50, "2024-03": 3.93, "2024-04": 3.69, "2024-05": 3.93,
    "2024-06": 4.23, "2024-07": 4.50, "2024-08": 4.24, "2024-09": 4.42, "2024-10": 4.76,
    "2024-11": 4.87, "2024-12": 4.83, "2025-01": 4.56, "2025-02": 5.06, "2025-03": 5.48,
    "2025-04": 5.53, "2025-05": 5.32, "2025-06": 5.35, "2025-07": 5.23, "2025-08": 5.13,
    "2025-09": 5.17, "2025-10": 4.68, "2025-11": 4.46, "2025-12": 4.26, "2026-01": 4.44,
    "2026-02": 3.81, "2026-03": 4.14, "2026-04": 4.39, "2026-05": 4.72, "2026-06": 4.64,
    "2026-07": 4.44, "2026-08": 4.22, "2026-09": 4.58,
}
INICIO_JANELA = pd.Timestamp("2022-01-01")
FIM_JANELA = pd.Timestamp("2026-10-01")


def ipca_na_data_base(data_base: pd.Timestamp) -> float:
    """Último IPCA 12m divulgado na data-base = mês anterior."""
    ref = (data_base - pd.DateOffset(months=1)).strftime("%Y-%m")
    return IPCA_12M[ref]


CATEGORIAS = {
    "Consultoria de Gestão": dict(peso=0.32, valor_med=1_200_000, efeito=0.35,
                                  sub=["Estratégia", "Operações", "Gestão de Riscos", "Pessoas e Organização"]),
    "Consultoria de Tecnologia": dict(peso=0.26, valor_med=1_800_000, efeito=0.70,
                                      sub=["Arquitetura de TI", "Dados e Analytics", "Segurança da Informação", "Transformação Digital"]),
    "Auditoria": dict(peso=0.22, valor_med=900_000, efeito=-0.10,
                      sub=["Auditoria Externa", "Auditoria Interna", "Asseguração / Controles"]),
    "Consultoria Tributária/Contábil": dict(peso=0.20, valor_med=450_000, efeito=0.15,
                                            sub=["Consultoria Tributária", "Compliance Fiscal", "Consultoria Contábil"]),
}
CAT_NOMES = list(CATEGORIAS)
CAT_PESOS = [CATEGORIAS[c]["peso"] for c in CAT_NOMES]

REMUNERACAO = {"Preço fixo": (0.40, 0.00), "Homem-hora": (0.30, 0.45),
               "Retainer mensal": (0.20, 0.10), "Por entrega": (0.10, -0.15)}
INDICE = {"IPCA": (0.70, 0.00), "IGP-M": (0.10, 0.30), "INPC": (0.08, 0.05), "Livre negociação": (0.12, 0.60)}


def escolher(d):
    nomes = list(d)
    return nomes[rng.choice(len(nomes), p=[d[n][0] for n in nomes])]


# ---------- Fornecedores (traços latentes = consistência histórica) ----------
N_FORN = 70
fornecedores = []
for i in range(1, N_FORN + 1):
    fornecedores.append(dict(
        fornecedor_id=f"FORN_{i:03d}",
        categoria=rng.choice(CAT_NOMES, p=CAT_PESOS),
        agressividade=rng.normal(0.6, 1.0),            # prêmio típico pedido acima do IPCA (p.p.)
    ))
    f = fornecedores[-1]
    # fornecedores mais agressivos tendem a ceder menos (consistência histórica)
    f["resistencia"] = float(np.clip(0.45 + 0.15 * f["agressividade"] + rng.normal(0, 0.12), 0.1, 0.9))
forn_por_cat = {c: [f for f in fornecedores if f["categoria"] == c] for c in CAT_NOMES}

# ---------- Contratos e eventos ----------
eventos = []
n_ctr = 0
while len(eventos) < N_EVENTOS:
    n_ctr += 1
    cat = rng.choice(CAT_NOMES, p=CAT_PESOS)
    cfg = CATEGORIAS[cat]
    forn = forn_por_cat[cat][rng.integers(len(forn_por_cat[cat]))]
    sub = rng.choice(cfg["sub"])
    remun = escolher(REMUNERACAO)
    indice = escolher(INDICE)
    inicio = pd.Timestamp(year=int(rng.integers(2019, 2026)), month=int(rng.integers(1, 13)), day=1)
    duracao_meses = int(rng.integers(36, 97))
    fim = inicio + pd.DateOffset(months=duracao_meses)
    valor = float(cfg["valor_med"] * rng.lognormal(0, 0.55))
    valor = float(np.clip(valor, 120_000, 9_000_000))

    data_base = inicio + pd.DateOffset(months=12)
    ultimo = inicio
    n_reaj = 0
    while data_base <= min(fim, FIM_JANELA):
        n_reaj += 1
        if data_base >= INICIO_JANELA:
            eventos.append(dict(
                id_contrato=f"CTR{n_ctr:04d}", forn=forn, categoria=cat, subcategoria=sub,
                data_inicio_contrato=inicio, data_base_reajuste=data_base,
                valor_anual_antes=round(valor, 2), modelo_remuneracao=remun, indice_contratual=indice,
                meses_desde_ultimo_reajuste=(data_base.year - ultimo.year) * 12 + data_base.month - ultimo.month,
                numero_reajuste_contrato=n_reaj, cat_efeito=cfg["efeito"],
                ef_remun=REMUNERACAO[remun][1], ef_indice=INDICE[indice][1],
            ))
            ev = eventos[-1]
            ev.update(_tmp_valor=valor)
        # valor evolui com o reajuste aprovado (preenchido depois) -> usamos placeholder e recalculamos
        ultimo = data_base
        atraso = int(rng.integers(1, 7)) if rng.random() < 0.08 else 0
        data_base = data_base + pd.DateOffset(months=12 + atraso)
        if len(eventos) >= N_EVENTOS:
            break

df = pd.DataFrame(eventos).sort_values(["id_contrato", "data_base_reajuste"]).reset_index(drop=True)
# primeiro evento: meses desde último = meses desde o início do contrato (já calculado)

# ---------- Geração sequencial por contrato (valor e comportamento coerentes) ----------
reg = []
for ctr, g in df.groupby("id_contrato", sort=False):
    valor = g.iloc[0]["valor_anual_antes"]
    for _, r in g.iterrows():
        forn = r["forn"]
        dbase = r["data_base_reajuste"]
        ipca = ipca_na_data_base(dbase)
        escopo = int(rng.random() < 0.07)
        renov = int(rng.random() < 0.25)
        log_valor = np.log(valor / 1_000_000)

        # ---- Reajuste solicitado ----
        tipo = rng.random()
        p_ipca = 0.30 if forn["agressividade"] < 0.2 else 0.06   # fornecedores "indexadores" pedem o IPCA
        if tipo < p_ipca:
            premio = 0.0                                    # pede exatamente o IPCA
        elif tipo < p_ipca + 0.04:
            premio = -abs(rng.normal(0.8, 0.5))             # pede abaixo do IPCA
        else:
            premio = (forn["agressividade"] + r["cat_efeito"] + r["ef_remun"] + r["ef_indice"]
                      + 0.25 * log_valor + 0.04 * (r["meses_desde_ultimo_reajuste"] - 12)
                      + rng.normal(0, 0.6))
            if ipca > 8:                                    # inflação alta: prêmio comprimido
                premio *= 0.5
        if escopo:
            premio += rng.uniform(1.5, 5.0)                 # repricing embutido por mudança de escopo
        solicitado = round(max(0.0, ipca + premio) * 20) / 20   # múltiplos de 0,05

        # ---- Negociação e aprovado ----
        excecao = False
        if solicitado <= ipca + 0.05 and rng.random() < 0.55:
            houve_neg, rodadas, aprovado = 0, 0, solicitado
        else:
            houve_neg = 1
            premio_pos = max(0.0, solicitado - ipca)
            alavanca = 0.8 * (1 - forn["resistencia"]) + 0.08 * log_valor + 0.12 * renov + rng.normal(0, 0.12)
            captura = float(np.clip(alavanca, 0.0, 1.0))
            economia = premio_pos * captura
            if ipca > 6:                                    # inflação alta: Compras cede abaixo do IPCA
                economia += (ipca - 6) * rng.uniform(0.2, 0.6)
            elif rng.random() < 0.08:
                economia += rng.uniform(0.2, 1.2)           # ganho abaixo do IPCA ocasional
            aprovado = solicitado - economia
            rodadas = int(np.clip(1 + round(premio_pos / 1.2 + 0.3 * max(log_valor, 0) + rng.normal(0, 0.6)), 1, 5))
            if rng.random() < 0.025:                        # solicitação recusada / congelamento
                aprovado = 0.0
            aprovado = round(float(np.clip(aprovado, 0.0, solicitado)) * 20) / 20
        # exceção explícita: cláusula de índice aplicada acima do pedido
        if r["indice_contratual"] in ("IPCA", "INPC") and solicitado < ipca - 0.3 and rng.random() < 0.25:
            aprovado = round(ipca * 20) / 20
            excecao = True

        # resultado
        if excecao:
            resultado = "Exceção: índice contratual acima do solicitado"
        elif aprovado == 0 and solicitado > 0:
            resultado = "Recusado (reajuste zero)"
        elif solicitado == 0:
            resultado = "Sem reajuste solicitado"
        elif aprovado >= solicitado:
            resultado = "Aceito integralmente"
        else:
            resultado = "Redução parcial"

        reg.append(dict(
            id_contrato=ctr, fornecedor_id=forn["fornecedor_id"], categoria=r["categoria"],
            subcategoria=r["subcategoria"], data_inicio_contrato=r["data_inicio_contrato"].date(),
            data_base_reajuste=dbase.date(), valor_anual_antes=round(valor, 2),
            modelo_remuneracao=r["modelo_remuneracao"], indice_contratual=r["indice_contratual"],
            ipca_12m_pct=ipca, reajuste_solicitado_pct=round(solicitado, 2), reajuste_aprovado_pct=round(aprovado, 2),
            meses_desde_ultimo_reajuste=int(r["meses_desde_ultimo_reajuste"]),
            numero_reajuste_contrato=int(r["numero_reajuste_contrato"]),
            escopo_alterado=escopo, renovacao_concomitante=renov, houve_negociacao=houve_neg,
            quantidade_rodadas=rodadas, resultado_negociacao=resultado,
        ))
        # valor do próximo ciclo: reajuste aprovado + (se houve) variação de escopo
        fator_escopo = rng.uniform(1.15, 1.6) if escopo and rng.random() < 0.7 else (rng.uniform(0.65, 0.9) if escopo else 1.0)
        valor = round(valor * (1 + aprovado / 100) * fator_escopo, 2)

base = pd.DataFrame(reg)

# ---------- Campos derivados ----------
base["delta_solicitado_ipca_pp"] = (base["reajuste_solicitado_pct"] - base["ipca_12m_pct"]).round(2)
base["delta_aprovado_ipca_pp"] = (base["reajuste_aprovado_pct"] - base["ipca_12m_pct"]).round(2)
base["economia_negociacao_pp"] = (base["reajuste_solicitado_pct"] - base["reajuste_aprovado_pct"]).round(2)


def faixa(p):
    if p == 0: return "Sem reajuste"
    if p <= 3: return "Baixo"
    if p <= 6: return "Moderado"
    if p <= 10: return "Alto"
    return "Muito alto"


base["faixa_reajuste_aprovado"] = base["reajuste_aprovado_pct"].apply(faixa)


def faixa_delta(d):
    if d < -0.5: return "Abaixo do IPCA"
    if d <= 0.5: return "Alinhado ao IPCA"
    if d <= 1.5: return "Acima do IPCA"
    return "Muito acima do IPCA"


base["faixa_delta_ipca"] = base["delta_aprovado_ipca_pp"].apply(faixa_delta)

base = base.sort_values(["data_base_reajuste", "id_contrato"]).reset_index(drop=True)
base.insert(0, "id_evento", [f"EVT{i:04d}" for i in range(1, len(base) + 1)])

COLS = ["id_evento", "id_contrato", "fornecedor_id", "categoria", "subcategoria", "data_inicio_contrato",
        "data_base_reajuste", "valor_anual_antes", "modelo_remuneracao", "indice_contratual", "ipca_12m_pct",
        "reajuste_solicitado_pct", "reajuste_aprovado_pct", "delta_solicitado_ipca_pp", "delta_aprovado_ipca_pp",
        "meses_desde_ultimo_reajuste", "numero_reajuste_contrato", "escopo_alterado", "renovacao_concomitante",
        "houve_negociacao", "quantidade_rodadas", "resultado_negociacao", "economia_negociacao_pp",
        "faixa_reajuste_aprovado", "faixa_delta_ipca"]
base = base[COLS]

# ---------- Validações automáticas ----------
b = base
exc = b["resultado_negociacao"].str.startswith("Exceção")
checks = {
    "aprovado <= solicitado (exceto exceções identificadas)": bool((b.loc[~exc, "reajuste_aprovado_pct"] <= b.loc[~exc, "reajuste_solicitado_pct"]).all()),
    "deltas e economia calculados corretamente": bool(
        np.allclose(b["delta_solicitado_ipca_pp"], b["reajuste_solicitado_pct"] - b["ipca_12m_pct"], atol=0.006)
        and np.allclose(b["delta_aprovado_ipca_pp"], b["reajuste_aprovado_pct"] - b["ipca_12m_pct"], atol=0.006)
        and np.allclose(b["economia_negociacao_pp"], b["reajuste_solicitado_pct"] - b["reajuste_aprovado_pct"], atol=0.006)),
    "datas cronologicamente consistentes (início + 12m <= data-base)": bool(
        (pd.to_datetime(b["data_inicio_contrato"]) + pd.DateOffset(months=12) <= pd.to_datetime(b["data_base_reajuste"])).all()),
    "numero_reajuste sequencial e data-base crescente por contrato": bool(all(
        (g["numero_reajuste_contrato"].diff().dropna() == 1).all() and g["data_base_reajuste"].is_monotonic_increasing
        for _, g in b.sort_values(["id_contrato", "numero_reajuste_contrato"]).groupby("id_contrato"))),
    "percentuais em faixa plausível (0% a 20%)": bool(b[["reajuste_solicitado_pct", "reajuste_aprovado_pct"]].stack().between(0, 20).all()),
    "id_evento sem duplicidade": bool(b["id_evento"].is_unique),
    "sem valores impossíveis (valor > 0, rodadas >= 0, meses >= 12)": bool(
        (b["valor_anual_antes"] > 0).all() and (b["quantidade_rodadas"] >= 0).all() and (b["meses_desde_ultimo_reajuste"] >= 12).all()),
    "mesmo mês de data-base => mesmo IPCA": bool((b.groupby("data_base_reajuste")["ipca_12m_pct"].nunique() == 1).all()),
    "sem ausentes": bool(b.notna().all().all()),
    "faixas coerentes com % aprovado e delta": bool((b["reajuste_aprovado_pct"].apply(faixa) == b["faixa_reajuste_aprovado"]).all()
        and (b["delta_aprovado_ipca_pp"].apply(faixa_delta) == b["faixa_delta_ipca"]).all()),
    "negociação coerente (rodadas=0 <=> sem negociação)": bool(((b["houve_negociacao"] == 0) == (b["quantidade_rodadas"] == 0)).all()),
}
for k, v in checks.items():
    print(("OK   " if v else "FALHA"), k)
assert all(checks.values()), "Validação falhou"
assert len(base) == N_EVENTOS

DATA = Path(__file__).resolve().parents[1] / "data"
DATA.mkdir(exist_ok=True)
base.to_csv(DATA / "base_reajustes_sinteticos.csv", index=False, sep=";", decimal=",", encoding="utf-8-sig")
print(f"\n{len(base)} eventos | {base['id_contrato'].nunique()} contratos | {base['fornecedor_id'].nunique()} fornecedores")
