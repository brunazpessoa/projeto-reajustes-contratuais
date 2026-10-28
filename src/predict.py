"""
predict.py - projeta os reajustes até 2028 e calcula o impacto financeiro.

Duas camadas, separadas de propósito:
  - PREVISÃO (modelo): estima o % de reajuste de cada contrato a partir do IPCA, da referência salarial, do gasto
    do fornecedor e do histórico. O teto da cláusula é regra e é aplicado depois do modelo.
  - CÁLCULO (determinístico): impacto = valor_base x % / 100.

Cenários: o IPCA 12m vem do Focus (central); os outros cenários deslocam esse caminho em p.p.
As premissas ficam aqui no topo e em reports/projecao_premissas.csv.

Uso: python src/predict.py   (antes: prepare_data.py e train_model.py)
Como biblioteca (a partir da pasta src): from predict import prever_reajuste, simular_impacto
"""
from pathlib import Path

import joblib
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.patches import Patch

RAIZ = Path(__file__).resolve().parents[1]
RAW, PROC, MODELS, REPORTS = RAIZ / "data" / "raw", RAIZ / "data" / "processed", RAIZ / "models", RAIZ / "reports"
FIGS = REPORTS / "figures"

# Choque no IPCA 12m (p.p.). Ele entra aos poucos, pois um acumulado de 12 meses não salta de uma vez.
CENARIOS = {"otimista": -1.0, "central": 0.0, "estresse": 2.0}
CORES = {"otimista": "#1baf7a", "central": "#2a78d6", "estresse": "#eb6834"}
ANOS_GANHO_REAL = [2024, 2025, 2026]      # anos usados para estimar o ganho real do salário mínimo
FIM_PROJECAO = pd.Timestamp("2028-12-31")
JANELA_SPEND = pd.Timedelta(days=370)     # mesma janela de 12 meses usada no treino


def brl(valor):
    return f"R$ {valor:,.0f}".replace(",", ".")


# ---------- Previsão e cálculo (podem ser usados isoladamente) ----------
def prever_reajuste(modelo, entradas):
    """Reajuste previsto (%) para cada linha de `entradas` (DataFrame). Rejeita entradas inválidas com mensagem clara."""
    cols = modelo["colunas"]
    faltam = [c for c in cols if c not in entradas.columns]
    if faltam:
        raise ValueError(f"Colunas ausentes: {faltam}")
    # O histórico pode faltar no 1º reajuste do contrato (o modelo imputa); o resto é obrigatório.
    obrigatorias = [c for c in cols if c not in ("reajuste_anterior_pct", "spread_anterior_pp")]
    nulos = [c for c in obrigatorias if entradas[c].isna().any()]
    if nulos:
        raise ValueError(f"Valores vazios em: {nulos}")
    if not entradas["peso_mao_de_obra"].between(0, 1).all():
        raise ValueError("peso_mao_de_obra deve estar entre 0 e 1")
    validas = set(modelo["pipeline"].named_steps["prep"].named_transformers_["cat"].categories_[0])
    invalidas = sorted(set(entradas["categoria"]) - validas)
    if invalidas:
        raise ValueError(f"Categoria desconhecida: {invalidas}. Categorias válidas: {sorted(validas)}")

    prev = modelo["pipeline"].predict(entradas[cols])
    if "teto_pct" in entradas.columns:
        com_teto = entradas["tem_teto"].to_numpy() == 1
        if (com_teto & entradas["teto_pct"].isna().to_numpy()).any():
            raise ValueError("tem_teto = 1 exige teto_pct preenchido")
        prev = np.where(com_teto, np.minimum(prev, entradas["teto_pct"].to_numpy()), prev)
    return prev


def simular_impacto(valor_base, percentual_estimado):
    """Cálculo determinístico: quanto o contrato aumenta, em R$, dado o % de reajuste."""
    return valor_base * percentual_estimado / 100


# ---------- Cenários de IPCA e salário mínimo ----------
def carregar_ipca():
    d = pd.read_csv(RAW / "ipca_mensal.csv", sep=";")
    d["periodo"] = pd.to_datetime(d["DateTime"]).dt.to_period("M")
    for c in ("IPCA ocorrido", "Focus mais recente"):
        d[c] = pd.to_numeric(d[c].astype(str).str.replace(",", "."), errors="coerce")
    ocorrido = d.dropna(subset=["IPCA ocorrido"]).set_index("periodo")["IPCA ocorrido"]
    focus = d.dropna(subset=["Focus mais recente"]).set_index("periodo")["Focus mais recente"]
    return ocorrido, focus


