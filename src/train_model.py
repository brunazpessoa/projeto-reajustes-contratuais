"""
train_model.py - treina e avalia o modelo de reajuste contratual.

Pergunta: dado o contexto de um contrato na data do reajuste (IPCA, referência salarial, peso da mão
de obra, gasto do fornecedor e histórico), qual será o % de reajuste?
O modelo só conta como ganho se superar baselines simples no período de teste.

Uso: python src/train_model.py   (rodar antes: python src/prepare_data.py)
"""
from pathlib import Path

import joblib
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.patches import Patch
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LinearRegression, Ridge
from sklearn.model_selection import GridSearchCV, TimeSeriesSplit
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

RAIZ = Path(__file__).resolve().parents[1]
PROC, MODELS, REPORTS = RAIZ / "data" / "processed", RAIZ / "models", RAIZ / "reports"
FIGS = REPORTS / "figures"

CORTE_TESTE = "2025-01-01"   # treino: antes desta data | teste: a partir dela (o tempo não é embaralhado)
ALVO = "reajuste_pct"
PRINCIPAL = "Regressão linear + índice salarial"

# Entradas: só o que já se sabe na data do reajuste. indice_aplicavel_pct e spread_vs_indice_pp
# ficam de fora porque entregam (quase) a resposta; servem só como baseline.
NUM_BASE = ["ipca_12m", "log_spend", "share_spend_fornecedor", "reajuste_anterior_pct",
            "spread_anterior_pp", "ordem_reajuste", "tem_teto"]
NUM_SALARIAL = ["dissidio_ref_pct", "peso_mao_de_obra", "pressao_salarial_pp"]
NUM_SPREAD = ["log_spend", "share_spend_fornecedor", "reajuste_anterior_pct",
              "spread_anterior_pp", "ordem_reajuste", "tem_teto"]
CAT = ["categoria"]

AZUL, LARANJA, CINZA, TEXTO, GRADE = "#2a78d6", "#eb6834", "#9a9992", "#0b0b0b", "#e5e4e0"


def montar_pipeline(num, estimador):
    """Imputação, escala e one-hot ficam dentro do pipeline: tudo é aprendido só com o treino."""
    prep = ColumnTransformer([
        ("num", Pipeline([("imp", SimpleImputer(strategy="median")), ("esc", StandardScaler())]), num),
        ("cat", OneHotEncoder(handle_unknown="ignore"), CAT),
    ])
    return Pipeline([("prep", prep), ("modelo", estimador)])


def metricas(nome, tipo, real, prev):
    erro = np.asarray(prev) - np.asarray(real)
    return {"modelo": nome, "tipo": tipo, "mae_pp": np.abs(erro).mean(),
            "rmse_pp": np.sqrt((erro ** 2).mean()), "vies_pp": erro.mean()}   # vies > 0: prevê acima do real


def estilo(ax):
    for lado in ("top", "right"):
        ax.spines[lado].set_visible(False)
    ax.tick_params(colors=TEXTO, labelsize=9)


def grafico_mae(res):
    res = res.sort_values("mae_pp", ascending=False)
    fig, ax = plt.subplots(figsize=(9, 4.8))
    cores = [AZUL if t == "modelo" else CINZA for t in res["tipo"]]
    ax.barh(res["modelo"], res["mae_pp"], color=cores, height=0.62)
    for y, v in enumerate(res["mae_pp"]):
        ax.text(v + 0.01, y, f"{v:.2f}", va="center", fontsize=9, color=TEXTO)
    ax.set_xlabel("Erro médio absoluto (p.p.) no teste, 2025 em diante: menor é melhor")
    ax.xaxis.grid(True, color=GRADE); ax.set_axisbelow(True)
    ax.legend(handles=[Patch(color=CINZA, label="Baseline"), Patch(color=AZUL, label="Modelo")], frameon=False, loc="upper right")
    estilo(ax)
    fig.tight_layout(); fig.savefig(FIGS / "mae_modelos_vs_baselines.png", dpi=150); plt.close(fig)


