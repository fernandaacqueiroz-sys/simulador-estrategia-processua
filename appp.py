import streamlit as st
import pandas as pd
import plotly.express as px
import requests

st.set_page_config(page_title="Simulador de Estratégia Processual", page_icon="⚖️", layout="wide")

st.title("⚖️ Simulador de Estratégia Processual")
st.write("Analise estratégias com base em dados (simulados) e visualize risco × ganho esperado.")

@st.cache_data
def carregar_dados():
    df = pd.read_csv("data/processos.csv")
    df["valor_causa"] = pd.to_numeric(df["valor_causa"], errors="coerce")
    df["tempo_medio"] = pd.to_numeric(df["tempo_medio"], errors="coerce")
    df["taxa_sucesso"] = pd.to_numeric(df["taxa_sucesso"], errors="coerce")
    return df.dropna(subset=["valor_causa", "tempo_medio", "taxa_sucesso"])

df = carregar_dados()

st.sidebar.header("Parâmetros")
classe_sel = st.sidebar.selectbox("Classe Processual", sorted(df["classe"].unique()))
instancia_sel = st.sidebar.selectbox("Instância", sorted(df["instancia"].unique()))
valor_input = st.sidebar.number_input(
    "Valor da causa (R$) — para cálculo do ganho esperado",
    min_value=1000, step=1000, value=int(df["valor_causa"].median())
)
st.sidebar.caption("Dica: o valor informado aqui é usado para estimar o ganho esperado na sua simulação.")

with st.sidebar.expander("Consulta opcional de CNPJ"):
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

filtro = df[(df["classe"] == classe_sel) & (df["instancia"] == instancia_sel)].copy()
if filtro.empty:
    st.warning("Sem dados para esse filtro (classe/instância). Ajuste os parâmetros na barra lateral.")
    st.stop()

filtro["risco"] = filtro["tempo_medio"] / (filtro["taxa_sucesso"] * 100)
filtro["ganho_esperado"] = valor_input * filtro["taxa_sucesso"]

colm1, colm2, colm3 = st.columns(3)
colm1.metric("Taxa de sucesso (média)", f"{(filtro['taxa_sucesso'].mean()*100):.1f}%")
colm2.metric("Tempo médio (dias)", f"{filtro['tempo_medio'].mean():.0f}")
colm3.metric("Ganho esperado médio (R$)", f"{filtro['ganho_esperado'].mean():,.0f}".replace(",", "."))

st.subheader(f"Resultados — {classe_sel} / {instancia_sel}")

fig1 = px.bar(
    filtro.groupby("estrategia", as_index=False)["taxa_sucesso"].mean(),
    x="estrategia", y="taxa_sucesso", color="estrategia",
    title="Taxa de sucesso por estratégia (média)",
    labels={"taxa_sucesso":"Taxa de sucesso"}
)
fig1.update_yaxes(tickformat=".0%")
st.plotly_chart(fig1, use_container_width=True)

fig2 = px.line(
    filtro.groupby("estrategia", as_index=False)["tempo_medio"].mean(),
    x="estrategia", y="tempo_medio", markers=True,
    title="Tempo médio (dias) por estratégia",
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

st.caption("Obs.: Dados simulados para prova de conceito. Substitua por datasets do DataJud/CNJ quando disponíveis.")