def caminho_ipca(ocorrido, focus, choque_pp):
    """{mês: (IPCA 12m, fonte)}: realizado até o último dado e Focus depois, com o choque do cenário."""
    ultimo = ocorrido.index.max()
    caminho = {p: (v, "ocorrido") for p, v in ocorrido.items()}
    for p, v in focus.items():
        if p > ultimo:
            meses = p.ordinal - ultimo.ordinal
            caminho[p] = (v + choque_pp * min(meses / 12, 1), "Focus")
    return caminho


def ipca_do_mes(caminho, periodo):
    if periodo in caminho:
        return caminho[periodo]
    return caminho[max(caminho)][0], "Focus (último valor mantido)"   # só ocorre além do fim do Focus


def estimar_ganho_real(sm, ocorrido):
    """Ganho real médio do salário mínimo sobre o IPCA de dezembro do ano anterior (premissa dos anos futuros)."""
    pct = (sm.set_index("ano")["salario_minimo_rs"].pct_change() * 100).to_dict()
    return float(np.mean([pct[a] - ocorrido[pd.Period(f"{a - 1}-12")] for a in ANOS_GANHO_REAL]))


def reajuste_salario_minimo(sm, caminho, ganho_real, ano):
    pct = (sm.set_index("ano")["salario_minimo_rs"].pct_change() * 100).to_dict()
    if ano in pct:
        return pct[ano]                                                    # ano já realizado
    return ipca_do_mes(caminho, pd.Period(f"{ano - 1}-12"))[0] + ganho_real   # premissa: IPCA de dez + ganho real


# ---------- Estado atual da carteira ----------
def estado_inicial():
    caminho_base = PROC / "base_analitica.csv"
    if not caminho_base.exists():
        raise SystemExit("Falta data/processed/base_analitica.csv. Rode antes: python src/prepare_data.py")
    cw = pd.read_csv(RAW / "contratos_cw.csv").set_index("id_cw")
    ws = pd.read_csv(RAW / "aprovacoes_ws.csv", parse_dates=["data_aprovacao"])
    base = pd.read_csv(caminho_base, parse_dates=["data_reajuste"])

    ws = ws.merge(cw[["fornecedor"]], left_on="id_cw", right_index=True).sort_values(["id_cw", "ordem"])
    ultimo = ws.groupby("id_cw").tail(1).set_index("id_cw")
    corte = ws["data_aprovacao"].max()
    # Contrato sem WS no último ciclo de 12 meses é tratado como encerrado e não entra na projeção.
    ativo = ultimo["data_aprovacao"] + pd.DateOffset(years=1) > corte
    # Reajuste e spread do último evento: viram o "histórico" do primeiro reajuste projetado.
    ult_reaj = base.sort_values("data_reajuste").groupby("id_cw").tail(1).set_index("id_cw")

    estado = {}
    for id_cw in ultimo.index[ativo]:
        r = ult_reaj.loc[id_cw] if id_cw in ult_reaj.index else None
        estado[id_cw] = dict(valor=ultimo.loc[id_cw, "valor_aprovado"], ordem=int(ultimo.loc[id_cw, "ordem"]),
                             data=ultimo.loc[id_cw, "data_aprovacao"],
                             reaj_ant=np.nan if r is None else r["reajuste_pct"],
                             spread_ant=np.nan if r is None else r["spread_vs_indice_pp"])
    return dict(contratos=cw, historico=ws, estado=estado, corte=corte, encerrados=int((~ativo).sum()))


