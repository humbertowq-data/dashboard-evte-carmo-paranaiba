"""
Dashboard EVTE 2.0 - Analisador Interativo de Estudos de Viabilidade Economico-Financeira
==========================================================================================

RECURSOS:
  - Upload de qualquer PDF de EVTE/EVTEJA (extracao automatica de indicadores e series anuais).
  - Fallback com o dataset de referencia (EVTEJA Carmo do Paranaiba) quando nenhum PDF for enviado.
  - Calculo completo: VPL, TIR, Payback simples/descontado, Indice de Lucratividade,
    ROIC, margens (bruta/EBITDA/liquida), Ponto de Equilibrio.
  - Comparacao entre indicadores extraidos do PDF (conforme reportado no estudo)
    e indicadores recalculados a partir do fluxo de caixa (auditoria cruzada).
  - Visual moderno: tema dark customizado, cards de metricas, abas organizadas,
    graficos Plotly interativos (zoom, hover, exportacao).

INSTALACAO LOCAL:
    pip install streamlit plotly pandas numpy pdfplumber

EXECUCAO LOCAL:
    streamlit run app_evte.py

PUBLICACAO (Streamlit Community Cloud, gratuito):
    1. Suba app_evte.py e requirements.txt na raiz de um repositorio GitHub.
    2. Acesse share.streamlit.io -> New app -> selecione o repositorio/arquivo.
    3. Deploy. Compartilhe a URL gerada.
"""

import re
import io
import numpy as np
import pandas as pd
import streamlit as st
import plotly.graph_objects as go

try:
    import pdfplumber
    PDF_OK = True
except ImportError:
    PDF_OK = False

# ============================================================
# CONFIGURACAO DA PAGINA E TEMA VISUAL
# ============================================================

