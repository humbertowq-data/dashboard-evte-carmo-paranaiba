"""
Dashboard EVTE 5.0 - Analisador Executivo de Estudos de Viabilidade Economico-Financeira
==========================================================================================
V5.0: Tema claro (fundo branco) + exportacao de relatorio executivo em PDF.

MANTIDO DA V4.1:
  - Payback relativo ao prazo da concessao, ROE (equity), DSCR, Value for Money,
    Matriz de Riscos, alerta de concentracao de receita, validacao cruzada de extracao.

NOVIDADES V5.0:
  - Tema claro: fundo branco, paleta com contraste validado (WCAG AA) para leitura confortavel.
  - Botao "Exportar Relatorio em PDF": gera um PDF de 1-2 paginas com os indicadores-chave
    e os principais graficos, para enviar a quem nao tem acesso ao link do dashboard.

INSTALACAO LOCAL:
    pip install streamlit plotly pandas numpy pdfplumber kaleido reportlab

EXECUCAO LOCAL:
    streamlit run app_evte.py
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

try:
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import cm
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image as RLImage, Table, TableStyle
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib import colors as rl_colors
    REPORTLAB_OK = True
except ImportError:
    REPORTLAB_OK = False

st.set_page_config(page_title="Dashboard EVTE | Análise Executiva", page_icon="📊", layout="wide", initial_sidebar_state="expanded")

# ============================================================
# PALETA — TEMA CLARO (contraste validado WCAG AA)
# ============================================================

COR_FUNDO = "#f7f8fa"
COR_CARD = "#ffffff"
COR_BORDA = "#e2e5eb"
COR_PRIMARIA = "#2563eb"
COR_SUCESSO = "#16a34a"
COR_ALERTA = "#d97706"
COR_ERRO = "#dc2626"
COR_TEXTO = "#1e293b"
COR_TEXTO_SEC = "#56637a"
COR_ROXO = "#7c3aed"
COR_ROSA = "#db2777"
COR_CIANO = "#0891b2"

def hex_to_rgba(hex_color, alpha):
    hex_color = hex_color.lstrip('#')
    r, g, b = int(hex_color[0:2], 16), int(hex_color[2:4], 16), int(hex_color[4:6], 16)
    return f"rgba({r},{g},{b},{alpha})"

RGBA_LINHA_REF = "rgba(30,41,59,0.25)"
RGBA_ROXO_FRACO = hex_to_rgba(COR_ROXO, 0.12)
RGBA_ROSA_FRACO = hex_to_rgba(COR_ROSA, 0.10)
RGBA_ERRO_FRACO = hex_to_rgba(COR_ERRO, 0.15)
RGBA_SUCESSO_FRACO = hex_to_rgba(COR_SUCESSO, 0.15)

CUSTOM_CSS = f"""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');
    html, body, [class*="css"] {{ font-family: 'Inter', sans-serif; }}
    .stApp {{ background-color: {COR_FUNDO}; color: {COR_TEXTO}; }}
    .main .block-container {{ padding-top: 1.2rem; padding-bottom: 3rem; max-width: 1440px; }}

    div[data-testid="stMetric"] {{
        background: {COR_CARD};
        border: 1px solid {COR_BORDA};
        border-radius: 12px;
        padding: 16px 18px 14px 18px;
        box-shadow: 0 1px 3px rgba(0,0,0,0.04);
        transition: box-shadow 0.15s ease, border-color 0.15s ease;
    }}
    div[data-testid="stMetric"]:hover {{ border-color: {COR_PRIMARIA}80; box-shadow: 0 4px 10px rgba(0,0,0,0.06); }}
    div[data-testid="stMetricLabel"] p {{ font-weight: 600; opacity: 0.7; font-size: 0.78rem; text-transform: uppercase; letter-spacing: 0.04em; color: {COR_TEXTO_SEC}; }}
    div[data-testid="stMetricValue"] {{ font-size: 1.55rem; font-weight: 700; color: {COR_TEXTO}; }}
    div[data-testid="stMetricDelta"] {{ font-size: 0.85rem; }}

    .stTabs [data-baseweb="tab-list"] {{ gap: 4px; border-bottom: 1px solid {COR_BORDA}; margin-bottom: 8px; }}
    .stTabs [data-baseweb="tab"] {{
        background-color: transparent; border-radius: 8px 8px 0 0;
        padding: 10px 20px; font-weight: 600; font-size: 0.92rem; color: {COR_TEXTO_SEC};
    }}
    .stTabs [aria-selected="true"] {{
        background: {COR_PRIMARIA}12 !important; color: {COR_PRIMARIA} !important;
        border-bottom: 2px solid {COR_PRIMARIA};
    }}

    h1 {{ font-weight: 800; letter-spacing: -0.02em; font-size: 1.9rem; margin-bottom: 0.2rem; color: {COR_TEXTO}; }}
    h2 {{ font-weight: 700; letter-spacing: -0.01em; font-size: 1.3rem; color: {COR_TEXTO}; }}
    h3 {{ font-weight: 700; font-size: 1.05rem; color: {COR_TEXTO}; }}
    p, .stCaption, [data-testid="stCaptionContainer"] {{ color: {COR_TEXTO_SEC} !important; }}

    .badge {{ display: inline-block; padding: 5px 14px; border-radius: 20px; font-weight: 700; font-size: 0.85rem; }}
    .badge-ok {{ background: {COR_SUCESSO}15; color: {COR_SUCESSO}; border: 1px solid {COR_SUCESSO}40; }}
    .badge-warn {{ background: {COR_ALERTA}15; color: {COR_ALERTA}; border: 1px solid {COR_ALERTA}40; }}

    .info-box {{ background: {COR_PRIMARIA}08; border-left: 3px solid {COR_PRIMARIA}; padding: 12px 16px; border-radius: 6px; font-size: 0.88rem; color: {COR_TEXTO}; }}
    .alert-box {{ background: {COR_ALERTA}0d; border-left: 3px solid {COR_ALERTA}; padding: 12px 16px; border-radius: 6px; font-size: 0.88rem; margin: 8px 0; color: {COR_TEXTO}; }}

    .score-card {{ background: {COR_CARD}; border-radius: 16px; padding: 22px; text-align: center; border: 1px solid {COR_BORDA}; box-shadow: 0 1px 3px rgba(0,0,0,0.04); }}
    .score-numero {{ font-size: 2.8rem; font-weight: 800; line-height: 1; }}
    .score-label {{ color: {COR_TEXTO_SEC}; font-size: 0.8rem; text-transform: uppercase; letter-spacing: 0.05em; margin-top: 6px; }}

    .section-header {{
        display: flex; align-items: center; gap: 10px; margin: 20px 0 10px 0;
        padding-bottom: 8px; border-bottom: 1px solid {COR_BORDA};
    }}
    .pill {{ padding: 3px 10px; border-radius: 6px; font-size: 0.75rem; font-weight: 700; text-transform: uppercase; letter-spacing: 0.03em; }}
    .pill-investidor {{ background: {COR_ROXO}15; color: {COR_ROXO}; }}
    .pill-publico {{ background: {COR_CIANO}15; color: {COR_CIANO}; }}

    hr {{ border-color: {COR_BORDA}; margin: 1.2rem 0; }}
    div[data-testid="stDataFrame"] {{ border: 1px solid {COR_BORDA}; border-radius: 8px; }}
    section[data-testid="stSidebar"] {{ background-color: {COR_CARD}; border-right: 1px solid {COR_BORDA}; }}