def projetar(modelo, ctx, caminho, sm_ano, cenario):
    """Simula os reajustes em ordem de data. Cada reajuste muda o gasto do fornecedor e o histórico dos próximos."""
    cw, hist = ctx["contratos"], ctx["historico"]
    estado = {k: dict(v) for k, v in ctx["estado"].items()}
    datas, valores, forn = list(hist["data_aprovacao"].to_numpy()), list(hist["valor_aprovado"]), list(hist["fornecedor"])

    eventos = []
    for id_cw, s in estado.items():
        d = s["data"] + pd.DateOffset(years=1)
        while d <= FIM_PROJECAO:
            eventos.append((d, id_cw))
            d += pd.DateOffset(years=1)
    eventos.sort()

    linhas = []
    for d, id_cw in eventos:
        c, s = cw.loc[id_cw], estado[id_cw]
        ad, av, af = np.array(datas), np.array(valores), np.array(forn)
        janela = (ad > (d - JANELA_SPEND).to_datetime64()) & (ad < d.to_datetime64())
        gasto_total, gasto_forn = av[janela].sum(), av[janela & (af == c["fornecedor"])].sum()
        ipca, fonte = ipca_do_mes(caminho, d.to_period("M") - 1)
        dis, w = sm_ano(d.year), c["peso_mao_de_obra"]

        entrada = pd.DataFrame([dict(
            ipca_12m=ipca, log_spend=np.log10(max(gasto_forn, 1.0)),
            share_spend_fornecedor=gasto_forn / gasto_total if gasto_total > 0 else 0.0,
            reajuste_anterior_pct=s["reaj_ant"], spread_anterior_pp=s["spread_ant"], ordem_reajuste=s["ordem"] + 1,
            tem_teto=c["tem_teto"], teto_pct=c["teto_pct"], dissidio_ref_pct=dis, peso_mao_de_obra=w,
            pressao_salarial_pp=w * (dis - ipca), categoria=c["categoria"])])
        reaj = float(prever_reajuste(modelo, entrada)[0])

        indice = w * dis + (1 - w) * ipca
        novo = s["valor"] * (1 + reaj / 100)
        linhas.append(dict(cenario=cenario, id_cw=id_cw, fornecedor=c["fornecedor"], categoria=c["categoria"],
                           data_prevista=d.date(), ano=d.year, ordem_reajuste=s["ordem"] + 1,
                           valor_anterior=s["valor"], ipca_12m=ipca, ipca_fonte=fonte, dissidio_ref_pct=dis,
                           indice_aplicavel_pct=indice, reajuste_previsto_pct=reaj, valor_projetado=novo,
                           impacto_rs=simular_impacto(s["valor"], reaj)))
        s.update(valor=novo, ordem=s["ordem"] + 1, reaj_ant=reaj, spread_ant=reaj - indice)
        datas.append(d.to_datetime64()); valores.append(novo); forn.append(c["fornecedor"])
    return pd.DataFrame(linhas)


def resumir(proj, por):
    g = proj.groupby(por).agg(n_reajustes=("id_cw", "count"), valor_base_rs=("valor_anterior", "sum"),
                              impacto_rs=("impacto_rs", "sum")).reset_index()
    g["reajuste_medio_ponderado_pct"] = g["impacto_rs"] / g["valor_base_rs"] * 100
    return g


# ---------- Gráficos ----------
def estilo(ax):
    for lado in ("top", "right"):
        ax.spines[lado].set_visible(False)
    ax.tick_params(colors="#0b0b0b", labelsize=9)
    ax.set_axisbelow(True)


def grafico_cenarios(res_ano):
    anos = [a for a in sorted(res_ano["ano"].unique()) if a >= 2027]
    fig, ax = plt.subplots(figsize=(7.5, 4.6))
    larg = 0.26
    for i, cen in enumerate(CENARIOS):
        vals = [res_ano[(res_ano["ano"] == a) & (res_ano["cenario"] == cen)]["reajuste_medio_ponderado_pct"].iloc[0] for a in anos]
        x = np.arange(len(anos)) + (i - 1) * larg
        ax.bar(x, vals, larg * 0.92, color=CORES[cen], label=cen.capitalize())
        for xi, v in zip(x, vals):
            ax.text(xi, v + 0.08, f"{v:.1f}%", ha="center", fontsize=9, color="#0b0b0b")
    ax.set_xticks(np.arange(len(anos))); ax.set_xticklabels(anos)
    ax.set_ylabel("Reajuste médio ponderado pelo valor (%)")
    ax.yaxis.grid(True, color="#e5e4e0"); ax.legend(frameon=False, ncol=3, loc="upper center", bbox_to_anchor=(0.5, 1.1))
    estilo(ax)
    fig.tight_layout(); fig.savefig(FIGS / "projecao_reajuste_cenarios.png", dpi=150); plt.close(fig)


def grafico_categoria(res_cat):
    d = res_cat[(res_cat["cenario"] == "central") & (res_cat["ano"] == 2027)].sort_values("impacto_rs")
    fig, ax = plt.subplots(figsize=(8.5, 4.8))
    ax.barh(d["categoria"], d["impacto_rs"] / 1e6, color=CORES["central"], height=0.62)
    for y, v in enumerate(d["impacto_rs"] / 1e6):
        ax.text(v + 0.03, y, f"{v:.1f}", va="center", fontsize=9, color="#0b0b0b")
    ax.set_xlabel("Impacto anualizado dos reajustes de 2027 (R$ milhões), cenário central")
    ax.xaxis.grid(True, color="#e5e4e0"); estilo(ax)
    fig.tight_layout(); fig.savefig(FIGS / "projecao_impacto_categoria_2027.png", dpi=150); plt.close(fig)


