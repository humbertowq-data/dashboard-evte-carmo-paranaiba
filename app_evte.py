import numpy as np
import pandas as pd
import streamlit as st
import plotly.graph_objects as go
from plotly.subplots import make_subplots

st.set_page_config(page_title="Dashboard EVTE - Carmo do Paranaíba", layout="wide")

# ============================================================
# 1. DADOS DE ENTRADA (extraidos do EVTEJA - Carmo do Paranaiba)
# ============================================================

ANOS = list(range(1, 26))  # Concessao de 25 anos
TMA_ESTUDO = 0.0807  # 8,07% a.a. (WACC/TMA original do estudo)

capex_inicial = {
    "Iluminação Pública": 3_687_232.89,
    "Telecomunicações": 2_090_895.44,
    "Usina Fotovoltaica": 1_414_906.90,
}
CAPEX_INICIAL_TOTAL = sum(capex_inicial.values())

reinvestimentos = {a: 0.0 for a in ANOS}
reinvestimentos[12] = 5_070_667.74
reinvestimentos[20] = 551_642.14

opex_anual = {
    1: 1_310_237.12, 2: 1_731_355.73, 3: 1_731_355.73, 4: 1_731_355.73,
    5: 1_731_355.73, 6: 1_731_355.73, 7: 1_731_355.73, 8: 1_731_355.73,
    9: 1_731_355.73, 10: 1_731_355.73, 11: 1_731_355.73, 12: 1_731_355.73,
    13: 1_745_538.99, 14: 1_745_538.99, 15: 1_745_538.99, 16: 1_745_538.99,
    17: 1_745_538.99, 18: 1_745_538.99, 19: 1_745_538.99, 20: 1_745_538.99,
    21: 1_745_538.99, 22: 1_745_538.99, 23: 1_745_538.99, 24: 1_745_538.99,
    25: 1_745_538.99,
}

receita_anual = {
    1: 2_246_815.19, 2: 3_093_852.65, 3: 3_093_852.65, 4: 3_093_852.65,
    5: 3_093_852.65, 6: 3_093_852.65, 7: 3_093_852.65, 8: 3_093_852.65,
    9: 3_093_852.65, 10: 3_093_852.65, 11: 3_093_852.65, 12: 3_093_852.65,
    13: 3_093_852.65, 14: 3_093_852.65, 15: 3_093_852.65, 16: 3_093_852.65,
    17: 3_093_852.65, 18: 3_093_852.65, 19: 3_093_852.65, 20: 3_093_852.65,
    21: 3_093_852.65, 22: 3_093_852.65, 23: 3_093_852.65, 24: 3_093_852.65,
    25: 3_093_852.65,
}

fluxo_caixa_acumulado_estudo = {
    1: -7_498_677.77, 2: -6_390_709.32, 3: -5_383_645.65, 4: -4_383_042.45,
    5: -3_388_681.26, 6: -2_484_872.47, 7: -1_602_963.06, 8: -723_922.02,
    9: 152_347.63, 10: 1_025_939.63, 11: 1_835_674.54, 12: -2_186_894.69,
    13: -1_215_919.54, 14: -286_281.40, 15: 639_159.92, 16: 1_560_546.34,
    17: 2_441_432.08, 18: 3_307_807.20, 19: 4_171_720.30, 20: 4_517_401.00,
    21: 5_403_405.22, 22: 6_224_140.32, 23: 7_022_855.93, 24: 7_820_853.08,
    25: 8_606_136.05,
}

lucro_liquido_anual = {
    1: -2_865_617.04, 2: 227_065.11, 3: 179_086.57, 4: 224_887.28,
    5: 270_263.89, 6: 479_301.85, 7: 499_393.92, 8: 538_221.72,
    9: 576_861.22, 10: 615_318.81, 11: 772_536.46, 12: 261_893.93,
    13: 593_182.10, 14: 564_620.69, 15: 572_767.46, 16: 580_638.73,
    17: 659_257.70, 18: 652_241.75, 19: 657_020.96, 20: 592_166.76,
    21: 652_299.83, 22: 756_059.71, 23: 736_227.32, 24: 737_621.98,
    25: 762_302.45,
}

