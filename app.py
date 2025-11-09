import streamlit as st
import pandas as pd
import plotly.express as px
import requests

# ===========================
# CONFIGURAÇÃO INICIAL
# ===========================
st.set_page_config(page_title="Simulador de Estratégia Processual", page_icon="⚖️", layout="wide")

st.title("⚖️ Simulador de Estratégia Processual")
st.write("Analise estratégias processuais e visualize dados reais do CNJ (DataJud API).")

# ===========================
# FUNÇÕES AUXILIARES
# ===========================

@st.cache_data
def carregar_dados_cnj(limite=100):
    """
    Busca dados reais de processos do CNJ (DataJud API),
    autenticando com a chave pública do CNJ.
    """
    url = f"https://api-publica.datajud.cnj.jus.br/api_publica/proc/json?limit={limite}"
    headers = {
        "Authorization": "APIKey cDZHYzlZa0JadVREZDJCendQbXY6SkJlTzNjLV9TRENyQk1RdnFKZGRQdw=="
    }
    try:
        resposta = requests.get(url, headers=headers, timeout=30)
        resposta.raise_for_status()
        dados = resposta.json()
        resultados = dados.get("results", [])
        if not resultados:
            st.warning("Nenhum processo retornado pela API do CNJ.")
            return pd.DataFrame()
        df = pd.json_normalize(resultados)
        return df
    except Exception as e:
        st.error(f"Falha ao acessar a API do CNJ: {e}")
        return pd.DataFrame()

@st.cache_data
def carregar_dados():
    df = pd.read_csv("data/processos.csv")
    df["valor_causa"] = pd.to_numeric(df["valor_causa"], errors="coerce")
    df["tempo_medio"] = pd.to_numeric(df["tempo_medio"], errors="coerce")
    df["taxa_sucesso"] = pd.to_numeric(df["taxa_sucesso"], errors="coerce")
    return df.dropna(subset=["valor_causa", "tempo_medio", "taxa_sucesso"])

# ===========================
# MENU LATERAL
# ===========================
st.sidebar.header("Parâmetros")
fonte_dados = st.sidebar.radio("Escolha a fonte dos dados:", ["API CNJ (real)", "Base local (CSV)"], index=0)
limite = st.sidebar.slider("Quantidade de processos a buscar (API CNJ)", 10, 100, 50)

# ===========================
# CONSULTA DE CNPJ (opcional)
# ===========================
with st.sidebar.expander("🔎 Consulta opcional de CNPJ"):
    cnpj = st.text_input("Digite um CNPJ (apenas números)", value="")
    if st.button("Consultar CNPJ"):
        if cnpj.strip():
            try:
                url = f"https://receitaws.com.br/v1/cnpj/{cnpj.strip()}"
                r = requests.get(url, timeout=15)
                j = r.json()
                if "status" in j and j["status"] == "ERROR":
                    st.warning(j.get("message", "Não encontrado / limite da API."))
                else:
                    st.success(f"{j.get('nome','(sem nome)')} — {j.get('fantasia','')}")
                    atvs = j.get("atividade_principal", [])
                    if atvs:
                        st.caption(f"Atividade principal: {atvs[0].get('text','')}")
                    st.caption(f"UF: {j.get('uf','')}  |  Município: {j.get('municipio','')}")
            except Exception as e:
                st.warning(f"Falha na consulta: {e}")
        else:
            st.info("Informe um CNPJ para consultar.")

# ===========================
# CARREGAMENTO DOS DADOS
# ===========================
if fonte_dados == "API CNJ (real)":
    st.info("🔄 Carregando dados reais da API do CNJ...")
    df = carregar_dados_cnj(limite)
    if df.empty:
        st.stop()
    st.success(f"✅ {len(df)} processos reais carregados do CNJ.")
else:
    df = carregar_dados()
    st.warning("Usando base local (CSV). Dados simulados.")