</style>
"""
st.markdown(CUSTOM_CSS, unsafe_allow_html=True)

LAYOUT_BASE = dict(
    template="plotly_white", plot_bgcolor=COR_CARD, paper_bgcolor=COR_CARD,
    font=dict(family="Inter, sans-serif", size=12, color=COR_TEXTO),
    margin=dict(l=10, r=10, t=35, b=10),
)


# ============================================================
# EXTRACAO DE PDF
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
    "Ponto de Equilibrio (R$)": r"Ponto de Equil[ií]brio[^\n]{0,60}?R\$\s*([\d\.,]+)",
    "Valor de Contrato (R$)": r"Valor (?:de|Estimado de) Contrato[^\n]{0,60}?R\$\s*([\d\.,]+)",
    "Custo Capital Proprio (%)": r"Custo (?:Real )?(?:de|do) Capital Pr[óo]prio[^\d%\n]{0,40}?([\d,]+)\s*%",
    "Custo Capital Terceiros (%)": r"Custo (?:Real )?(?:de|do) Capital de Terceiros[^\d%\n]{0,40}?([\d,]+)\s*%",
    "Investimento Total / CAPEX (R$)": r"(?:INVESTIMENTO TOTAL|Investimento Total|CAPEX Total)[^\n]{0,60}?R\$\s*([\d\.,]+)",
    "Capital Terceiros (%)": r"Capital de Terceiros[^\d%\n]{0,40}?([\d,]+)\s*%",
    "Capital Proprio (%)": r"Capital Pr[óo]prio[^\d%\n]{0,40}?([\d,]+)\s*%",
    "Vantajosidade VfM (%)": r"Vantajosidade\s*%[^\d\n]{0,20}?([\d,]+)\s*%",
    "VfM Cenario PPP (R$)": r"Cen[áa]rio PPP[^\n]{0,30}?R\$\s*([\d\.,]+)",
    "VfM Cenario Atual (R$)": r"Cen[áa]rio com Custo Atual[^\n]{0,30}?R\$\s*([\d\.,]+)",
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


@st.cache_data(show_spinner=False)
def analisar_pdf_cache(arquivo_bytes, nome_arquivo):
    texto_completo, n_paginas = extrair_texto_completo(io.BytesIO(arquivo_bytes))
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

    alerta_validacao = None
    if series.get("receita") and indicadores.get("Valor de Contrato (R$)"):
        soma_receita = sum(series["receita"].values())
        valor_contrato = indicadores["Valor de Contrato (R$)"]
        if valor_contrato:
            diff_pct = abs(soma_receita - valor_contrato) / valor_contrato * 100
            if diff_pct > 15:
                alerta_validacao = (f"A soma da série de receita extraída (R$ {soma_receita:,.0f}) difere "
                                     f"{diff_pct:.0f}% do Valor de Contrato reportado no PDF "
                                     f"(R$ {valor_contrato:,.0f}). A extração pode estar incompleta.")

    return indicadores, series, n_paginas, alerta_validacao


# ============================================================
# DATASET DE REFERENCIA (EVTEJA Carmo do Paranaiba)
# ============================================================

TMA_REF = 0.0807
PCT_CAPITAL_TERCEIROS_REF = 0.45
CUSTO_DIVIDA_REF = 0.0532
CAPEX_TOTAL_REF = 13_891_524.04
VFM_CENARIO_PPP_REF = 39_375_680.56
VFM_CENARIO_ATUAL_REF = 45_805_316.73

fluxo_caixa_acumulado_ref = {
    1: -7_498_677.77, 2: -6_390_709.32, 3: -5_383_645.65, 4: -4_383_042.45,
    5: -3_388_681.26, 6: -2_484_872.47, 7: -1_602_963.06, 8: -723_922.02,
    9: 152_347.63, 10: 1_025_939.63, 11: 1_835_674.54, 12: -2_186_894.69,
    13: -1_215_919.54, 14: -286_281.40, 15: 639_159.92, 16: 1_560_546.34,
    17: 2_441_432.08, 18: 3_307_807.20, 19: 4_171_720.30, 20: 4_517_401.00,
    21: 5_403_405.22, 22: 6_224_140.32, 23: 7_022_855.93, 24: 7_820_853.08,
    25: 8_606_136.05,
}
opex_ref = {1: 1_310_237.12, **{a: 1_731_355.73 for a in range(2, 13)}, **{a: 1_745_538.99 for a in range(13, 26)}}
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
    "Ponto de Equilibrio (R$)": 2_324_058.14, "Valor de Contrato (R$)": 76_499_278.83,
    "Custo Capital Proprio (%)": 10.33, "Custo Capital Terceiros (%)": 8.06,
    "Investimento Total / CAPEX (R$)": CAPEX_TOTAL_REF,
    "Capital Terceiros (%)": 45.0, "Capital Proprio (%)": 55.0,
    "Vantajosidade VfM (%)": 14.04, "VfM Cenario PPP (R$)": VFM_CENARIO_PPP_REF,
    "VfM Cenario Atual (R$)": VFM_CENARIO_ATUAL_REF,
}

MATRIZ_RISCOS_REF = [
    {"Risco": "Construção / Implantação", "Responsável": "Concessionária (privado)", "Severidade": "Média", "score": 2},
    {"Risco": "Demanda / Receita", "Responsável": "Compartilhado", "Severidade": "Baixa", "score": 1},
    {"Risco": "Operação e Manutenção", "Responsável": "Concessionária (privado)", "Severidade": "Média", "score": 2},
    {"Risco": "Político / Regulatório", "Responsável": "Poder Concedente (público)", "Severidade": "Alta", "score": 3},
    {"Risco": "Inadimplência do Poder Público", "Responsável": "Poder Concedente (público)", "Severidade": "Alta", "score": 3},
    {"Risco": "Financiamento / Taxa de Juros", "Responsável": "Concessionária (privado)", "Severidade": "Média", "score": 2},
]


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


def calcular_score_saude(vpl, tir, tma, payback_s, payback_d, horizonte):
    score = 30 if vpl >= 0 else (15 if vpl == 0 else 5)
    spread = (tir - tma) / tma if tma else 0
    score += min(30, max(0, 15 + spread * 100))
    if not np.isnan(payback_s) and payback_s <= horizonte:
        score += 20 * (1 - payback_s / horizonte)
    if not np.isnan(payback_d) and payback_d <= horizonte:
        score += 20
    return min(100, max(0, score))


def vpl_simulado(fluxos, taxa, fator_receita=1.0, fator_opex_capex=1.0):
    total = 0
    for ano, v in fluxos.items():
        ajustado = v * fator_opex_capex if v < 0 else v * fator_receita
        total += ajustado / (1 + taxa) ** ano
    return total


def payback_relativo_ao_prazo(payback_anos, horizonte):
    if payback_anos is None or np.isnan(payback_anos) or horizonte == 0:
        return None, None
    pct_consumido = payback_anos / horizonte * 100
    margem_seguranca = horizonte - payback_anos
    return pct_consumido, margem_seguranca


def calcular_fluxo_equity(fluxos_projeto, pct_capital_proprio):
    fluxos_equity = {}
    for ano, v in fluxos_projeto.items():
        fluxos_equity[ano] = v * pct_capital_proprio if v < 0 else v
    return fluxos_equity


def dscr_aproximado(fluxo_caixa_operacional_medio, capital_terceiros_total, custo_divida, prazo_amortizacao):
    if prazo_amortizacao <= 0 or custo_divida <= 0 or capital_terceiros_total <= 0:
        return None, None
    taxa = custo_divida
    parcela = capital_terceiros_total * (taxa * (1 + taxa) ** prazo_amortizacao) / ((1 + taxa) ** prazo_amortizacao - 1)
    dscr = fluxo_caixa_operacional_medio / parcela if parcela else None
    return dscr, parcela


def calcular_concentracao_receita(receita_serie):
    valores = [v for v in receita_serie.values() if v and v > 0]
    if not valores:
        return None
    cv = np.std(valores) / np.mean(valores) if np.mean(valores) else 0
    return cv


# ============================================================
# GERACAO DE RELATORIO PDF EXECUTIVO
# ============================================================

def gerar_grafico_para_pdf(df, tma_input, fluxos_dict):
    fig = go.Figure()
    cores_barras = [COR_ERRO if v < 0 else COR_SUCESSO for v in df["fluxo_caixa_acumulado"]]
    fig.add_trace(go.Bar(x=df["ano"], y=df["fluxo_caixa_acumulado"], marker_color=cores_barras))
    fig.add_hline(y=0, line_color=RGBA_LINHA_REF, line_width=1)
    fig.update_layout(
        template="plotly_white", title="Fluxo de Caixa Livre Acumulado",
        xaxis_title="Ano", yaxis_title="R$", height=380, width=760,
        font=dict(family="Inter, sans-serif", size=11),
    )
    return fig.to_image(format="png", scale=2)


def gerar_pdf_executivo(nome_fonte, score_saude, viavel, vpl_calc, tir_calc, tma_input,
                         payback_s_calc, payback_d_calc, il_calc, receita_total, opex_total,
                         lucro_total, margem_liquida_calc, tir_equity, vpl_equity,
                         capital_proprio_valor, capital_terceiros_valor, dscr_calc,
                         vantajosidade_vfm_pct, economia_vfm_valor, df, fluxos_dict):
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, topMargin=1.5*cm, bottomMargin=1.5*cm,
                             leftMargin=1.8*cm, rightMargin=1.8*cm)
    styles = getSampleStyleSheet()
    titulo_style = ParagraphStyle('Titulo', parent=styles['Title'], fontSize=18, spaceAfter=4,
                                   textColor=rl_colors.HexColor(COR_TEXTO))
    subtitulo_style = ParagraphStyle('Subtitulo', parent=styles['Normal'], fontSize=10,
                                      textColor=rl_colors.HexColor(COR_TEXTO_SEC), spaceAfter=14)
    secao_style = ParagraphStyle('Secao', parent=styles['Heading2'], fontSize=13, spaceBefore=14,
                                  spaceAfter=8, textColor=rl_colors.HexColor(COR_PRIMARIA))
    corpo_style = ParagraphStyle('Corpo', parent=styles['Normal'], fontSize=9.5, leading=14,
                                  textColor=rl_colors.HexColor(COR_TEXTO))

    elementos = []
    elementos.append(Paragraph("Relatório Executivo — Viabilidade Econômico-Financeira", titulo_style))
    elementos.append(Paragraph(f"Fonte dos dados: {nome_fonte}", subtitulo_style))

    status_txt = "PROJETO VIÁVEL" if viavel else "ATENÇÃO — REVISAR PREMISSAS"
    status_cor = rl_colors.HexColor(COR_SUCESSO) if viavel else rl_colors.HexColor(COR_ALERTA)
    elementos.append(Paragraph(f"<b><font color='{status_cor.hexval()}'>{status_txt}</font></b> · "
                                f"Score de Saúde do Projeto: <b>{score_saude:.0f}/100</b>", corpo_style))
    elementos.append(Spacer(1, 10))

    elementos.append(Paragraph("Indicadores-Chave do Projeto", secao_style))
    dados_tabela1 = [
        ["Indicador", "Valor"],
        ["VPL (à TMA de {:.2f}%)".format(tma_input*100), f"R$ {vpl_calc/1e6:,.2f} M"],
        ["TIR", f"{tir_calc*100:.2f}%"],
        ["Payback Simples", f"{payback_s_calc:.1f} anos" if not np.isnan(payback_s_calc) else "N/D"],
        ["Payback Descontado", f"{payback_d_calc:.1f} anos" if not np.isnan(payback_d_calc) else "> horizonte"],
        ["Índice de Lucratividade", f"{il_calc:.2f}" if not np.isnan(il_calc) else "N/D"],
        ["Receita Total", f"R$ {receita_total/1e6:,.2f} M"],
        ["OPEX Total", f"R$ {opex_total/1e6:,.2f} M"],
        ["Lucro Líquido Acumulado", f"R$ {lucro_total/1e6:,.2f} M"],
        ["Margem Líquida Média", f"{margem_liquida_calc:.1f}%" if not np.isnan(margem_liquida_calc) else "N/D"],
    ]
    tabela1 = Table(dados_tabela1, colWidths=[9*cm, 6*cm])
    tabela1.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), rl_colors.HexColor(COR_PRIMARIA)),
        ('TEXTCOLOR', (0, 0), (-1, 0), rl_colors.white),
        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('GRID', (0, 0), (-1, -1), 0.5, rl_colors.HexColor(COR_BORDA)),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [rl_colors.white, rl_colors.HexColor(COR_FUNDO)]),
        ('TOPPADDING', (0, 0), (-1, -1), 5), ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
    ]))
    elementos.append(tabela1)
    elementos.append(Spacer(1, 12))

    elementos.append(Paragraph("Perspectiva do Investidor (Equity)", secao_style))
    dados_tabela2 = [
        ["Indicador", "Valor"],
        ["Capital Próprio Investido", f"R$ {capital_proprio_valor/1e6:,.2f} M"],
        ["Capital de Terceiros", f"R$ {capital_terceiros_valor/1e6:,.2f} M"],
        ["TIR do Capital Próprio", f"{tir_equity*100:.2f}%" if not np.isnan(tir_equity) else "N/D"],
        ["VPL do Capital Próprio", f"R$ {vpl_equity/1e6:,.2f} M" if not np.isnan(vpl_equity) else "N/D"],
        ["DSCR (Cobertura da Dívida)", f"{dscr_calc:.2f}x" if dscr_calc else "N/D"],
    ]
    tabela2 = Table(dados_tabela2, colWidths=[9*cm, 6*cm])
    tabela2.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), rl_colors.HexColor(COR_ROXO)),
        ('TEXTCOLOR', (0, 0), (-1, 0), rl_colors.white),
        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('GRID', (0, 0), (-1, -1), 0.5, rl_colors.HexColor(COR_BORDA)),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [rl_colors.white, rl_colors.HexColor(COR_FUNDO)]),
        ('TOPPADDING', (0, 0), (-1, -1), 5), ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
    ]))
    elementos.append(tabela2)
    elementos.append(Spacer(1, 12))

    if vantajosidade_vfm_pct is not None:
        elementos.append(Paragraph("Perspectiva do Poder Público (Value for Money)", secao_style))
        elementos.append(Paragraph(
            f"A modelagem via concessão (PPP) apresenta uma vantajosidade estimada de "
            f"<b>{vantajosidade_vfm_pct:.2f}%</b> em relação ao custo atual do município, representando uma "
            f"economia em valor presente de aproximadamente <b>R$ {economia_vfm_valor/1e6:,.2f} milhões</b> "
            f"ao longo do período da concessão.", corpo_style
        ))
        elementos.append(Spacer(1, 10))

    try:
        img_bytes = gerar_grafico_para_pdf(df, tma_input, fluxos_dict)
        img_buffer = io.BytesIO(img_bytes)
        elementos.append(Paragraph("Fluxo de Caixa Livre Acumulado", secao_style))
        elementos.append(RLImage(img_buffer, width=15*cm, height=7.6*cm))
    except Exception:
        pass

    elementos.append(Spacer(1, 14))
    elementos.append(Paragraph(
        "Este relatório é gerado automaticamente a partir da série de fluxo de caixa extraída do documento "
        "original ou do dataset de referência. Os indicadores de ROE/DSCR são aproximações simplificadas. "
        "Este material serve como apoio à tomada de decisão e não substitui a análise de um profissional habilitado.",
        ParagraphStyle('Rodape', parent=styles['Normal'], fontSize=7.5, textColor=rl_colors.HexColor(COR_TEXTO_SEC))
    ))

    doc.build(elementos)
    buffer.seek(0)
    return buffer


# ============================================================
# SIDEBAR
# ============================================================

st.sidebar.markdown("## 📁 Fonte de Dados")
uploaded_file = st.sidebar.file_uploader(
    "Envie o PDF do Estudo de Viabilidade", type=["pdf"],
    help="Extração automática de indicadores e séries financeiras."
)

usar_pdf = False
indicadores_extraidos, series_extraidas = {}, {}
alerta_validacao = None
nome_fonte = "Estudo de Referência — EVTEJA Carmo do Paranaíba/MG"

if uploaded_file is not None:
    if not PDF_OK:
        st.sidebar.error("Módulo pdfplumber ausente no requirements.txt.")
    else:
        with st.spinner("Analisando PDF..."):
            try:
                file_bytes = uploaded_file.getvalue()
                indicadores_extraidos, series_extraidas, n_paginas, alerta_validacao = analisar_pdf_cache(file_bytes, uploaded_file.name)
                usar_pdf = True
                nome_fonte = f"{uploaded_file.name} · {n_paginas} páginas"
                st.sidebar.success(f"✅ {n_paginas} páginas processadas")
                if alerta_validacao:
                    st.sidebar.warning(f"⚠️ {alerta_validacao}")
            except Exception as e:
                st.sidebar.error(f"Erro: {e}")

st.sidebar.markdown("---")
st.sidebar.markdown("## ⚙️ Parâmetros")

tma_default = indicadores_extraidos.get("WACC / TMA (%)") if usar_pdf and indicadores_extraidos.get("WACC / TMA (%)") else TMA_REF * 100
tma_input = st.sidebar.slider("TMA (% a.a.)", 1.0, 25.0, float(tma_default), 0.1) / 100

pct_terceiros_default = indicadores_extraidos.get("Capital Terceiros (%)") if usar_pdf and indicadores_extraidos.get("Capital Terceiros (%)") else PCT_CAPITAL_TERCEIROS_REF * 100
pct_capital_terceiros = st.sidebar.slider("Capital de Terceiros (%)", 0.0, 100.0, float(pct_terceiros_default), 5.0) / 100
pct_capital_proprio = 1 - pct_capital_terceiros

custo_divida_default = indicadores_extraidos.get("Custo Capital Terceiros (%)") if usar_pdf and indicadores_extraidos.get("Custo Capital Terceiros (%)") else CUSTO_DIVIDA_REF * 100
custo_divida_input = st.sidebar.slider("Custo da Dívida (% a.a.)", 1.0, 20.0, float(custo_divida_default), 0.1) / 100

prazo_amortizacao = st.sidebar.slider("Prazo de Amortização da Dívida (anos)", 5, 25, 15, 1)

st.sidebar.markdown("---")
st.sidebar.caption(f"📄 **Fonte ativa**\n\n{nome_fonte}")


# ============================================================
# MONTAGEM DOS DADOS
# ============================================================

if usar_pdf and series_extraidas.get("fluxo_caixa"):
    fc_acumulado = series_extraidas["fluxo_caixa"]
else:
    fc_acumulado = fluxo_caixa_acumulado_ref

anos_disponiveis = sorted(fc_acumulado.keys())
fluxos_incrementais = fluxo_incremental_de_acumulado(fc_acumulado)
horizonte = max(anos_disponiveis)

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

capex_total = indicadores_extraidos.get("Investimento Total / CAPEX (R$)") if usar_pdf and indicadores_extraidos.get("Investimento Total / CAPEX (R$)") else CAPEX_TOTAL_REF
vfm_ppp = indicadores_extraidos.get("VfM Cenario PPP (R$)") if usar_pdf and indicadores_extraidos.get("VfM Cenario PPP (R$)") else VFM_CENARIO_PPP_REF
vfm_atual = indicadores_extraidos.get("VfM Cenario Atual (R$)") if usar_pdf and indicadores_extraidos.get("VfM Cenario Atual (R$)") else VFM_CENARIO_ATUAL_REF
matriz_riscos = MATRIZ_RISCOS_REF

vpl_calc = vpl_fluxo_anual(tma_input, fluxos_dict)
tir_calc = tir_bisseccao(fluxos_dict)
payback_s_calc = payback_simples(fluxos_dict)
payback_d_calc = payback_descontado(tma_input, fluxos_dict)
il_calc = indice_lucratividade(tma_input, fluxos_dict)
score_saude = calcular_score_saude(vpl_calc, tir_calc, tma_input, payback_s_calc, payback_d_calc, horizonte)

receita_total = df["receita"].sum()
opex_total = df["opex"].sum()
lucro_total = df["lucro_liquido"].sum()
margem_liquida_calc = (lucro_total / receita_total * 100) if receita_total else np.nan

pct_payback_consumido, margem_seguranca_anos = payback_relativo_ao_prazo(payback_s_calc, horizonte)

fluxos_equity = calcular_fluxo_equity(fluxos_dict, pct_capital_proprio)
tir_equity = tir_bisseccao(fluxos_equity)
vpl_equity = vpl_fluxo_anual(tma_input, fluxos_equity)
capital_proprio_valor = capex_total * pct_capital_proprio
capital_terceiros_valor = capex_total * pct_capital_terceiros

fc_operacional_medio = df[df["fluxo_caixa_livre"] > 0]["fluxo_caixa_livre"].mean() if (df["fluxo_caixa_livre"] > 0).any() else 0
dscr_calc, parcela_divida_calc = dscr_aproximado(fc_operacional_medio, capital_terceiros_valor, custo_divida_input, prazo_amortizacao)

vantajosidade_vfm_pct = (vfm_atual - vfm_ppp) / vfm_atual * 100 if vfm_atual else None
economia_vfm_valor = vfm_atual - vfm_ppp if vfm_atual and vfm_ppp else None

cv_receita = calcular_concentracao_receita(receita_serie)

viavel = (vpl_calc >= 0) and (tir_calc >= tma_input)

st.sidebar.markdown("---")
st.sidebar.markdown("## 📄 Exportar")
if REPORTLAB_OK:
    if st.sidebar.button("📥 Gerar Relatório PDF Executivo", use_container_width=True):
        with st.spinner("Gerando PDF..."):
            try:
                pdf_buffer = gerar_pdf_executivo(
                    nome_fonte, score_saude, viavel, vpl_calc, tir_calc, tma_input,
                    payback_s_calc, payback_d_calc, il_calc, receita_total, opex_total,
                    lucro_total, margem_liquida_calc, tir_equity, vpl_equity,
                    capital_proprio_valor, capital_terceiros_valor, dscr_calc,
                    vantajosidade_vfm_pct, economia_vfm_valor, df, fluxos_dict
                )
                st.sidebar.download_button(
                    "⬇️ Baixar PDF", pdf_buffer, "relatorio_executivo_evte.pdf",
                    "application/pdf", use_container_width=True
                )
            except Exception as e:
                st.sidebar.error(f"Erro ao gerar PDF: {e}")
else:
    st.sidebar.caption("⚠️ Adicione 'reportlab' e 'kaleido' ao requirements.txt para habilitar a exportação em PDF.")


# ============================================================
# CABECALHO
# ============================================================

col_titulo, col_score = st.columns([3, 1])
with col_titulo:
    st.title("📊 Dashboard de Viabilidade Econômico-Financeira")
    st.markdown(f"<div class='info-box'>📄 <b>Fonte:</b> {nome_fonte}</div>", unsafe_allow_html=True)

with col_score:
    cor_score = COR_SUCESSO if score_saude >= 70 else (COR_ALERTA if score_saude >= 45 else COR_ERRO)
    emoji_score = "🟢" if score_saude >= 70 else ("🟡" if score_saude >= 45 else "🔴")
    st.markdown(f"""
    <div class='score-card'>
        <div class='score-numero' style='color:{cor_score}'>{score_saude:.0f}</div>
        <div class='score-label'>{emoji_score} Score de Saúde</div>
    </div>
    """, unsafe_allow_html=True)

badge_class = "badge-ok" if viavel else "badge-warn"
badge_texto = "✅ PROJETO VIÁVEL" if viavel else "⚠️ ATENÇÃO — REVISAR PREMISSAS"
st.markdown(f"<span class='badge {badge_class}'>{badge_texto}</span>", unsafe_allow_html=True)
st.markdown("<br>", unsafe_allow_html=True)


# ============================================================
# ABAS
# ============================================================

tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
    "📈 Visão Geral", "💼 Investidor × Poder Público", "🎯 TIR & Sensibilidade",
    "💧 Composição do VPL", "⚠️ Riscos", "📋 Dados & Auditoria"
])

# --- TAB 1: VISAO GERAL ---
with tab1:
    st.markdown("<div class='section-header'><h3>Indicadores-Chave do Projeto</h3></div>", unsafe_allow_html=True)
    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("VPL", f"R$ {vpl_calc/1e6:,.2f} M")
    c2.metric("TIR", f"{tir_calc*100:.2f}%", delta=f"{(tir_calc-tma_input)*100:+.2f} p.p. vs TMA")
    c3.metric("Payback Simples", f"{payback_s_calc:.1f} anos" if not np.isnan(payback_s_calc) else "N/D")
    c4.metric("Payback Descontado", f"{payback_d_calc:.1f} anos" if not np.isnan(payback_d_calc) else "> horizonte")
    c5.metric("Índice Lucratividade", f"{il_calc:.2f}" if not np.isnan(il_calc) else "N/D")

    st.markdown("<br>", unsafe_allow_html=True)
    c6, c7, c8, c9 = st.columns(4)
    c6.metric("Receita Total", f"R$ {receita_total/1e6:,.2f} M")
    c7.metric("OPEX Total", f"R$ {opex_total/1e6:,.2f} M")
    c8.metric("Lucro Líquido Acum.", f"R$ {lucro_total/1e6:,.2f} M")
    c9.metric("Margem Líquida Média", f"{margem_liquida_calc:.1f}%" if not np.isnan(margem_liquida_calc) else "N/D")

    if pct_payback_consumido is not None:
        st.markdown(
            f"<div class='info-box'>⏱️ O payback consome <b>{pct_payback_consumido:.1f}%</b> do prazo total da "
            f"concessão ({horizonte:.0f} anos), deixando uma <b>margem de segurança de {margem_seguranca_anos:.1f} anos</b> "
            f"de geração de caixa após o retorno do investimento.</div>",
            unsafe_allow_html=True
        )

    st.markdown("<div class='section-header'><h3>💰 Fluxo de Caixa Livre Acumulado</h3></div>", unsafe_allow_html=True)
    fig1 = go.Figure()
    cores_barras = [COR_ERRO if v < 0 else COR_SUCESSO for v in df["fluxo_caixa_acumulado"]]
    fig1.add_trace(go.Bar(x=df["ano"], y=df["fluxo_caixa_acumulado"], marker_color=cores_barras, name="Fluxo acumulado"))
    fig1.add_hline(y=0, line_color=RGBA_LINHA_REF, line_width=1)
    fig1.update_layout(**LAYOUT_BASE, xaxis_title="Ano", yaxis_title="R$", height=400, hovermode="x unified")
    st.plotly_chart(fig1, use_container_width=True)

    st.markdown("<div class='section-header'><h3>📈 Receita, OPEX e Lucro Líquido por Ano</h3></div>", unsafe_allow_html=True)
    fig2 = go.Figure()
    fig2.add_trace(go.Bar(x=df["ano"], y=df["receita"], name="Receita", marker_color=COR_PRIMARIA))
    fig2.add_trace(go.Bar(x=df["ano"], y=df["opex"], name="OPEX", marker_color=COR_ALERTA))
    fig2.add_trace(go.Scatter(x=df["ano"], y=df["lucro_liquido"], name="Lucro Líquido",
                               mode="lines+markers", line=dict(color=COR_SUCESSO, width=3)))
    fig2.update_layout(**LAYOUT_BASE, barmode="group", xaxis_title="Ano", yaxis_title="R$", height=400, hovermode="x unified")
    st.plotly_chart(fig2, use_container_width=True)

# --- TAB 2: INVESTIDOR x PODER PUBLICO ---
with tab2:
    st.markdown(
        "<div class='section-header'><span class='pill pill-investidor'>Investidor</span>"
        "<h3>Retorno sobre o Capital Próprio (Equity)</h3></div>", unsafe_allow_html=True
    )
    st.caption("O VPL/TIR do projeto (unlevered) mostram o retorno do empreendimento como um todo. "
               "Para quem decide investir, o que importa é o retorno sobre o capital que de fato será desembolsado "
               "— aqui aproximado considerando a estrutura de capital definida na barra lateral.")

    col_e1, col_e2, col_e3, col_e4 = st.columns(4)
    col_e1.metric("Capital Próprio Investido", f"R$ {capital_proprio_valor/1e6:,.2f} M", f"{pct_capital_proprio*100:.0f}% do CAPEX")
    col_e2.metric("Capital de Terceiros", f"R$ {capital_terceiros_valor/1e6:,.2f} M", f"{pct_capital_terceiros*100:.0f}% do CAPEX")
    col_e3.metric("TIR do Capital Próprio", f"{tir_equity*100:.2f}%" if not np.isnan(tir_equity) else "N/D",
                  delta=f"{(tir_equity-tir_calc)*100:+.2f} p.p. vs TIR do projeto" if not np.isnan(tir_equity) else None)
    col_e4.metric("VPL do Capital Próprio", f"R$ {vpl_equity/1e6:,.2f} M" if not np.isnan(vpl_equity) else "N/D")

    st.markdown(
        "<div class='alert-box'>ℹ️ A TIR do capital próprio tende a ser <b>maior</b> que a TIR do projeto quando "
        "há alavancagem (capital de terceiros com custo menor que o retorno do projeto) — efeito conhecido como "
        "alavancagem financeira positiva.</div>", unsafe_allow_html=True
    )

    st.markdown(
        "<div class='section-header'><span class='pill pill-investidor'>Investidor</span>"
        "<h3>Cobertura do Serviço da Dívida (DSCR)</h3></div>", unsafe_allow_html=True
    )
    st.caption("Mede quantas vezes o fluxo de caixa operacional médio cobre a parcela anual da dívida "
               "(amortização + juros, aproximados pelo Sistema de Amortização Francês/Price).")

    col_d1, col_d2, col_d3 = st.columns(3)
    col_d1.metric("Fluxo de Caixa Operacional Médio", f"R$ {fc_operacional_medio/1e6:,.2f} M")
    col_d2.metric("Parcela Anual Estimada da Dívida", f"R$ {parcela_divida_calc/1e6:,.2f} M" if parcela_divida_calc else "N/D")
    if dscr_calc:
        cor_dscr = COR_SUCESSO if dscr_calc >= 1.3 else (COR_ALERTA if dscr_calc >= 1.0 else COR_ERRO)
        col_d3.markdown(f"""
        <div style='padding-top:8px;'>
            <span style='font-size:0.78rem; text-transform:uppercase; opacity:0.7; font-weight:600; color:{COR_TEXTO_SEC};'>DSCR</span><br>
            <span style='font-size:1.55rem; font-weight:700; color:{cor_dscr}'>{dscr_calc:.2f}x</span>
        </div>
        """, unsafe_allow_html=True)
    else:
        col_d3.metric("DSCR", "N/D")

    if dscr_calc:
        if dscr_calc >= 1.3:
            st.markdown("<div class='info-box'>✅ DSCR confortável — geralmente bancos exigem mínimo de 1,2x a 1,5x para aprovar financiamento.</div>", unsafe_allow_html=True)
        elif dscr_calc >= 1.0:
            st.markdown("<div class='alert-box'>⚠️ DSCR apertado — próximo do limite mínimo aceito por instituições financeiras.</div>", unsafe_allow_html=True)
        else:
            st.markdown(f"<div class='alert-box' style='border-color:{COR_ERRO}'>🔴 DSCR insuficiente — o fluxo de caixa pode não cobrir o serviço da dívida nas premissas atuais.</div>", unsafe_allow_html=True)

    st.markdown(
        "<div class='section-header'><span class='pill pill-publico'>Poder Público</span>"
        "<h3>Value for Money — Vantajosidade da Concessão</h3></div>", unsafe_allow_html=True
    )
    st.caption("Compara o custo presente do modelo de concessão (PPP) com o custo presente do cenário atual "
               "(prestação direta ou contratos fragmentados), descontados à mesma taxa.")

    col_v1, col_v2, col_v3 = st.columns(3)
    col_v1.metric("VP Cenário com PPP", f"R$ {vfm_ppp/1e6:,.2f} M" if vfm_ppp else "N/D")
    col_v2.metric("VP Cenário Atual (sem PPP)", f"R$ {vfm_atual/1e6:,.2f} M" if vfm_atual else "N/D")
    if vantajosidade_vfm_pct is not None:
        col_v3.metric("Vantajosidade para o Município", f"{vantajosidade_vfm_pct:.2f}%",
                      delta=f"R$ {economia_vfm_valor/1e6:,.2f} M de economia")
    else:
        col_v3.metric("Vantajosidade para o Município", "N/D")

    if vfm_ppp and vfm_atual:
        fig_vfm = go.Figure(go.Bar(
            x=["Cenário Atual (sem PPP)", "Cenário com PPP"],
            y=[vfm_atual, vfm_ppp],
            marker_color=[COR_ERRO, COR_SUCESSO],
            text=[f"R$ {vfm_atual/1e6:,.1f} M", f"R$ {vfm_ppp/1e6:,.1f} M"],
            textposition="outside",
        ))
        fig_vfm.update_layout(**LAYOUT_BASE, yaxis_title="Valor Presente (R$)", height=340)
        st.plotly_chart(fig_vfm, use_container_width=True)

    if cv_receita is not None:
        st.markdown(
            f"<div class='alert-box'>🎯 <b>Concentração de receita:</b> a receita projetada apresenta baixa "
            f"variabilidade entre anos (coeficiente de variação de {cv_receita*100:.1f}%), típico de contratos "
            f"com pagador único (poder concedente). Isso reduz o risco de demanda, mas concentra o risco de "
            f"crédito/inadimplência em uma única contraparte.</div>", unsafe_allow_html=True
        )

# --- TAB 3: TIR & SENSIBILIDADE ---
with tab3:
    col_gauge, col_sens = st.columns([1, 2])
    with col_gauge:
        st.markdown("<h3>🎯 TIR vs. TMA</h3>", unsafe_allow_html=True)
        limite_gauge = max(tir_calc * 100 * 1.6, tma_input * 100 * 1.6, 15)
        fig_gauge = go.Figure(go.Indicator(
            mode="gauge+number+delta",
            value=tir_calc * 100,
            number={'suffix': "%", 'font': {'size': 38}},
            delta={'reference': tma_input * 100, 'increasing': {'color': COR_SUCESSO}, 'decreasing': {'color': COR_ERRO}},
            gauge={
                'axis': {'range': [0, limite_gauge], 'tickcolor': COR_TEXTO_SEC},
                'bar': {'color': COR_PRIMARIA},
                'bgcolor': COR_CARD,
                'bordercolor': COR_BORDA,
                'steps': [
                    {'range': [0, tma_input * 100], 'color': RGBA_ERRO_FRACO},
                    {'range': [tma_input * 100, limite_gauge], 'color': RGBA_SUCESSO_FRACO},
                ],
                'threshold': {'line': {'color': COR_ALERTA, 'width': 4}, 'thickness': 0.8, 'value': tma_input * 100},
            },
        ))
        fig_gauge.update_layout(**LAYOUT_BASE, height=300)
        st.plotly_chart(fig_gauge, use_container_width=True)
        st.caption(f"Zona verde = TIR acima da TMA ({tma_input*100:.2f}%).")

    with col_sens:
        st.markdown("<h3>📉 Sensibilidade do VPL à Taxa de Desconto</h3>", unsafe_allow_html=True)
        taxas = np.arange(0.01, 0.25, 0.005)
        vpls = [vpl_fluxo_anual(t, fluxos_dict) for t in taxas]
        fig3 = go.Figure()
        fig3.add_trace(go.Scatter(x=taxas * 100, y=vpls, mode="lines", line=dict(color=COR_ROXO, width=3),
                                   fill="tozeroy", fillcolor=RGBA_ROXO_FRACO))
        fig3.add_hline(y=0, line_color=RGBA_LINHA_REF, line_width=1)
        fig3.add_vline(x=tma_input * 100, line_dash="dash", line_color=COR_ALERTA, annotation_text=f"TMA {tma_input*100:.2f}%")
        if not np.isnan(tir_calc):
            fig3.add_vline(x=tir_calc * 100, line_dash="dot", line_color=COR_SUCESSO, annotation_text=f"TIR {tir_calc*100:.2f}%")
        fig3.update_layout(**LAYOUT_BASE, xaxis_title="Taxa (%)", yaxis_title="VPL (R$)", height=300)
        st.plotly_chart(fig3, use_container_width=True)

    st.markdown("<div class='section-header'><h3>🌪️ Sensibilidade Multivariável (Tornado)</h3></div>", unsafe_allow_html=True)
    st.caption("Impacto no VPL ao variar cada premissa isoladamente em ±15% (±2 p.p. para a TMA).")

    variaveis_tornado = {
        "Receita (±15%)": ("receita", 0.15),
        "OPEX/CAPEX (±15%)": ("custo", 0.15),
        "TMA (±2 p.p.)": ("tma", 0.02),
    }
    resultados_tornado = []
    for label, (tipo, delta) in variaveis_tornado.items():
        if tipo == "receita":
            vpl_low = vpl_simulado(fluxos_dict, tma_input, fator_receita=1 - delta)
            vpl_high = vpl_simulado(fluxos_dict, tma_input, fator_receita=1 + delta)
        elif tipo == "custo":
            vpl_low = vpl_simulado(fluxos_dict, tma_input, fator_opex_capex=1 + delta)
            vpl_high = vpl_simulado(fluxos_dict, tma_input, fator_opex_capex=1 - delta)
        else:
            vpl_low = vpl_fluxo_anual(tma_input + delta, fluxos_dict)
            vpl_high = vpl_fluxo_anual(tma_input - delta, fluxos_dict)
        resultados_tornado.append((label, vpl_low - vpl_calc, vpl_high - vpl_calc))

    resultados_tornado.sort(key=lambda x: abs(x[2] - x[1]))
    labels_t = [r[0] for r in resultados_tornado]
    baixos = [r[1] for r in resultados_tornado]
    altos = [r[2] for r in resultados_tornado]

    fig_tornado = go.Figure()
    fig_tornado.add_trace(go.Bar(y=labels_t, x=baixos, orientation='h', name='Cenário desfavorável', marker_color=COR_ERRO))
    fig_tornado.add_trace(go.Bar(y=labels_t, x=altos, orientation='h', name='Cenário favorável', marker_color=COR_SUCESSO))
    fig_tornado.update_layout(**LAYOUT_BASE, barmode='overlay', xaxis_title="Variação do VPL (R$)", height=300,
                               legend=dict(orientation="h", yanchor="bottom", y=1.02))
    st.plotly_chart(fig_tornado, use_container_width=True)

# --- TAB 4: COMPOSICAO DO VPL ---
with tab4:
    st.markdown("<h3>💧 Contribuição de Cada Ano ao VPL</h3>", unsafe_allow_html=True)
    st.caption("Cada barra mostra o valor presente do fluxo de caixa daquele ano, descontado à TMA selecionada.")

    contrib_vp = {a: v / (1 + tma_input) ** a for a, v in fluxos_dict.items()}
    anos_wf = sorted(contrib_vp.keys())

    fig_wf = go.Figure(go.Waterfall(
        x=[f"Ano {a}" for a in anos_wf] + ["VPL Total"],
        y=[contrib_vp[a] for a in anos_wf] + [None],
        measure=["relative"] * len(anos_wf) + ["total"],
        increasing={"marker": {"color": COR_SUCESSO}},
        decreasing={"marker": {"color": COR_ERRO}},
        totals={"marker": {"color": COR_PRIMARIA}},
        connector={"line": {"color": RGBA_LINHA_REF}},
    ))
    fig_wf.update_layout(**LAYOUT_BASE, height=460, xaxis_title="", yaxis_title="Valor Presente (R$)")
    st.plotly_chart(fig_wf, use_container_width=True)

    col_a, col_b = st.columns(2)
    with col_a:
        st.markdown("<h3>💹 Payback Visual</h3>", unsafe_allow_html=True)
        acumulado_simples = np.cumsum(df["fluxo_caixa_livre"].fillna(0).values)
        fig4 = go.Figure()
        fig4.add_trace(go.Scatter(x=df["ano"], y=acumulado_simples, mode="lines+markers",
                                   line=dict(color=COR_ROSA, width=3), fill="tozeroy", fillcolor=RGBA_ROSA_FRACO))
        fig4.add_hline(y=0, line_color=RGBA_LINHA_REF, line_width=1)
        if not np.isnan(payback_s_calc):
            fig4.add_vline(x=payback_s_calc, line_dash="dash", line_color=COR_SUCESSO,
                           annotation_text=f"Payback: {payback_s_calc:.1f}a")
        fig4.update_layout(**LAYOUT_BASE, xaxis_title="Ano", yaxis_title="R$ acumulado", height=360)
        st.plotly_chart(fig4, use_container_width=True)

    with col_b:
        st.markdown("<h3>🥧 Entradas vs. Saídas de Caixa</h3>", unsafe_allow_html=True)
        total_positivo = sum(v for v in fluxos_dict.values() if v > 0)
        total_negativo = abs(sum(v for v in fluxos_dict.values() if v < 0))
        fig_pizza = go.Figure(data=[go.Pie(
            labels=["Entradas de caixa", "Saídas de caixa"], values=[total_positivo, total_negativo],
            hole=0.55, marker_colors=[COR_SUCESSO, COR_ERRO],
        )])
        fig_pizza.update_layout(**LAYOUT_BASE, height=360)
        st.plotly_chart(fig_pizza, use_container_width=True)

# --- TAB 5: RISCOS ---
with tab5:
    st.markdown("<h3>⚠️ Matriz de Riscos — Repartição entre as Partes</h3>", unsafe_allow_html=True)
    st.caption("Estrutura qualitativa típica de contratos de concessão/PPP: cada risco é alocado à parte mais "
               "capaz de gerenciá-lo. Um VPL positivo com riscos concentrados em severidade 'Alta' merece atenção "
               "redobrada na análise de crédito e nas garantias contratuais.")

    df_riscos = pd.DataFrame(matriz_riscos)
    cores_severidade = {1: COR_SUCESSO, 2: COR_ALERTA, 3: COR_ERRO}

    fig_riscos = go.Figure(go.Bar(
        y=df_riscos["Risco"], x=df_riscos["score"], orientation='h',
        marker_color=[cores_severidade[s] for s in df_riscos["score"]],
        text=df_riscos["Severidade"], textposition="outside",
    ))
    fig_riscos.update_layout(**LAYOUT_BASE, xaxis=dict(visible=False), height=340, xaxis_title="")
    st.plotly_chart(fig_riscos, use_container_width=True)

    st.dataframe(df_riscos[["Risco", "Responsável", "Severidade"]], use_container_width=True, height=250)

    n_riscos_publico = sum(1 for r in matriz_riscos if "público" in r["Responsável"].lower())
    n_riscos_privado = sum(1 for r in matriz_riscos if "privado" in r["Responsável"].lower())
    n_riscos_alta = sum(1 for r in matriz_riscos if r["Severidade"] == "Alta")

    col_r1, col_r2, col_r3 = st.columns(3)
    col_r1.metric("Riscos sob o Poder Público", n_riscos_publico)
    col_r2.metric("Riscos sob o Privado", n_riscos_privado)
    col_r3.metric("Riscos de Severidade Alta", n_riscos_alta)

    if n_riscos_alta > 0:
        st.markdown(
            f"<div class='alert-box'>⚠️ Há <b>{n_riscos_alta} risco(s) de severidade alta</b>, geralmente "
            f"associados à capacidade fiscal e à continuidade político-administrativa do poder concedente. "
            f"Vale avaliar garantias contratuais (ex.: vinculação de receitas como COSIP/FPM) antes de decidir.</div>",
            unsafe_allow_html=True
        )

# --- TAB 6: DADOS & AUDITORIA ---
with tab6:
    st.markdown("<h3>📑 Indicadores Extraídos vs. Recalculados</h3>", unsafe_allow_html=True)
    fonte_indicadores = indicadores_extraidos if usar_pdf else indicadores_ref
    comparacao = pd.DataFrame({
        "Indicador": [
            "VPL (R$)", "TIR (%)", "Payback (anos)", "WACC / TMA (%)", "ROIC (%)",
            "Margem Bruta (%)", "Margem EBITDA (%)", "Margem Líquida (%)",
            "Ponto de Equilíbrio (R$)", "Valor de Contrato (R$)",
            "Custo Capital Próprio (%)", "Custo Capital Terceiros (%)",
        ],
        "No PDF/Referência": [
            fonte_indicadores.get("VPL (R$)"), fonte_indicadores.get("TIR (%)"),
            fonte_indicadores.get("Payback (anos)"), fonte_indicadores.get("WACC / TMA (%)"),
            fonte_indicadores.get("ROIC (%)"), fonte_indicadores.get("Margem Bruta (%)"),
            fonte_indicadores.get("Margem EBITDA (%)"), fonte_indicadores.get("Margem Liquida (%)"),
            fonte_indicadores.get("Ponto de Equilibrio (R$)"), fonte_indicadores.get("Valor de Contrato (R$)"),
            fonte_indicadores.get("Custo Capital Proprio (%)"), fonte_indicadores.get("Custo Capital Terceiros (%)"),
        ],
        "Recalculado": [
            round(vpl_calc, 2), round(tir_calc * 100, 2),
            round(payback_s_calc, 2) if not np.isnan(payback_s_calc) else None,
            round(tma_input * 100, 2), None, None, None,
            round(margem_liquida_calc, 2) if not np.isnan(margem_liquida_calc) else None,
            None, round(receita_total, 2), None, None,
        ],
    })
    st.dataframe(comparacao, use_container_width=True, height=440)

    if usar_pdf:
        n_encontrados = sum(1 for v in indicadores_extraidos.values() if v is not None)
        st.info(f"🔎 {n_encontrados} de {len(indicadores_extraidos)} indicadores localizados automaticamente no PDF.")
        if alerta_validacao:
            st.warning(f"⚠️ {alerta_validacao}")

    st.markdown("---")
    st.markdown("<h3>📋 Tabela Detalhada do Fluxo de Caixa</h3>", unsafe_allow_html=True)
    df_show = df.copy()
    df_show.columns = ["Ano", "Fluxo Acumulado", "Fluxo Livre", "OPEX", "Receita", "Lucro Líquido"]
    st.dataframe(
        df_show.style.format({c: "R$ {:,.2f}" for c in df_show.columns if c != "Ano"}),
        use_container_width=True, height=380
    )
    csv = df_show.to_csv(index=False).encode("utf-8-sig")
    st.download_button("⬇️ Baixar dados em CSV", csv, "dados_evte.csv", "text/csv")

    if usar_pdf:
        st.markdown("---")
        st.markdown("<h3>🧾 Todos os Indicadores Extraídos do PDF</h3>", unsafe_allow_html=True)
        df_ind = pd.DataFrame(list(indicadores_extraidos.items()), columns=["Indicador", "Valor"])
        st.dataframe(df_ind, use_container_width=True, height=380)

st.markdown("---")
st.caption("Dashboard interativo de análise de viabilidade econômico-financeira. Os indicadores de VPL/TIR/Payback "
           "são recalculados a partir da série de fluxo de caixa; ROE/DSCR são aproximações simplificadas com base "
           "na estrutura de capital informada. A matriz de riscos reflete a estrutura típica de PPPs/concessões "
           "e deve ser ajustada conforme o contrato específico. Este material serve como apoio à tomada de decisão "
           "e não substitui a análise de um profissional habilitado.")