def exemplo(modelo):
    """Uso do modelo para UM contrato, sem rodar a carteira inteira."""
    entrada = pd.DataFrame([dict(ipca_12m=5.2, log_spend=6.5, share_spend_fornecedor=0.03, reajuste_anterior_pct=6.5,
                                 spread_anterior_pp=0.1, ordem_reajuste=3, tem_teto=0, dissidio_ref_pct=7.7,
                                 peso_mao_de_obra=0.8, pressao_salarial_pp=0.8 * (7.7 - 5.2),
                                 categoria="Limpeza e Conservacao")])
    pct, base = float(prever_reajuste(modelo, entrada)[0]), 3_000_000
    print(f"\nExemplo (Limpeza, valor base {brl(base)}): reajuste previsto {pct:.2f}% -> impacto {brl(simular_impacto(base, pct))}")


def main():
    arquivo_modelo = MODELS / "modelo_reajuste.joblib"
    if not arquivo_modelo.exists():
        raise SystemExit("Modelo não encontrado. Rode antes: python src/prepare_data.py e python src/train_model.py")
    modelo = joblib.load(arquivo_modelo)
    ocorrido, focus = carregar_ipca()
    sm = pd.read_csv(RAW / "salario_minimo.csv")
    ctx = estado_inicial()
    ganho = estimar_ganho_real(sm, ocorrido)
    print(f"Data de corte: {ctx['corte'].date()} | contratos ativos: {len(ctx['estado'])} | encerrados (sem WS no último ciclo): {ctx['encerrados']}")
    print(f"Ganho real do salário mínimo (média {ANOS_GANHO_REAL[0]}-{ANOS_GANHO_REAL[-1]}): {ganho:.2f} p.p. sobre o IPCA de dezembro")

    resultados, premissas = [], [
        ("data_corte", ctx["corte"].date()), ("contratos_ativos", len(ctx["estado"])), ("contratos_encerrados", ctx["encerrados"]),
        ("ganho_real_salario_minimo_pp", round(ganho, 2)), ("ultimo_ipca_realizado", ocorrido.index.max()),
        ("ultimo_mes_focus", focus.index.max()), ("horizonte", FIM_PROJECAO.date()),
        ("regra_teto", "teto da cláusula aplicado após o modelo")]
    for nome, choque in CENARIOS.items():
        caminho = caminho_ipca(ocorrido, focus, choque)
        sm_ano = lambda ano: reajuste_salario_minimo(sm, caminho, ganho, ano)
        resultados.append(projetar(modelo, ctx, caminho, sm_ano, nome))
        premissas += [(f"{nome}_choque_ipca_pp", choque), (f"{nome}_salario_minimo_2027_pct", round(sm_ano(2027), 2)),
                      (f"{nome}_salario_minimo_2028_pct", round(sm_ano(2028), 2))]

    proj = pd.concat(resultados, ignore_index=True)
    res_ano, res_cat = resumir(proj, ["cenario", "ano"]), resumir(proj, ["cenario", "ano", "categoria"])
    FIGS.mkdir(parents=True, exist_ok=True)
    proj.round(4).to_csv(REPORTS / "projecao_contratos.csv", index=False)
    res_ano.round(4).to_csv(REPORTS / "projecao_resumo_ano.csv", index=False)
    res_cat.round(4).to_csv(REPORTS / "projecao_resumo_categoria.csv", index=False)
    pd.DataFrame(premissas, columns=["premissa", "valor"]).to_csv(REPORTS / "projecao_premissas.csv", index=False)
    grafico_cenarios(res_ano); grafico_categoria(res_cat)

    ordem = list(CENARIOS)
    print("\nReajuste médio ponderado (%) por ano e cenário")
    print(res_ano.pivot(index="ano", columns="cenario", values="reajuste_medio_ponderado_pct")[ordem].round(2).to_string())
    print("\nImpacto anualizado dos reajustes (R$ milhões)")
    print((res_ano.pivot(index="ano", columns="cenario", values="impacto_rs")[ordem] / 1e6).round(1).to_string())
    print("\nObs.: 2026 = só o restante do ano; 2028 usa o último valor do Focus para o mês sem projeção; "
          "impacto = aumento anualizado do valor dos contratos, não o caixa do ano.")
    exemplo(modelo)


if __name__ == "__main__":
    main()