VALOR_CONTRATO = 76_499_278.83

fc_acum_series = pd.Series(fluxo_caixa_acumulado_estudo).sort_index()
fluxo_caixa_incremental = fc_acum_series.diff()
fluxo_caixa_incremental.iloc[0] = fc_acum_series.iloc[0]

df = pd.DataFrame({
    "ano": ANOS,
    "capex_reinvestimento": [reinvestimentos[a] for a in ANOS],
    "opex": [opex_anual[a] for a in ANOS],
    "receita_prm": [receita_anual[a] for a in ANOS],
    "lucro_liquido": [lucro_liquido_anual[a] for a in ANOS],
    "fluxo_caixa_livre": fluxo_caixa_incremental.values,
    "fluxo_caixa_acumulado": fc_acum_series.values,
})

fluxos_dict = dict(zip(df["ano"], df["fluxo_caixa_livre"]))


# ============================================================
# 2. FUNCOES DE CALCULO FINANCEIRO
# ============================================================

def vpl_fluxo_anual(taxa, fluxos_por_ano):
    return sum(v / (1 + taxa) ** ano for ano, v in fluxos_por_ano.items())


def tir_bisseccao(fluxos_por_ano, low=-0.99, high=5.0, tol=1e-7, max_iter=200):
    f = lambda r: vpl_fluxo_anual(r, fluxos_por_ano)
    f_low, f_high = f(low), f(high)
    if f_low * f_high > 0:
        for hi in [1, 2, 3, 5, 10]:
            if f(low) * f(hi) < 0:
                high = hi
                break
        else:
            return np.nan
    for _ in range(max_iter):
        mid = (low + high) / 2
        f_mid = f(mid)
        if abs(f_mid) < tol:
            return mid
        if f(low) * f_mid < 0:
            high = mid
        else:
            low = mid
    return (low + high) / 2


def payback_simples(fluxos_por_ano):
    acumulado = 0
    for ano in sorted(fluxos_por_ano):
        anterior = acumulado
        acumulado += fluxos_por_ano[ano]
        if acumulado >= 0:
            if fluxos_por_ano[ano] == 0:
                return ano
            fracao = -anterior / fluxos_por_ano[ano]
            return ano - 1 + fracao
    return np.nan


def payback_descontado(taxa, fluxos_por_ano):
    acumulado = 0
    for ano in sorted(fluxos_por_ano):
        fc_desc = fluxos_por_ano[ano] / (1 + taxa) ** ano
        anterior = acumulado
        acumulado += fc_desc
        if acumulado >= 0:
            if fc_desc == 0:
                return ano
            fracao = -anterior / fc_desc
            return ano - 1 + fracao
    return np.nan


# ============================================================
# 3. SIDEBAR - CONTROLES INTERATIVOS
# ============================================================

st.sidebar.title("⚙️ Parâmetros da Análise")
st.sidebar.markdown("Ajuste a taxa de desconto para simular cenários e ver o impacto nos indicadores em tempo real.")

tma_input = st.sidebar.slider(
    "Taxa Mínima de Atratividade / TMA (% a.a.)",
    min_value=2.0, max_value=20.0, value=TMA_ESTUDO * 100, step=0.1
) / 100

anos_filtro = st.sidebar.slider(
    "Horizonte de análise (anos)",
    min_value=5, max_value=25, value=25, step=1
)

st.sidebar.markdown("---")
st.sidebar.caption("Fonte dos dados: EVTEJA - Estudo de Viabilidade Técnica, Econômica, "
                    "Jurídica e Ambiental para PPP de Iluminação Pública, Telecomunicações "
                    "e Usina Fotovoltaica de Carmo do Paranaíba/MG (IPGC, 2023).")