# ===========================
# SEÇÃO: DADOS REAIS DO CNJ
# ===========================
if "classe.nome" in df.columns:
    st.subheader("📊 Processos Reais — Dados do CNJ (DataJud API)")
    
    # Seleciona colunas importantes
    mostrar = df[["numero", "orgaoJulgador.nome", "classe.nome", "assunto.nome", "grau"]].copy()
    mostrar.rename(columns={
        "numero": "Número do Processo",
        "orgaoJulgador.nome": "Órgão Julgador",
        "classe.nome": "Classe Processual",
        "assunto.nome": "Assunto Principal",
        "grau": "Grau de Jurisdição"
    }, inplace=True)

    # Mostra tabela
    st.dataframe(mostrar.head(20))

    # --- Gráfico 1: quantidade de processos por classe ---
    fig1 = px.bar(
        mostrar.groupby("Classe Processual").size().reset_index(name="Quantidade"),
        x="Classe Processual", y="Quantidade", color="Classe Processual",
        title="Quantidade de Processos por Classe Processual"
    )
    st.plotly_chart(fig1, use_container_width=True)

    # --- Gráfico 2: distribuição por grau ---
    fig2 = px.pie(
        mostrar, names="Grau de Jurisdição", title="Distribuição por Grau de Jurisdição"
    )
    st.plotly_chart(fig2, use_container_width=True)

    # --- Gráfico 3: processos por tribunal (órgão julgador) ---
    fig3 = px.bar(
        mostrar.groupby("Órgão Julgador").size().reset_index(name="Processos"),
        x="Órgão Julgador", y="Processos",
        title="Processos por Tribunal / Órgão Julgador"
    )
    st.plotly_chart(fig3, use_container_width=True)

    st.caption("💡 Dados reais consultados via API oficial do CNJ (DataJud).")
    st.stop()

# ===========================
# SEÇÃO: BASE LOCAL (CSV)
# ===========================
st.subheader("📁 Dados Locais — Base Simulada")
classe_sel = st.sidebar.selectbox("Classe Processual", sorted(df["classe"].unique()))
instancia_sel = st.sidebar.selectbox("Instância", sorted(df["instancia"].unique()))
valor_input = st.sidebar.number_input(
    "Valor da causa (R$) — para cálculo do ganho esperado",
    min_value=1000, step=1000, value=int(df["valor_causa"].median())
)
st.sidebar.caption("O valor informado é usado para estimar o ganho esperado na simulação.")

# --- Filtro ---
filtro = df[(df["classe"] == classe_sel) & (df["instancia"] == instancia_sel)].copy()
if filtro.empty:
    st.warning("Sem dados para esse filtro. Ajuste os parâmetros na barra lateral.")
    st.stop()

# --- Cálculos ---
filtro["risco"] = filtro["tempo_medio"] / (filtro["taxa_sucesso"] * 100)
filtro["ganho_esperado"] = valor_input * filtro["taxa_sucesso"]

# --- Métricas ---
colm1, colm2, colm3 = st.columns(3)
colm1.metric("Taxa de sucesso (média)", f"{(filtro['taxa_sucesso'].mean()*100):.1f}%")
colm2.metric("Tempo médio (dias)", f"{filtro['tempo_medio'].mean():.0f}")
colm3.metric("Ganho esperado médio (R$)", f"{filtro['ganho_esperado'].mean():,.0f}".replace(",", "."))

# --- Gráficos ---
st.subheader(f"Resultados — {classe_sel} / {instancia_sel}")

fig1 = px.bar(
    filtro.groupby("estrategia", as_index=False)["taxa_sucesso"].mean(),
    x="estrategia", y="taxa_sucesso", color="estrategia",
    title="Taxa de sucesso por Estratégia (média)",
    labels={"taxa_sucesso":"Taxa de sucesso"}
)
fig1.update_yaxes(tickformat=".0%")
st.plotly_chart(fig1, use_container_width=True)

fig2 = px.line(
    filtro.groupby("estrategia", as_index=False)["tempo_medio"].mean(),
    x="estrategia", y="tempo_medio", markers=True,
    title="Tempo médio (dias) por Estratégia",
    labels={"tempo_medio":"Tempo (dias)"}
)
st.plotly_chart(fig2, use_container_width=True)

fig3 = px.scatter(
    filtro, x="risco", y="ganho_esperado", color="estrategia",
    hover_data=["valor_causa", "tempo_medio", "taxa_sucesso"],
    title="Dispersão: Risco × Ganho esperado",
    labels={"risco":"Risco (tempo / taxa*100)", "ganho_esperado":"Ganho esperado (R$)"}
)
st.plotly_chart(fig3, use_container_width=True)

st.caption("📌 Dados simulados — base local. Use a API do CNJ para dados reais atualizados.")