def grafico_previsto_real(real, prev, mae):
    fig, ax = plt.subplots(figsize=(5.6, 5.6))
    ax.scatter(real, prev, s=14, alpha=0.5, color=AZUL, edgecolors="none")
    lim = [min(real.min(), prev.min()) - 0.3, max(real.max(), prev.max()) + 0.3]
    ax.plot(lim, lim, color=CINZA, linestyle="--", linewidth=1)
    ax.set_xlim(lim); ax.set_ylim(lim)
    ax.set_xlabel("Reajuste real (%)"); ax.set_ylabel("Reajuste previsto (%)")
    ax.set_title(f"{PRINCIPAL}: teste (MAE {mae:.2f} p.p.)", fontsize=10, color=TEXTO)
    ax.grid(True, color=GRADE); ax.set_axisbelow(True)
    estilo(ax)
    fig.tight_layout(); fig.savefig(FIGS / "previsto_vs_real.png", dpi=150); plt.close(fig)


def grafico_coeficientes(coef):
    top = coef.reindex(coef.abs().sort_values(ascending=False).index)[:12][::-1]
    fig, ax = plt.subplots(figsize=(8, 4.8))
    ax.barh(top.index, top.values, color=[AZUL if v > 0 else LARANJA for v in top.values], height=0.62)
    ax.axvline(0, color=TEXTO, linewidth=0.8)
    ax.set_xlabel("Efeito no reajuste previsto (p.p.); variáveis numéricas padronizadas")
    ax.legend(handles=[Patch(color=AZUL, label="Aumenta o reajuste"), Patch(color=LARANJA, label="Reduz o reajuste")],
              frameon=False, loc="lower right")
    ax.xaxis.grid(True, color=GRADE); ax.set_axisbelow(True)
    estilo(ax)
    fig.tight_layout(); fig.savefig(FIGS / "coeficientes.png", dpi=150); plt.close(fig)


