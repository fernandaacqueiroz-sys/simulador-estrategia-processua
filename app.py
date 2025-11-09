import streamlit as st
import pandas as pd
import plotly.express as px
import requests
from fpdf import FPDF

# ===============================
# CONFIGURAÇÃO GERAL
# ===============================
st.set_page_config(page_title="Simulador de Estratégia Processual", page_icon="⚖️", layout="wide")
st.title("⚖️ Simulador de Estratégia Processual")
st.write("Analise estratégias com base em dados reais do CNJ (DataJud).")

# ===============================
# FUNÇÃO: BUSCA DE DADOS REAIS DO CNJ
# ===============================
@st.cache_data
def carregar_dados_cnj(tribunal="tjrj", limite=50):
    """
    Busca dados reais do DataJud (CNJ) para um tribunal específico.
    """
    url = f"https://api-publica.datajud.cnj.jus.br/api_publica_{tribunal}/_search"
    headers = {
        "Authorization": "APIKey cDZHYzlZa0JadVREZDJCendQbXY6SkJlTzNjLV9TRENyQk1RdnFKZGRQdw==",
        "Content-Type": "application/json"
    }
    payload = {
        "query": {"match_all": {}},
        "size": int(limite)
    }

    try:
        r = requests.post(url, headers=headers, json=payload, timeout=60)
        r.raise_for_status()
        dados = r.json()
        resultados = dados.get("hits", {}).get("hits", [])
        if not resultados:
            st.warning("Nenhum processo retornado pela API.")
            return pd.DataFrame()
        return pd.json_normalize(resultados)
    except Exception as e:
        st.error(f"Erro ao acessar o CNJ: {e}")
        return pd.DataFrame()

# ===============================
# PARÂMETROS NA BARRA LATERAL
# ===============================
st.sidebar.header("⚙️ Parâmetros de Simulação")

tribunal = st.sidebar.selectbox(
    "Tribunal (alias)",
    ["tjrj", "tjsp", "tjmg", "tjrs", "stj", "stf"],
    index=0
)
limite = st.sidebar.slider("Quantidade de processos (limite)", 10, 100, 30)
estrategias = ["Recorrer", "Negociar", "Desistir"]

# ===============================
# CARREGAMENTO DOS DADOS
# ===============================
st.info("🔄 Buscando dados reais do CNJ...")
df = carregar_dados_cnj(tribunal, limite)
if df.empty:
    st.stop()
st.success(f"✅ {len(df)} processos obtidos do {tribunal.upper()}")

# ===============================
# ORGANIZAÇÃO DOS DADOS
# ===============================
colunas = [
    "numero", "classeProcessual.sigla", "assuntoPrincipal.nome",
    "orgaoJulgador.nome", "dataAjuizamento", "grau"
]
df = df[[c for c in colunas if c in df.columns]]
df.rename(columns={
    "numero": "Número do Processo",
    "classeProcessual.sigla": "Classe",
    "assuntoPrincipal.nome": "Assunto",
    "orgaoJulgador.nome": "Órgão Julgador",
    "dataAjuizamento": "Data de Ajuizamento",
    "grau": "Grau"
}, inplace=True)

st.subheader("📊 Dados Reais do CNJ")
st.dataframe(df.head(10))

# ===============================
# SIMULAÇÃO DE ESTRATÉGIAS
# ===============================
st.markdown("---")
st.subheader("🎯 Simulação de Estratégias Processuais")

valor_causa = st.number_input("Valor estimado da causa (R$)", min_value=1000, value=50000, step=1000)

# Pesos fictícios baseados em lógica realista (poderia ser calibrado com estatísticas)
parametros = {
    "Recorrer": {"taxa_sucesso": 0.65, "tempo": 1.5, "custo": 0.10},
    "Negociar": {"taxa_sucesso": 0.80, "tempo": 0.6, "custo": 0.05},
    "Desistir": {"taxa_sucesso": 0.0, "tempo": 0.1, "custo": 0.0},
}

dados_sim = []
for e in estrategias:
    sucesso = parametros[e]["taxa_sucesso"]
    tempo = parametros[e]["tempo"]
    custo = parametros[e]["custo"]
    ganho = valor_causa * sucesso * (1 - custo)
    risco = tempo / (sucesso + 0.01)
    dados_sim.append([e, sucesso, tempo, custo, ganho, risco])

df_sim = pd.DataFrame(dados_sim, columns=["Estratégia", "Taxa de Sucesso", "Tempo (relativo)", "Custo", "Ganho Esperado (R$)", "Risco"])

st.dataframe(df_sim)

# ===============================
# GRÁFICOS
# ===============================
fig1 = px.bar(df_sim, x="Estratégia", y="Taxa de Sucesso", color="Estratégia", title="Taxa de Sucesso por Estratégia")
fig2 = px.line(df_sim, x="Estratégia", y="Tempo (relativo)", markers=True, title="Tempo Relativo de Duração")
fig3 = px.scatter(df_sim, x="Risco", y="Ganho Esperado (R$)", color="Estratégia", title="Dispersão: Risco × Ganho Esperado")

st.plotly_chart(fig1, use_container_width=True)
st.plotly_chart(fig2, use_container_width=True)
st.plotly_chart(fig3, use_container_width=True)

# ===============================
# GERAR RELATÓRIO PDF
# ===============================
st.markdown("---")
st.subheader("📄 Gerar Relatório da Simulação")

if st.button("Gerar PDF"):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", "B", 16)
    pdf.cell(0, 10, "Simulador de Estratégia Processual", ln=True, align="C")
    pdf.ln(10)
    pdf.set_font("Arial", "", 12)
    pdf.cell(0, 10, f"Tribunal: {tribunal.upper()}", ln=True)
    pdf.cell(0, 10, f"Valor da causa: R$ {valor_causa:,.2f}", ln=True)
    pdf.ln(5)
    pdf.set_font("Arial", "B", 12)
    pdf.cell(0, 10, "Resultados:", ln=True)
    pdf.set_font("Arial", "", 12)
    for _, row in df_sim.iterrows():
        pdf.cell(0, 8, f"{row['Estratégia']}: sucesso {row['Taxa de Sucesso']*100:.1f}% | ganho R$ {row['Ganho Esperado (R$)']:,.2f}", ln=True)
    pdf.output("relatorio_simulador.pdf")
    with open("relatorio_simulador.pdf", "rb") as f:
        st.download_button("📥 Baixar Relatório PDF", data=f, file_name="relatorio_simulador.pdf")

st.caption("💡 Dados reais obtidos via API DataJud/CNJ e simulação estatística baseada em parâmetros hipotéticos.")
