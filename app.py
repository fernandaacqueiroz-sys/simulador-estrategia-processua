import streamlit as st
import pandas as pd
import plotly.express as px
import requests
from fpdf import FPDF

# ===============================
# CONFIGURAÇÃO INICIAL
# ===============================
st.set_page_config(page_title="Simulador de Estratégia Processual", page_icon="⚖️", layout="wide")
st.title("⚖️ Simulador de Estratégia Processual")
st.write("Analise estratégias processuais e visualize dados reais do CNJ (DataJud API).")

# ===============================
# FUNÇÃO: BUSCA DE DADOS REAIS DO CNJ
# ===============================
@st.cache_data
def carregar_dados_cnj(tribunal="tjrj", limite=50):
    """Busca dados reais do DataJud (CNJ) para um tribunal específico."""
    url = f"https://api-publica.datajud.cnj.jus.br/api_publica_{tribunal}/_search"
    headers = {
        "Authorization": "APIKey cDZHYzlZa0JadVREZDJCendQbXY6SkJlTzNjLV9TRENyQk1RdnFKZGRQdw==",
        "Content-Type": "application/json"
    }
    payload = {"query": {"match_all": {}}, "size": int(limite)}

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
# FUNÇÃO: CARREGAR DADOS LOCAIS
# ===============================
@st.cache_data
def carregar_dados_locais():
    df = pd.read_csv("data/processos.csv")
    df["valor_causa"] = pd.to_numeric(df["valor_causa"], errors="coerce")
    df["tempo_medio"] = pd.to_numeric(df["tempo_medio"], errors="coerce")
    df["taxa_sucesso"] = pd.to_numeric(df["taxa_sucesso"], errors="coerce")
    return df.dropna(subset=["valor_causa", "tempo_medio", "taxa_sucesso"])

# ===============================
# MENU LATERAL
# ===============================
st.sidebar.header("⚙️ Parâmetros de Simulação")
fonte_dados = st.sidebar.radio("Fonte dos dados:", ["API CNJ (real)", "Base local (CSV)"], index=0)
tribunal = st.sidebar.selectbox("Tribunal (alias)", ["tjrj", "tjsp", "tjmg", "tjrs", "stj", "stf"])
limite = st.sidebar.slider("Quantidade de processos a buscar (API CNJ)", 10, 100, 50)

# ===============================
# CONSULTA DE CNPJ (opcional)
# ===============================
with st.sidebar.expander("🔎 Consulta opcional de CNPJ"):
    cnpj = st.text_input("Digite um CNPJ (apenas números)", value="")
    if st.button("Consultar CNPJ"):
        if cnpj.strip():
            try:
                url = f"https://receitaws.com.br/v1/cnpj/{cnpj.strip()}"
                r = requests.get(url, timeout=15)
                j = r.json()
                if j.get("status") == "ERROR":
                    st.warning(j.get("message", "Não encontrado / limite da API."))
                else:
                    st.success(f"{j.get('nome','(sem nome)')} — {j.get('fantasia','')}")
                    atvs = j.get("atividade_principal", [])
                    if atvs:
                        st.caption(f"Atividade principal: {atvs[0].get('text','')}")
                    st.caption(f"UF: {j.get('uf','')} | Município: {j.get('municipio','')}")
            except Exception as e:
                st.warning(f"Falha na consulta: {e}")
        else:
            st.info("Informe um CNPJ para consultar.")

# ===============================
# CARREGAMENTO DE DADOS
# ===============================
if fonte_dados == "API CNJ (real)":
    st.info("🔄 Carregando dados reais da API do CNJ...")
    df = carregar_dados_cnj(tribunal, limite)
    if df.empty:
        st.stop()
    st.success(f"✅ {len(df)} processos reais carregados do CNJ.")
else:
    df = carregar_dados_locais()
    st.warning("Usando base local (CSV). Dados simulados.")

# ===============================
# VISUALIZAÇÃO DE DADOS REAIS
# ===============================
if "classeProcessual.sigla" in df.columns:
    st.subheader("📊 Processos Reais — Dados do CNJ (DataJud API)")
    mostrar = df[["numero", "classeProcessual.sigla", "assuntoPrincipal.nome", "orgaoJulgador.nome"]].copy()
    mostrar.rename(columns={
        "numero": "Número do Processo",
        "classeProcessual.sigla": "Classe",
        "assuntoPrincipal.nome": "Assunto",
        "orgaoJulgador.nome": "Órgão Julgador"
    }, inplace=True)
    st.dataframe(mostrar.head(20))
    st.stop()

# ===============================
# SIMULAÇÃO LOCAL
# ===============================
st.markdown("---")
st.subheader("🎯 Simulação de Estratégias Processuais")
valor_causa = st.number_input("Valor estimado da causa (R$)", min_value=1000, value=50000, step=1000)

estrategias = ["Recorrer", "Negociar", "Desistir"]
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

fig1 = px.bar(df_sim, x="Estratégia", y="Taxa de Sucesso", color="Estratégia", title="Taxa de Sucesso por Estratégia")
fig2 = px.line(df_sim, x="Estratégia", y="Tempo (relativo)", markers=True, title="Tempo Relativo de Duração")
fig3 = px.scatter(df_sim, x="Risco", y="Ganho Esperado (R$)", color="Estratégia", title="Dispersão: Risco × Ganho Esperado")

st.plotly_chart(fig1, use_container_width=True)
st.plotly_chart(fig2, use_container_width=True)
st.plotly_chart(fig3, use_container_width=True)

st.caption("💡 Dados reais via API DataJud/CNJ ou base local simulada.")
