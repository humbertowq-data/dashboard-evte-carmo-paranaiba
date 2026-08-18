import streamlit as st
import pandas as pd
import numpy_financial as npf
import plotly.graph_objects as go
from weasyprint import HTML

# Configuração de layout moderno e limpo
st.set_page_config(page_title="Controladoria de Projetos", layout="wide")

st.title("Analisador de Viabilidade Econômica e Financeira")
st.subheader("Painel Estratégico de Controle e Eficiência")

# Barra lateral com premissas orçamentárias
st.sidebar.header("Premissas Orçamentárias")

tma_wacc_padrao = 8.07
tma = st.sidebar.slider("Taxa Mínima de Atratividade (WACC) %", min_value=1.0, max_value=20.0, value=tma_wacc_padrao, step=0.1) / 100
variacao_capex = st.sidebar.slider("Ajuste de CAPEX Inicial (%)", min_value=-20.0, max_value=20.0, value=0.0, step=1.0) / 100
variacao_opex = st.sidebar.slider("Ajuste de Eficiência OPEX (%)", min_value=-30.0, max_value=10.0, value=0.0, step=1.0) / 100

st.sidebar.subheader("Importação de Dados")
arquivo_excel = st.sidebar.file_uploader("Carregar planilha complementar (.xlsx)", type=["xlsx"])

# Lógica de carregamento de dados
if arquivo_excel is not None:
    df_base = pd.read_excel(arquivo_excel)
else:
    anos = list(range(0, 26))
    
    # Estruturação baseada em infraestrutura urbana e reinvestimentos
    capex_base = [0] * 26
    capex_base[0] = 8269214.16
    capex_base[12] = 2500000.00
    
    opex_base = [0] + [1273765.42] * 25
    receita_base = [0] + [3093852.65] * 25
    
    df_base = pd.DataFrame({
        "Ano": anos,
        "CAPEX_Base": capex_base,
        "OPEX_Base": opex_base,
        "Receita_Base": receita_base
    })

# Criação de cenários sobre os dados base
df_simulado = df_base.copy()
df_simulado["CAPEX"] = df_simulado["CAPEX_Base"] * (1 + variacao_capex)
df_simulado["OPEX"] = df_simulado["OPEX_Base"] * (1 + variacao_opex)
df_simulado["Receita"] = df_simulado["Receita_Base"]

# Fluxo de caixa livre e listas para algoritmos financeiros
df_simulado["Fluxo_Liquido"] = df_simulado["Receita"] - df_simulado["OPEX"] - df_simulado["CAPEX"]
fluxo_caixa = df_simulado["Fluxo_Liquido"].tolist()

# Cálculos de engenharia econômica
vpl = npf.npv(tma, fluxo_caixa)
tir = npf.irr(fluxo_caixa)

capex_total_vp = df_simulado["CAPEX"].sum()
eficiencia_capital = vpl / capex_total_vp if capex_total_vp > 0 else 0
margem_seguranca = ((df_simulado["Receita"].sum() - df_simulado["OPEX"].sum()) / df_simulado["Receita"].sum()) * 100

# Exibição dos indicadores principais
c1, c2, c3, c4 = st.columns(4)
c1.metric("VPL Líquido do Projeto", f"R$ {vpl:,.2f}")
c2.metric("Taxa Interna de Retorno (TIR)", f"{tir * 100:.2f}%" if not pd.isna(tir) else "N/A")
c3.metric("Índice de Eficiência de Capital", f"{eficiencia_capital:.2f}x")
c4.metric("Margem de Segurança Operacional", f"{margem_seguranca:.1f}%")

# Construção do gráfico do fluxo de caixa
st.subheader("Análise Gráfica Estatística do Fluxo de Caixa")
fig = go.Figure()
fig.add_trace(go.Bar(x=df_simulado["Ano"], y=df_simulado["Receita"], name="Receita Projetada", marker_color="#27ae60"))
fig.add_trace(go.Bar(x=df_simulado["Ano"], y=-df_simulado["OPEX"], name="Custos Operacionais", marker_color="#e67e22"))
fig.add_trace(go.Bar(x=df_simulado["Ano"], y=-df_simulado["CAPEX"], name="Investimento (CAPEX)", marker_color="#c0392b"))
fig.add_trace(go.Scatter(x=df_simulado["Ano"], y=df_simulado["Fluxo_Liquido"], name="Fluxo Líquido", mode="lines+markers", line=dict(color="#2980b9", width=3)))

fig.update_layout(barmode="relative", plot_bgcolor="rgba(0,0,0,0)", hovermode="x unified")
st.plotly_chart(fig, use_container_width=True)

# Tabela detalhada
st.subheader("Demonstrativo Financeiro Consolidado")
st.dataframe(df_simulado.style.format("R$ {:,.2f}", subset=["CAPEX", "OPEX", "Receita", "Fluxo_Liquido"]), use_container_width=True)

# Geração e exportação do documento PDF
st.subheader("Central de Relatórios")
if st.button("Exportar Relatório Executivo Oficial"):
    html_pdf = f"""
    <html>
    <head>
        <style>
            body {{ font-family: 'Arial', sans-serif; color: #2c3e50; padding: 20px; }}
            h2 {{ border-bottom: 2px solid #2980b9; padding-bottom: 10px; }}
            .card {{ padding: 15px; background: #ecf0f1; border-radius: 5px; margin-bottom: 15px; }}
            table {{ width: 100%; border-collapse: collapse; margin-top: 20px; font-size: 14px; }}
            th, td {{ border: 1px solid #bdc3c7; padding: 8px; text-align: right; }}
            th {{ background: #34495e; color: white; text-align: center; }}
        </style>
    </head>
    <body>
        <h2>Estudo de Viabilidade e Eficiência</h2>
        <div class="card">
            <p><b>VPL do Projeto:</b> R$ {vpl:,.2f}</p>
            <p><b>Taxa Interna de Retorno (TIR):</b> {tir*100:.2f}%</p>
            <p><b>Retorno por Real Investido:</b> {eficiencia_capital:.2f}x</p>
            <p><b>Margem de Segurança:</b> {margem_seguranca:.1f}%</p>
        </div>
        <table>
            <tr><th>Ano</th><th>CAPEX</th><th>OPEX</th><th>Receita</th><th>Fluxo Líquido</th></tr>
    """
    
    for _, row in df_simulado.iterrows():
        html_pdf += f"<tr><td>{int(row['Ano'])}</td><td>{row['CAPEX']:,.2f}</td><td>{row['OPEX']:,.2f}</td><td>{row['Receita']:,.2f}</td><td>{row['Fluxo_Liquido']:,.2f}</td></tr>"
        
    html_pdf += """
        </table>
    </body>
    </html>
    """
    
    pdf_documento = HTML(string=html_pdf).write_pdf()
    st.download_button("Baixar Arquivo PDF", data=pdf_documento, file_name="Relatorio_Viabilidade_Controladoria.pdf", mime="application/pdf")