df_filtrado = df[df["ano"] <= anos_filtro].copy()
fluxos_filtrado = {a: v for a, v in fluxos_dict.items() if a <= anos_filtro}

# ============================================================
# 4. CALCULO DOS INDICADORES (reativos ao slider)
# ============================================================

vpl_projeto = vpl_fluxo_anual(tma_input, fluxos_filtrado)
tir_projeto = tir_bisseccao(fluxos_filtrado)
payback_simples_anos = payback_simples(fluxos_filtrado)
payback_descontado_anos = payback_descontado(tma_input, fluxos_filtrado)

investimento_inicial_t0 = fluxos_filtrado[1]
vp_fluxos_futuros = sum(v / (1 + tma_input) ** a for a, v in fluxos_filtrado.items() if a >= 2)
indice_lucratividade_valor = (
    vp_fluxos_futuros / abs(investimento_inicial_t0) if investimento_inicial_t0 else np.nan
)

receita_total = df_filtrado["receita_prm"].sum()
opex_total = df_filtrado["opex"].sum()
capex_total = CAPEX_INICIAL_TOTAL + df_filtrado["capex_reinvestimento"].sum()
lucro_liquido_total = df_filtrado["lucro_liquido"].sum()
margem_liquida_media = lucro_liquido_total / receita_total if receita_total else np.nan


# ============================================================
# 5. LAYOUT PRINCIPAL
# ============================================================

st.title("📊 Dashboard de Viabilidade Econômico-Financeira")
st.subheader("PPP Cidade Inteligente — Carmo do Paranaíba/MG")
st.caption("Iluminação Pública · Infraestrutura de Telecomunicações · Usina Fotovoltaica de Geração Distribuída")

# --- Cartões de indicadores-chave ---
col1, col2, col3, col4, col5 = st.columns(5)
col1.metric("VPL", f"R$ {vpl_projeto/1e6:,.2f} M", help="Valor Presente Líquido descontado à TMA selecionada")
col2.metric("TIR", f"{tir_projeto*100:.2f}%", delta=f"{(tir_projeto - tma_input)*100:+.2f} p.p. vs TMA")
col3.metric("Payback Simples", f"{payback_simples_anos:.1f} anos")
col4.metric("Payback Descontado", f"{payback_descontado_anos:.1f} anos" if not np.isnan(payback_descontado_anos) else "> horizonte")
col5.metric("Índice de Lucratividade", f"{indice_lucratividade_valor:.2f}")

st.markdown("---")

col_a, col_b, col_c, col_d = st.columns(4)
col_a.metric("CAPEX Total", f"R$ {capex_total/1e6:,.2f} M")
col_b.metric("OPEX Total", f"R$ {opex_total/1e6:,.2f} M")
col_c.metric("Receita Total", f"R$ {receita_total/1e6:,.2f} M")
col_d.metric("Margem Líquida Média", f"{margem_liquida_media*100:.1f}%")

# Alerta de decisão
if vpl_projeto >= 0 and tir_projeto >= tma_input:
    st.success(f"✅ Projeto **viável** no cenário atual: VPL positivo e TIR ({tir_projeto*100:.2f}%) ≥ TMA ({tma_input*100:.2f}%).")
else:
    st.error(f"⚠️ Projeto **inviável** no cenário simulado: VPL negativo ou TIR abaixo da TMA de {tma_input*100:.2f}%.")

st.markdown("---")

# --- Grafico 1: Fluxo de caixa acumulado ---
st.subheader("💰 Fluxo de Caixa Livre Acumulado")
fig1 = go.Figure()
cores = ['#d62728' if v < 0 else '#2ca02c' for v in df_filtrado["fluxo_caixa_acumulado"]]
fig1.add_trace(go.Bar(x=df_filtrado["ano"], y=df_filtrado["fluxo_caixa_acumulado"],
                       marker_color=cores, name="Fluxo acumulado"))
