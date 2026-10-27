"""
prepare_data.py - monta a base analítica (1 linha por reajuste) a partir de:
contratos (CW), aprovações financeiras (WS) e índices externos (IPCA e salário mínimo).

Etapas: 1) ler  2) validar  3) calcular o reajuste e as variáveis  4) salvar.
Uso: python src/prepare_data.py
"""
from pathlib import Path

import numpy as np
import pandas as pd

RAIZ = Path(__file__).resolve().parents[1]
RAW, PROC, REPORTS = RAIZ / "data" / "raw", RAIZ / "data" / "processed", RAIZ / "reports"

INICIO_ANALISE = "2019-01-01"          # antes disso o gasto de 12 meses do fornecedor ainda não tem histórico
JANELA_SPEND = pd.Timedelta(days=370)  # 12 meses + folga para diferenças de data


def carregar():
    cw = pd.read_csv(RAW / "contratos_cw.csv", parse_dates=["data_inicio"])
    ws = pd.read_csv(RAW / "aprovacoes_ws.csv", parse_dates=["data_aprovacao"])
    sm = pd.read_csv(RAW / "salario_minimo.csv")

    # O arquivo de IPCA usa ';' e vírgula decimal. "IPCA ocorrido" já é o acumulado em 12 meses;
    # os meses futuros (só com Focus) ficam sem valor e saem aqui.
    ipca = pd.read_csv(RAW / "ipca_mensal.csv", sep=";")
    ipca["periodo"] = pd.to_datetime(ipca["DateTime"]).dt.to_period("M")
    ipca["ipca_12m"] = pd.to_numeric(ipca["IPCA ocorrido"].astype(str).str.replace(",", "."), errors="coerce")
    ipca = ipca.dropna(subset=["ipca_12m"]).set_index("periodo")["ipca_12m"]
    return cw, ws, ipca, sm


def validar(cw, ws, ipca, sm):
    """Checa a integridade dos dados antes de calcular qualquer coisa. Falha crítica interrompe o script."""
    checks = []

    def check(nome, ok, detalhe=""):
        checks.append({"verificacao": nome, "ok": bool(ok), "detalhe": detalhe})

    ordenado = ws.sort_values(["id_cw", "ordem"]).groupby("id_cw")
    datas_reajuste = ws.loc[ws["ordem"] >= 1, "data_aprovacao"]
    meses_precisos = set(datas_reajuste.dt.to_period("M") - 1)      # o IPCA usado é o do mês anterior
    anos_precisos = set(datas_reajuste.dt.year) | set(datas_reajuste.dt.year - 1)

    check("id_cw único em contratos", cw["id_cw"].is_unique)
    check("id_ws único em aprovações", ws["id_ws"].is_unique)
    check("Sem WS duplicado para o mesmo contrato e ordem", not ws.duplicated(["id_cw", "ordem"]).any())
    check("Todo WS pertence a um contrato existente", ws["id_cw"].isin(cw["id_cw"]).all())
    check("Todo contrato tem ao menos um WS", cw["id_cw"].isin(ws["id_cw"]).all())
    check("Ordem dos WS contínua (0, 1, 2...)", ordenado["ordem"].apply(lambda s: (s.values == np.arange(len(s))).all()).all())
    check("Datas dos WS crescentes dentro do contrato", ordenado["data_aprovacao"].apply(lambda s: s.is_monotonic_increasing).all())
    check("Valores aprovados positivos e sem nulos", ws["valor_aprovado"].notna().all() and (ws["valor_aprovado"] > 0).all())
    check("Campos obrigatórios do contrato sem nulos",
          cw[["fornecedor", "categoria", "indexador", "peso_mao_de_obra"]].notna().all().all())
    check("peso_mao_de_obra entre 0 e 1", cw["peso_mao_de_obra"].between(0, 1).all())
    check("Recorte sem concorrência (fornecedor único)", cw["tipo_contratacao"].str.contains("sem concorrencia").all())
    faltam_ipca = sorted(str(p) for p in meses_precisos if p not in ipca.index)
    check("IPCA cobre todos os meses necessários", not faltam_ipca, f"faltam: {faltam_ipca}" if faltam_ipca else "")
    faltam_sm = sorted(a for a in anos_precisos if a not in set(sm["ano"]))
    check("Salário mínimo cobre todos os anos necessários", not faltam_sm, f"faltam: {faltam_sm}" if faltam_sm else "")

    rel = pd.DataFrame(checks)
    REPORTS.mkdir(exist_ok=True)
    rel.to_csv(REPORTS / "diagnostico_dados.csv", index=False)

    print(f"Contratos: {len(cw)} | WS: {len(ws)} | categorias: {cw['categoria'].nunique()} | "
          f"WS de {ws['data_aprovacao'].min().date()} a {ws['data_aprovacao'].max().date()}")
    for r in rel.itertuples():
        print(f"  [{'OK' if r.ok else 'FALHA'}] {r.verificacao} {r.detalhe}")
    if not rel["ok"].all():
        raise SystemExit("Validação falhou: corrija os dados de entrada antes de seguir.")