def main():
    df = pd.read_csv(PROC / "base_analitica.csv", parse_dates=["data_reajuste"]).sort_values("data_reajuste")
    treino, teste = df[df["data_reajuste"] < CORTE_TESTE], df[df["data_reajuste"] >= CORTE_TESTE]
    y_tr, y_te = treino[ALVO], teste[ALVO]
    print(f"Treino: {len(treino)} reajustes (até 2024) | Teste: {len(teste)} reajustes (2025 em diante)")

    # Baselines: referências simples que o modelo precisa vencer.
    resultados = [
        metricas("Média do treino", "baseline", y_te, np.full(len(teste), y_tr.mean())),
        metricas("Reajuste = IPCA 12m", "baseline", y_te, teste["ipca_12m"]),
        metricas("Índice da cláusula", "baseline", y_te, teste["indice_aplicavel_pct"]),
        metricas("Índice da cláusula + spread médio", "baseline", y_te,
                 teste["indice_aplicavel_pct"] + treino["spread_vs_indice_pp"].mean()),
    ]

    # Modelos. A: só IPCA e gasto (mostra o que o índice salarial acrescenta). B: o principal.
    cols_a, cols_b = NUM_BASE + CAT, NUM_BASE + NUM_SALARIAL + CAT
    m_a = montar_pipeline(NUM_BASE, LinearRegression()).fit(treino[cols_a], y_tr)
    m_b = montar_pipeline(NUM_BASE + NUM_SALARIAL, LinearRegression()).fit(treino[cols_b], y_tr)

    # Ridge: o alpha é escolhido só dentro do treino, com validação que respeita a ordem do tempo.
    busca = GridSearchCV(montar_pipeline(NUM_BASE + NUM_SALARIAL, Ridge()), {"modelo__alpha": [0.01, 0.1, 1, 10, 100]},
                         cv=TimeSeriesSplit(5), scoring="neg_mean_absolute_error").fit(treino[cols_b], y_tr)
    print(f"Ridge: melhor alpha no treino = {busca.best_params_['modelo__alpha']}")

    # Alternativa: aceitar o índice da cláusula e prever só o spread (o que sobra da negociação).
    m_sp = montar_pipeline(NUM_SPREAD, LinearRegression()).fit(treino[NUM_SPREAD + CAT], treino["spread_vs_indice_pp"])

    prev_b = m_b.predict(teste[cols_b])
    resultados += [
        metricas("Regressão linear (só IPCA)", "modelo", y_te, m_a.predict(teste[cols_a])),
        metricas(PRINCIPAL, "modelo", y_te, prev_b),
        metricas("Ridge + índice salarial", "modelo", y_te, busca.best_estimator_.predict(teste[cols_b])),
        metricas("Índice da cláusula + spread previsto", "modelo", y_te,
                 teste["indice_aplicavel_pct"] + m_sp.predict(teste[NUM_SPREAD + CAT])),
    ]

    res = pd.DataFrame(resultados)
    mae_media = res.loc[res["modelo"] == "Média do treino", "mae_pp"].iloc[0]
    res["ganho_vs_media_pct"] = (1 - res["mae_pp"] / mae_media) * 100
    REPORTS.mkdir(exist_ok=True); FIGS.mkdir(exist_ok=True); MODELS.mkdir(exist_ok=True)
    res.round(4).to_csv(REPORTS / "model_metrics.csv", index=False)
    print("\n" + res.round(2).to_string(index=False))

    # Conclusão automática: o resultado é reportado como saiu, mesmo quando o modelo não ganha.
    mae_p = res.loc[res["modelo"] == PRINCIPAL, "mae_pp"].iloc[0]
    print(f"\nModelo principal ('{PRINCIPAL}', MAE {mae_p:.2f} p.p.):")
    for r in res[res["tipo"] == "baseline"].itertuples():
        print(f"  {'ganha de' if mae_p < r.mae_pp else 'PERDE para'} '{r.modelo}' (MAE {r.mae_pp:.2f})")

    # Onde o modelo erra mais: erro por categoria no teste.
    por_cat = (teste.assign(erro_abs=np.abs(prev_b - y_te)).groupby("categoria")["erro_abs"]
               .agg(n="count", mae_pp="mean").sort_values("mae_pp", ascending=False))
    por_cat.round(4).to_csv(REPORTS / "erro_por_categoria.csv")

    # Coeficientes: numéricas padronizadas, então comparáveis entre si.
    nomes = [n.split("__", 1)[1] for n in m_b.named_steps["prep"].get_feature_names_out()]
    coef = pd.Series(m_b.named_steps["modelo"].coef_, index=nomes)
    coef.reindex(coef.abs().sort_values(ascending=False).index).round(4).to_csv(REPORTS / "coeficientes.csv", header=["coeficiente_pp"])

    grafico_mae(res); grafico_previsto_real(y_te, pd.Series(prev_b, index=y_te.index), mae_p); grafico_coeficientes(coef)

    # Modelo salvo: mesma especificação do principal, reajustada com TODOS os dados (treino + teste),
    # que é o que se usa para projetar 2027 em diante. As métricas acima são do modelo treinado só até 2024.
    final = montar_pipeline(NUM_BASE + NUM_SALARIAL, LinearRegression()).fit(df[cols_b], df[ALVO])
    joblib.dump({"pipeline": final, "colunas": cols_b, "alvo": ALVO,
                 "treinado_ate": str(df["data_reajuste"].max().date())}, MODELS / "modelo_reajuste.joblib")
    print(f"\nSalvos: {MODELS / 'modelo_reajuste.joblib'}, reports/model_metrics.csv e reports/figures/")


if __name__ == "__main__":
    main()