fig1.add_hline(y=0, line_color="black", line_width=1)
fig1.update_layout(xaxis_title="Ano da concessão", yaxis_title="R$",
                    height=420, hovermode="x unified")
st.plotly_chart(fig1, use_container_width=True)

# --- Grafico 2: Receita x OPEX x Lucro liquido ---
st.subheader("📈 Receita, OPEX e Lucro Líquido por Ano")
fig2 = go.Figure()
fig2.add_trace(go.Bar(x=df_filtrado["ano"], y=df_filtrado["receita_prm"], name="Receita (PRM)", marker_color="#1f77b4"))
fig2.add_trace(go.Bar(x=df_filtrado["ano"], y=df_filtrado["opex"], name="OPEX", marker_color="#ff7f0e"))
fig2.add_trace(go.Scatter(x=df_filtrado["ano"], y=df_filtrado["lucro_liquido"], name="Lucro Líquido",
                           mode="lines+markers", line=dict(color="#2ca02c", width=3)))
fig2.update_layout(barmode="group", xaxis_title="Ano da concessão", yaxis_title="R$",
                    height=420, hovermode="x unified")
st.plotly_chart(fig2, use_container_width=True)

col_pizza, col_sens = st.columns(2)

with col_pizza:
    st.subheader("🥧 Composição do CAPEX Inicial")
    fig3 = go.Figure(data=[go.Pie(labels=list(capex_inicial.keys()),
                                   values=list(capex_inicial.values()),
                                   hole=0.35)])
    fig3.update_layout(height=380)
    st.plotly_chart(fig3, use_container_width=True)

with col_sens:
    st.subheader("🎯 Sensibilidade do VPL à Taxa de Desconto")
    taxas_sensibilidade = np.arange(0.02, 0.20, 0.005)
    vpls_sensibilidade = [vpl_fluxo_anual(t, fluxos_filtrado) for t in taxas_sensibilidade]
    fig4 = go.Figure()
    fig4.add_trace(go.Scatter(x=taxas_sensibilidade * 100, y=vpls_sensibilidade,
                               mode="lines", line=dict(color="#8172b2", width=3)))
    fig4.add_hline(y=0, line_color="black", line_width=1)
    fig4.add_vline(x=tma_input * 100, line_dash="dash", line_color="red",
                   annotation_text=f"TMA {tma_input*100:.2f}%")
    fig4.add_vline(x=tir_projeto * 100, line_dash="dot", line_color="green",
                   annotation_text=f"TIR {tir_projeto*100:.2f}%")
    fig4.update_layout(xaxis_title="Taxa de desconto (%)", yaxis_title="VPL (R$)", height=380)
    st.plotly_chart(fig4, use_container_width=True)

st.markdown("---")

# --- Tabela detalhada navegavel ---
st.subheader("📋 Tabela Detalhada do Fluxo de Caixa")
df_exibicao = df_filtrado.copy()
df_exibicao.columns = ["Ano", "CAPEX Reinvest.", "OPEX", "Receita (PRM)",
                        "Lucro Líquido", "Fluxo de Caixa Livre", "Fluxo Acumulado"]
st.dataframe(
    df_exibicao.style.format({col: "R$ {:,.2f}" for col in df_exibicao.columns if col != "Ano"}),
    use_container_width=True,
    height=350
)

csv = df_exibicao.to_csv(index=False).encode("utf-8-sig")
st.download_button("⬇️ Baixar tabela em CSV", csv, "fluxo_caixa_detalhado.csv", "text/csv")

st.markdown("---")
st.caption("Dashboard gerado a partir do EVTEJA de Carmo do Paranaíba (IPGC, 2023). "
           "Os indicadores respondem dinamicamente à TMA selecionada na barra lateral.")