def montar_base(cw, ws, ipca, sm):
    # Cada WS herda o fornecedor do contrato (necessário para somar o gasto por fornecedor).
    ws = ws.merge(cw[["id_cw", "fornecedor"]], on="id_cw").sort_values(["id_cw", "ordem"])
    ws["valor_anterior"] = ws.groupby("id_cw")["valor_aprovado"].shift(1)

    # Reajuste = WS atual vs. WS anterior. A ordem 0 é a aprovação inicial, não é reajuste.
    campos_contrato = ["id_cw", "categoria", "indexador", "peso_mao_de_obra", "tem_teto", "teto_pct"]
    ev = ws[ws["ordem"] >= 1].merge(cw[campos_contrato], on="id_cw")
    ev = ev.rename(columns={"data_aprovacao": "data_reajuste", "ordem": "ordem_reajuste"})
    ev["reajuste_pct"] = (ev["valor_aprovado"] / ev["valor_anterior"] - 1) * 100

    # Índices externos. O IPCA é o acumulado 12m do mês ANTERIOR ao reajuste (o que já se conhece na data).
    ev["ipca_12m"] = (ev["data_reajuste"].dt.to_period("M") - 1).map(ipca.to_dict())
    reajuste_sm = sm.set_index("ano")["salario_minimo_rs"].pct_change() * 100   # proxy pública do dissídio
    ev["dissidio_ref_pct"] = ev["data_reajuste"].dt.year.map(reajuste_sm.to_dict())

    # Índice da cláusula: mistura dissídio e IPCA conforme o peso da mão de obra no contrato.
    w = ev["peso_mao_de_obra"]
    ev["indice_aplicavel_pct"] = w * ev["dissidio_ref_pct"] + (1 - w) * ev["ipca_12m"]
    ev["spread_vs_indice_pp"] = ev["reajuste_pct"] - ev["indice_aplicavel_pct"]   # ganho/perda de negociação

    # Gasto do fornecedor nos 12 meses ANTES do reajuste (datas estritamente anteriores: sem vazamento).
    datas, valores, forn = ws["data_aprovacao"].to_numpy(), ws["valor_aprovado"].to_numpy(), ws["fornecedor"].to_numpy()
    gasto_forn, gasto_total = [], []
    for d, f in zip(ev["data_reajuste"], ev["fornecedor"]):
        janela = (datas > (d - JANELA_SPEND).to_datetime64()) & (datas < d.to_datetime64())
        gasto_total.append(valores[janela].sum())
        gasto_forn.append(valores[janela & (forn == f)].sum())
    gasto_forn, gasto_total = np.array(gasto_forn), np.array(gasto_total)
    ev["spend_fornecedor_12m"] = gasto_forn
    ev["share_spend_fornecedor"] = np.divide(gasto_forn, gasto_total, out=np.full(len(ev), np.nan), where=gasto_total > 0)

    # Histórico do próprio contrato. Calculado ANTES de filtrar o período para não perder o evento anterior.
    ev = ev.sort_values(["id_cw", "ordem_reajuste"])
    ev["reajuste_anterior_pct"] = ev.groupby("id_cw")["reajuste_pct"].shift(1)
    ev["spread_anterior_pp"] = ev.groupby("id_cw")["spread_vs_indice_pp"].shift(1)

    # Variáveis derivadas usadas pelo modelo.
    ev["ano"], ev["mes_reajuste"] = ev["data_reajuste"].dt.year, ev["data_reajuste"].dt.month
    ev["log_spend"] = np.log10(ev["spend_fornecedor_12m"].clip(lower=1))                 # gasto tem cauda longa
    ev["pressao_salarial_pp"] = w * (ev["dissidio_ref_pct"] - ev["ipca_12m"])            # quanto o salário pesa acima do IPCA

    colunas = ["id_cw", "fornecedor", "categoria", "indexador", "data_reajuste", "ano", "mes_reajuste",
               "ordem_reajuste", "valor_anterior", "spend_fornecedor_12m", "share_spend_fornecedor",
               "tem_teto", "teto_pct", "peso_mao_de_obra", "ipca_12m", "dissidio_ref_pct",
               "indice_aplicavel_pct", "reajuste_anterior_pct", "spread_anterior_pp",
               "reajuste_pct", "spread_vs_indice_pp", "log_spend", "pressao_salarial_pp"]
    base = ev[ev["data_reajuste"] >= INICIO_ANALISE][colunas].sort_values(["data_reajuste", "id_cw"]).reset_index(drop=True)
    numericas = base.select_dtypes("number").columns
    base[numericas] = base[numericas].round(4)
    return base


def main():
    cw, ws, ipca, sm = carregar()
    validar(cw, ws, ipca, sm)
    base = montar_base(cw, ws, ipca, sm)

    PROC.mkdir(parents=True, exist_ok=True)
    base.to_csv(PROC / "base_analitica.csv", index=False)

    # Só reajuste_anterior/spread_anterior (primeiro reajuste) e teto_pct (sem teto) podem ter vazios.
    nulos = base.isna().sum()
    print(f"\nBase analítica: {len(base)} linhas x {base.shape[1]} colunas | "
          f"{base['data_reajuste'].min().date()} a {base['data_reajuste'].max().date()}")
    print("Colunas com vazios:", nulos[nulos > 0].to_dict())
    print(f"Salvo em {PROC / 'base_analitica.csv'}")


if __name__ == "__main__":
    main()