st.set_page_config(
    page_title="Dashboard EVTE | Análise de Viabilidade",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

CUSTOM_CSS = """
<style>
    .main { background-color: #0e1117; }
    div[data-testid="metric-container"] {
        background: linear-gradient(135deg, #1a1f2e 0%, #232937 100%);
        border: 1px solid #2d3548;
        border-radius: 12px;
        padding: 16px 18px;
        box-shadow: 0 4px 12px rgba(0,0,0,0.25);
    }
    div[data-testid="stMetricLabel"] { font-weight: 600; opacity: 0.85; }
    div[data-testid="stMetricValue"] { font-size: 1.6rem; }
    .stTabs [data-baseweb="tab-list"] { gap: 4px; }
    .stTabs [data-baseweb="tab"] {
        background-color: #1a1f2e;
        border-radius: 8px 8px 0 0;
        padding: 8px 20px;
    }
    .stTabs [aria-selected="true"] { background-color: #2d5ba3 !important; }
    h1, h2, h3 { font-weight: 700; }
    .badge-ok { background:#1e4d2b; color:#4ade80; padding:4px 12px; border-radius:20px; font-weight:600; }
    .badge-warn { background:#4d1e1e; color:#f87171; padding:4px 12px; border-radius:20px; font-weight:600; }
    .info-box { background:#1a1f2e; border-left:4px solid #2d5ba3; padding:12px 16px; border-radius:6px; margin:8px 0; }
</style>
"""
st.markdown(CUSTOM_CSS, unsafe_allow_html=True)


# ============================================================
# MODULO DE EXTRACAO DE PDF
# ============================================================

def parse_numero_br(s):
    if s is None:
        return None
    s = s.strip().replace(' ', '').replace('.', '').replace(',', '.')
    try:
        return float(s)
    except ValueError:
        return None


PADROES_INDICADORES = {
    "VPL (R$)": r"Valor Presente L[ií]quido[^\n]{0,60}?R\$\s*([\-\d\.,]+)",
    "TIR (%)": r"TIR\s*\([^)]*\)?[^\d%\n]{0,40}?([\d,]+)\s*%",
    "Payback (anos)": r"Payback[^\d\n]{0,30}?:?\s*(\d+[.,]?\d*)",
    "WACC / TMA (%)": r"(?:WACC|Taxa M[ií]nima de Atratividade|TMA)[^\d%\n]{0,40}?([\d,]+)\s*%",
    "ROIC (%)": r"ROIC[^)]*\)?[^\d%\n]{0,40}?([\d,]+)\s*%",
    "Margem Bruta (%)": r"Margem Bruta[^%\n]{0,40}?([\d,]+)\s*%",
    "Margem EBITDA (%)": r"Margem EBITDA[^%\n]{0,40}?([\d,]+)\s*%",
    "Margem Liquida (%)": r"Margem L[ií]quida[^%\n]{0,40}?([\d,]+)\s*%",
    "Margem de Contribuicao (%)": r"\(%\)\s*Margem de Contribui[çc][ãa]o[^%\n]{0,40}?([\d,]+)\s*%",
    "Ponto de Equilibrio (R$)": r"Ponto de Equil[ií]brio[^\n]{0,60}?R\$\s*([\d\.,]+)",
    "Valor de Contrato (R$)": r"Valor (?:de|Estimado de) Contrato[^\n]{0,60}?R\$\s*([\d\.,]+)",
    "Custo Capital Proprio (%)": r"Custo (?:Real )?(?:de|do) Capital Pr[óo]prio[^\d%\n]{0,40}?([\d,]+)\s*%",
    "Custo Capital Terceiros (%)": r"Custo (?:Real )?(?:de|do) Capital de Terceiros[^\d%\n]{0,40}?([\d,]+)\s*%",
    "Investimento Total / CAPEX (R$)": r"(?:INVESTIMENTO TOTAL|Investimento Total|CAPEX Total)[^\n]{0,60}?R\$\s*([\d\.,]+)",
}


def extrair_texto_completo(arquivo_pdf):
    texto_paginas = []
    with pdfplumber.open(arquivo_pdf) as pdf:
        for pagina in pdf.pages:
            texto_paginas.append(pagina.extract_text() or "")
    return "\n".join(texto_paginas), len(texto_paginas)


def extrair_indicadores(texto_completo):
    resultados = {}
    for nome, padrao in PADROES_INDICADORES.items():
        matches = re.findall(padrao, texto_completo, re.IGNORECASE)
        resultados[nome] = parse_numero_br(matches[0]) if matches else None
    return resultados


def extrair_serie_anual(texto_completo, palavra_chave):
    idx = texto_completo.lower().find(palavra_chave.lower())
    if idx == -1:
        return {}
    trecho = texto_completo[idx: idx + 6000]
    linhas = trecho.split("\n")
    padrao_linha = r"^\s*(\d{1,2})\s+(-?)\s*R?\$?\s*([\d\.,]+)\s*$"
    serie = {}
    for linha in linhas:
        m = re.match(padrao_linha, linha.strip())
        if m:
            ano = int(m.group(1))
            if 1 <= ano <= 50:
                sinal = -1 if m.group(2) == '-' else 1
                valor = parse_numero_br(m.group(3))
                if valor is not None:
                    serie[ano] = valor * sinal
    return serie


def analisar_pdf(arquivo_pdf):
    texto_completo, n_paginas = extrair_texto_completo(arquivo_pdf)
    indicadores = extrair_indicadores(texto_completo)
    ancoras = {
        "fluxo_caixa": ["Fluxo de Caixa Acumulado", "Fluxo de Caixa Livre"],
        "opex": ["OPEX TOTAL projetado", "OPEX Total"],
        "receita": ["Parcela Remunerat", "Receita Anual"],
        "dre": ["Demonstrativo do Resultado do Exerc", "Lucro L[ií]quido"],
    }
    series = {}
    for chave, palavras in ancoras.items():
        for p in palavras:
            serie = extrair_serie_anual(texto_completo, p)
            if serie:
                series[chave] = serie
                break
        else:
            series[chave] = {}
    return indicadores, series, n_paginas, texto_completo


# ============================================================
# DATASET DE REFERENCIA (fallback: EVTEJA Carmo do Paranaiba)
# ============================================================

ANOS_REF = list(range(1, 26))
TMA_REF = 0.0807

fluxo_caixa_acumulado_ref = {
    1: -7_498_677.77, 2: -6_390_709.32, 3: -5_383_645.65, 4: -4_383_042.45,
    5: -3_388_681.26, 6: -2_484_872.47, 7: -1_602_963.06, 8: -723_922.02,
    9: 152_347.63, 10: 1_025_939.63, 11: 1_835_674.54, 12: -2_186_894.69,
    13: -1_215_919.54, 14: -286_281.40, 15: 639_159.92, 16: 1_560_546.34,
    17: 2_441_432.08, 18: 3_307_807.20, 19: 4_171_720.30, 20: 4_517_401.00,
    21: 5_403_405.22, 22: 6_224_140.32, 23: 7_022_855.93, 24: 7_820_853.08,
    25: 8_606_136.05,
}
opex_ref = {
    1: 1_310_237.12, **{a: 1_731_355.73 for a in range(2, 13)},
    **{a: 1_745_538.99 for a in range(13, 26)}
}
receita_ref = {1: 2_246_815.19, **{a: 3_093_852.65 for a in range(2, 26)}}
lucro_liquido_ref = {
    1: -2_865_617.04, 2: 227_065.11, 3: 179_086.57, 4: 224_887.28,
    5: 270_263.89, 6: 479_301.85, 7: 499_393.92, 8: 538_221.72,
    9: 576_861.22, 10: 615_318.81, 11: 772_536.46, 12: 261_893.93,
    13: 593_182.10, 14: 564_620.69, 15: 572_767.46, 16: 580_638.73,
    17: 659_257.70, 18: 652_241.75, 19: 657_020.96, 20: 592_166.76,
    21: 652_299.83, 22: 756_059.71, 23: 736_227.32, 24: 737_621.98,
    25: 762_302.45,
}
indicadores_ref = {
    "VPL (R$)": 0.0, "TIR (%)": 8.07, "Payback (anos)": 15.0,
    "WACC / TMA (%)": 8.07, "ROIC (%)": 6.9, "Margem Bruta (%)": 26.9,
    "Margem EBITDA (%)": 40.1, "Margem Liquida (%)": 19.4,
    "Margem de Contribuicao (%)": 42.94, "Ponto de Equilibrio (R$)": 2_324_058.14,
    "Valor de Contrato (R$)": 76_499_278.83, "Custo Capital Proprio (%)": 10.33,
    "Custo Capital Terceiros (%)": 8.06, "Investimento Total / CAPEX (R$)": 13_891_524.04,
}


# ============================================================
# FUNCOES FINANCEIRAS
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
            return ano - 1 + (-anterior / fluxos_por_ano[ano])
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
            return ano - 1 + (-anterior / fc_desc)
    return np.nan


def indice_lucratividade(taxa, fluxos_por_ano):
    investimento_inicial = fluxos_por_ano.get(1, 0)
    vp_futuros = sum(v / (1 + taxa) ** a for a, v in fluxos_por_ano.items() if a >= 2)
    return vp_futuros / abs(investimento_inicial) if investimento_inicial else np.nan


def fluxo_incremental_de_acumulado(fc_acumulado_dict):
    serie = pd.Series(fc_acumulado_dict).sort_index()
    incremental = serie.diff()
    incremental.iloc[0] = serie.iloc[0]
    return dict(zip(serie.index, incremental.values))


def fmt_moeda(x, pos=None):
    return f'R$ {x/1e6:,.1f}M'


# ============================================================
# SIDEBAR: UPLOAD E PARAMETROS
# ============================================================

st.sidebar.title("📁 Fonte de Dados")

uploaded_file = st.sidebar.file_uploader(
    "Envie o PDF do Estudo de Viabilidade (EVTE/EVTEJA)",
    type=["pdf"],
    help="O sistema tenta extrair automaticamente indicadores e séries de fluxo de caixa. "
         "Se nenhum arquivo for enviado, o dashboard usa o estudo de referência (Carmo do Paranaíba/MG)."
)

usar_pdf = False
indicadores_extraidos = {}
series_extraidas = {}
nome_fonte = "Estudo de Referência: EVTEJA Carmo do Paranaíba/MG (IPGC, 2023)"

if uploaded_file is not None:
    if not PDF_OK:
        st.sidebar.error("Biblioteca pdfplumber não encontrada. Adicione 'pdfplumber' ao requirements.txt.")
    else:
        with st.spinner("Analisando o PDF... extraindo indicadores e séries financeiras."):
            try:
                indicadores_extraidos, series_extraidas, n_paginas, _texto = analisar_pdf(uploaded_file)
                usar_pdf = True
                nome_fonte = f"PDF enviado: {uploaded_file.name} ({n_paginas} páginas analisadas)"
                st.sidebar.success(f"PDF processado com sucesso! {n_paginas} páginas.")
            except Exception as e:
                st.sidebar.error(f"Erro ao processar PDF: {e}")

st.sidebar.markdown("---")
st.sidebar.title("⚙️ Parâmetros de Simulação")

tma_default = indicadores_extraidos.get("WACC / TMA (%)") if usar_pdf and indicadores_extraidos.get("WACC / TMA (%)") else TMA_REF * 100
tma_input = st.sidebar.slider("Taxa Mínima de Atratividade / TMA (% a.a.)", 1.0, 25.0, float(tma_default), 0.1) / 100

st.sidebar.markdown("---")
st.sidebar.caption(f"📄 Fonte ativa:\n\n{nome_fonte}")


# ============================================================
# MONTAGEM DOS DADOS (PDF extraido OU referencia)
# ============================================================

if usar_pdf and series_extraidas.get("fluxo_caixa"):
    fc_acumulado = series_extraidas["fluxo_caixa"]
else:
    fc_acumulado = fluxo_caixa_acumulado_ref
    if usar_pdf:
        st.sidebar.warning("Não foi possível localizar a série de Fluxo de Caixa no PDF. Usando dataset de referência para os gráficos de fluxo.")

anos_disponiveis = sorted(fc_acumulado.keys())
fluxos_incrementais = fluxo_incremental_de_acumulado(fc_acumulado)

opex_serie = series_extraidas.get("opex") if usar_pdf and series_extraidas.get("opex") else opex_ref
receita_serie = series_extraidas.get("receita") if usar_pdf and series_extraidas.get("receita") else receita_ref
dre_serie = series_extraidas.get("dre") if usar_pdf and series_extraidas.get("dre") else lucro_liquido_ref

df = pd.DataFrame({
    "ano": anos_disponiveis,
    "fluxo_caixa_acumulado": [fc_acumulado.get(a, np.nan) for a in anos_disponiveis],
    "fluxo_caixa_livre": [fluxos_incrementais.get(a, np.nan) for a in anos_disponiveis],
    "opex": [opex_serie.get(a, np.nan) for a in anos_disponiveis],
    "receita": [receita_serie.get(a, np.nan) for a in anos_disponiveis],
    "lucro_liquido": [dre_serie.get(a, np.nan) for a in anos_disponiveis],
})

fluxos_dict = dict(zip(df["ano"], df["fluxo_caixa_livre"]))


# ============================================================
# CALCULO DOS INDICADORES RECALCULADOS
# ============================================================

vpl_calc = vpl_fluxo_anual(tma_input, fluxos_dict)
tir_calc = tir_bisseccao(fluxos_dict)
payback_s_calc = payback_simples(fluxos_dict)
payback_d_calc = payback_descontado(tma_input, fluxos_dict)
il_calc = indice_lucratividade(tma_input, fluxos_dict)

receita_total = df["receita"].sum()
opex_total = df["opex"].sum()
lucro_total = df["lucro_liquido"].sum()
margem_liquida_calc = (lucro_total / receita_total * 100) if receita_total else np.nan


# ============================================================
# CABECALHO
# ============================================================

st.title("📊 Dashboard de Viabilidade Econômico-Financeira")
st.markdown(f"<div class='info-box'>📄 <b>Fonte de dados:</b> {nome_fonte}</div>", unsafe_allow_html=True)

viavel = (vpl_calc >= 0) and (tir_calc >= tma_input)
if viavel:
    st.markdown(
        f"<span class='badge-ok'>✅ PROJETO VIÁVEL</span> &nbsp; VPL positivo e TIR "
        f"({tir_calc*100:.2f}%) ≥ TMA ({tma_input*100:.2f}%)",
        unsafe_allow_html=True
    )
else:
    st.markdown(
        f"<span class='badge-warn'>⚠️ ATENÇÃO</span> &nbsp; VPL negativo ou TIR abaixo da TMA "
        f"de {tma_input*100:.2f}% no cenário simulado",
        unsafe_allow_html=True
    )

st.markdown("<br>", unsafe_allow_html=True)


# ============================================================
# ABAS
# ============================================================

tab1, tab2, tab3, tab4 = st.tabs([
    "📈 Visão Geral", "🔍 Indicadores Detalhados", "📊 Análise Gráfica", "📋 Dados & Auditoria"
])

# --- TAB 1: VISAO GERAL ---
with tab1:
    st.subheader("Indicadores-Chave (recalculados a partir do fluxo de caixa)")
    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("VPL", f"R$ {vpl_calc/1e6:,.2f} M")
    c2.metric("TIR", f"{tir_calc*100:.2f}%", delta=f"{(tir_calc-tma_input)*100:+.2f} p.p. vs TMA")
    c3.metric("Payback Simples", f"{payback_s_calc:.1f} anos" if not np.isnan(payback_s_calc) else "N/D")
    c4.metric("Payback Descontado", f"{payback_d_calc:.1f} anos" if not np.isnan(payback_d_calc) else "> horizonte")
    c5.metric("Índice de Lucratividade", f"{il_calc:.2f}" if not np.isnan(il_calc) else "N/D")

    st.markdown("<br>", unsafe_allow_html=True)
    c6, c7, c8, c9 = st.columns(4)
    c6.metric("Receita Total", f"R$ {receita_total/1e6:,.2f} M")
    c7.metric("OPEX Total", f"R$ {opex_total/1e6:,.2f} M")
    c8.metric("Lucro Líquido Acumulado", f"R$ {lucro_total/1e6:,.2f} M")
    c9.metric("Margem Líquida Média", f"{margem_liquida_calc:.1f}%" if not np.isnan(margem_liquida_calc) else "N/D")

    st.markdown("---")
    st.subheader("💰 Fluxo de Caixa Livre Acumulado")
    fig1 = go.Figure()
    cores = ['#f87171' if v < 0 else '#4ade80' for v in df["fluxo_caixa_acumulado"]]
    fig1.add_trace(go.Bar(x=df["ano"], y=df["fluxo_caixa_acumulado"], marker_color=cores, name="Fluxo acumulado"))
    fig1.add_hline(y=0, line_color="white", line_width=1)
    fig1.update_layout(
        template="plotly_dark", xaxis_title="Ano", yaxis_title="R$",
        height=420, hovermode="x unified", plot_bgcolor="#0e1117", paper_bgcolor="#0e1117"
    )
    st.plotly_chart(fig1, use_container_width=True)

# --- TAB 2: INDICADORES DETALHADOS ---
with tab2:
    st.subheader("📑 Indicadores Extraídos do PDF vs. Recalculados")
    st.caption("Comparação entre os valores reportados no documento original (quando encontrados) e os "
               "valores recalculados por este sistema a partir da série de fluxo de caixa, para auditoria cruzada.")

    fonte_indicadores = indicadores_extraidos if usar_pdf else indicadores_ref

    comparacao = pd.DataFrame({
        "Indicador": [
            "VPL (R$)", "TIR (%)", "Payback (anos)", "WACC / TMA (%)", "ROIC (%)",
            "Margem Bruta (%)", "Margem EBITDA (%)", "Margem Líquida (%)",
            "Ponto de Equilíbrio (R$)", "Valor de Contrato (R$)",
            "Custo Capital Próprio (%)", "Custo Capital Terceiros (%)",
        ],
        "Valor no PDF/Referência": [
            fonte_indicadores.get("VPL (R$)"),
            fonte_indicadores.get("TIR (%)"),
            fonte_indicadores.get("Payback (anos)"),
            fonte_indicadores.get("WACC / TMA (%)"),
            fonte_indicadores.get("ROIC (%)"),
            fonte_indicadores.get("Margem Bruta (%)"),
            fonte_indicadores.get("Margem EBITDA (%)"),
            fonte_indicadores.get("Margem Liquida (%)"),
            fonte_indicadores.get("Ponto de Equilibrio (R$)"),
            fonte_indicadores.get("Valor de Contrato (R$)"),
            fonte_indicadores.get("Custo Capital Proprio (%)"),
            fonte_indicadores.get("Custo Capital Terceiros (%)"),
        ],
        "Valor Recalculado (fluxo de caixa)": [
            round(vpl_calc, 2), round(tir_calc * 100, 2), round(payback_s_calc, 2) if not np.isnan(payback_s_calc) else None,
            round(tma_input * 100, 2), None, None, None,
            round(margem_liquida_calc, 2) if not np.isnan(margem_liquida_calc) else None,
            None, round(receita_total, 2), None, None,
        ],
    })
    st.dataframe(comparacao, use_container_width=True, height=460)

    if usar_pdf:
        n_encontrados = sum(1 for v in indicadores_extraidos.values() if v is not None)
        st.info(f"🔎 {n_encontrados} de {len(indicadores_extraidos)} indicadores foram localizados automaticamente no PDF enviado.")

# --- TAB 3: ANALISE GRAFICA ---
with tab3:
    st.subheader("📈 Receita, OPEX e Lucro Líquido por Ano")
    fig2 = go.Figure()
    fig2.add_trace(go.Bar(x=df["ano"], y=df["receita"], name="Receita", marker_color="#60a5fa"))
    fig2.add_trace(go.Bar(x=df["ano"], y=df["opex"], name="OPEX", marker_color="#fb923c"))
    fig2.add_trace(go.Scatter(x=df["ano"], y=df["lucro_liquido"], name="Lucro Líquido",
                               mode="lines+markers", line=dict(color="#4ade80", width=3)))
    fig2.update_layout(
        template="plotly_dark", barmode="group", xaxis_title="Ano", yaxis_title="R$",
        height=440, hovermode="x unified", plot_bgcolor="#0e1117", paper_bgcolor="#0e1117"
    )
    st.plotly_chart(fig2, use_container_width=True)

    col_a, col_b = st.columns(2)
    with col_a:
        st.subheader("🎯 Sensibilidade do VPL à Taxa de Desconto")
        taxas = np.arange(0.01, 0.25, 0.005)
        vpls = [vpl_fluxo_anual(t, fluxos_dict) for t in taxas]
        fig3 = go.Figure()
        fig3.add_trace(go.Scatter(x=taxas * 100, y=vpls, mode="lines", line=dict(color="#a78bfa", width=3)))
        fig3.add_hline(y=0, line_color="white", line_width=1)
        fig3.add_vline(x=tma_input * 100, line_dash="dash", line_color="#f87171",
                       annotation_text=f"TMA {tma_input*100:.2f}%")
        if not np.isnan(tir_calc):
            fig3.add_vline(x=tir_calc * 100, line_dash="dot", line_color="#4ade80",
                           annotation_text=f"TIR {tir_calc*100:.2f}%")
        fig3.update_layout(
            template="plotly_dark", xaxis_title="Taxa (%)", yaxis_title="VPL (R$)",
            height=400, plot_bgcolor="#0e1117", paper_bgcolor="#0e1117"
        )
        st.plotly_chart(fig3, use_container_width=True)

    with col_b:
        st.subheader("💹 Payback Visual")
        acumulado_simples = np.cumsum(df["fluxo_caixa_livre"].fillna(0).values)
        fig4 = go.Figure()
        fig4.add_trace(go.Scatter(x=df["ano"], y=acumulado_simples, mode="lines+markers",
                                   line=dict(color="#fb7185", width=3)))
        fig4.add_hline(y=0, line_color="white", line_width=1)
        if not np.isnan(payback_s_calc):
            fig4.add_vline(x=payback_s_calc, line_dash="dash", line_color="#4ade80",
                           annotation_text=f"Payback: {payback_s_calc:.1f}a")
        fig4.update_layout(
            template="plotly_dark", xaxis_title="Ano", yaxis_title="R$ (acumulado)",
            height=400, plot_bgcolor="#0e1117", paper_bgcolor="#0e1117"
        )
        st.plotly_chart(fig4, use_container_width=True)

# --- TAB 4: DADOS & AUDITORIA ---
with tab4:
    st.subheader("📋 Tabela Detalhada")
    df_show = df.copy()
    df_show.columns = ["Ano", "Fluxo Acumulado", "Fluxo Livre", "OPEX", "Receita", "Lucro Líquido"]
    st.dataframe(
        df_show.style.format({c: "R$ {:,.2f}" for c in df_show.columns if c != "Ano"}),
        use_container_width=True, height=400
    )
    csv = df_show.to_csv(index=False).encode("utf-8-sig")
    st.download_button("⬇️ Baixar dados em CSV", csv, "dados_evte.csv", "text/csv")

    if usar_pdf:
        st.markdown("---")
        st.subheader("🧾 Todos os Indicadores Extraídos do PDF")
        df_ind = pd.DataFrame(list(indicadores_extraidos.items()), columns=["Indicador", "Valor"])
        st.dataframe(df_ind, use_container_width=True, height=380)

st.markdown("---")
st.caption("Dashboard interativo de análise de viabilidade econômico-financeira. "
           "Os cálculos de VPL/TIR/Payback são recalculados localmente a partir da série de fluxo de caixa "
           "(extraída do PDF ou do dataset de referência) e servem como apoio à tomada de decisão, "
           "não substituindo a análise de um profissional habilitado.")
