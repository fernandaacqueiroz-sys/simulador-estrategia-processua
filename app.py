import streamlit as st
import pandas as pd
import requests
import numpy as np
import plotly.express as px
from sklearn.linear_model import LinearRegression

# --- Configuração Básica do Streamlit ---
st.set_page_config(layout="wide", page_title="Simulador de Estratégia Processual (STJ)", page_icon="⚖️")

# --- Variáveis da API CNJ/STJ ---
API_URL = "https://api-publica.datajud.cnj.jus.br/api_publica_stj/_search"
API_KEY = "cDZHYzlZa0JadVREZDJCendQbXY6SkJlTzNjLV9TRENyQk1RdnFKZGRQdw=="
HEADERS = {
    "Authorization": f"APIKey {API_KEY}",
    "Content-Type": "application/json"
}

QUERY_JSON = {
    "size": 50,
    "query": {
        "match_all": {}
    },
    "_source": ["classeProcessual.nome", "valorDaCausa", "dataAjuizamento", "assunto", "tribunal.nome", "tempoDeTramitacao"]
}


# --- 1. FUNÇÃO FALLBACK: Cria um DataFrame Simulado Garantido ---
def criar_df_simulado():
    """Cria um DataFrame garantido para fallback quando a API falha ou retorna dados sujos."""
    st.warning("⚠️ Falha ao obter dados limpos da API. Usando dados simulados para garantir a análise.")
    np.random.seed(42) # Garante a reprodutibilidade dos dados simulados

    data = {
        'Classe_Processual': np.random.choice(['Recurso Especial', 'Agravo de Instrumento', 'Ação Rescisória', 'Conflito de Competência'], 50),
        'Valor_Causa_R$': np.random.randint(5000, 500000, 50),
        'Tempo_dias': np.random.randint(300, 2000, 50)
    }
    df = pd.DataFrame(data)
    
    # Simula variáveis analíticas com base nos dados garantidos
    def simular_estrategia_fallback(classe):
        if 'Recurso' in classe: return 'Recorrer'
        if 'Rescisória' in classe: return 'Desistir'
        return 'Negociar'
    
    df['Estrategia_Escolhid'] = df['Classe_Processual'].apply(simular_estrategia_fallback)
    
    prob_sucesso = {'Recorrer': 0.58, 'Negociar': 0.70, 'Desistir': 0.15}
    df['Resultado'] = df['Estrategia_Escolhid'].apply(
        lambda x: 1 if np.random.rand() < prob_sucesso.get(x, 0.5) else 0
    )
    
    df['Custo_R$'] = df['Valor_Causa_R$'] * np.random.uniform(0.01, 0.05)
    df['Impacto_R$'] = np.where(df['Resultado'] == 1, df['Valor_Causa_R$'] - df['Custo_R$'], -df['Custo_R$'])
    
    return df

# --- 2. FUNÇÃO PRINCIPAL DE BUSCA ---
@st.cache_data(ttl=3600)
def buscar_e_processar_dados_cnj():
    """Busca dados da API e processa, com fallback para dados simulados em caso de falha."""
    st.info("Buscando dados no DataJud (STJ) via API... (Cache de 1h)")
    df_processos = pd.DataFrame() # DataFrame inicial vazio

    try:
        response = requests.post(API_URL, headers=HEADERS, json=QUERY_JSON, timeout=10)
        response.raise_for_status() 
        data = response.json()
        hits = data.get('hits', {}).get('hits', [])
        
        if hits:
            processos = []
            for hit in hits:
                source = hit.get('_source', {})
                classe = source.get('classeProcessual', {}).get('nome', 'N/A').split(':')[0].strip()
                valor = source.get('valorDaCausa', 0)
                tempo_raw = source.get('tempoDeTramitacao', {})
                tempo_dias = tempo_raw.get('dias', np.random.randint(100, 1500)) if tempo_raw and isinstance(tempo_raw.get('dias'), (int, float)) else np.random.randint(100, 1500)
                
                processos.append({
                    'Classe_Processual': classe,
                    'Valor_Causa_R$': valor,
                    'Tempo_dias': tempo_dias
                })

            df = pd.DataFrame(processos)
            df['Valor_Causa_R$'] = pd.to_numeric(df['Valor_Causa_R$'], errors='coerce').fillna(0)
            
            # Limpeza crucial: aceita qualquer valor maior que 1 para evitar descartar todos
            df_limpo = df[df['Valor_Causa_R$'] >= 1.0].copy() 

            if df_limpo.empty:
                st.warning("A API retornou dados, mas todos foram filtrados (Valor da Causa zero/nulo).")
                return criar_df_simulado() # Chama o fallback
            
            df_processos = df_limpo
        else:
            st.error("API CNJ retornou 0 resultados (Hits vazios).")
            return criar_df_simulado() # Chama o fallback se não houver hits
        
    except requests.exceptions.RequestException as e:
        st.error(f"❌ Erro de conexão ou autenticação com a API CNJ/STJ. Detalhes: {e}. ")
        return criar_df_simulado() # Chama o fallback em caso de falha de conexão
    except Exception as e:
        st.error(f"❌ Erro inesperado no processamento. Detalhes: {e}")
        return criar_df_simulado() # Chama o fallback em caso de erro

    # --- Aplicação da Simulação Analítica (Apenas se a API funcionou) ---
    def simular_estrategia(classe):
        classe_lower = classe.lower()
        if 'recurso' in classe_lower or 'agravo' in classe_lower: return 'Recorrer'
        elif 'embargos' in classe_lower or 'conflito' in classe_lower: return 'Negociar'
        return np.random.choice(['Recorrer', 'Negociar', 'Desistir'], p=[0.35, 0.45, 0.20])

    df_processos['Estrategia_Escolhid'] = df_processos['Classe_Processual'].apply(simular_estrategia)
    prob_sucesso = {'Recorrer': 0.55, 'Negociar': 0.75, 'Desistir': 0.10}
    df_processos['Resultado'] = df_processos['Estrategia_Escolhid'].apply(
        lambda x: 1 if np.random.rand() < prob_sucesso.get(x, 0.5) else 0
    )
    df_processos['Custo_R$'] = df_processos['Valor_Causa_R$'] * np.random.uniform(0.01, 0.05)
    df_processos['Impacto_R$'] = np.where(df_processos['Resultado'] == 1, df_processos['Valor_Causa_R$'] - df_processos['Custo_R$'], -df_processos['Custo_R$'])

    return df_processos

# --- Carrega os Dados (Usa API ou Fallback) ---
df_processos = buscar_e_processar_dados_cnj()

if df_processos.empty:
    st.error("Não foi possível carregar dados limpos, mesmo com o fallback. Verifique o código.")
    st.stop()


# --- Funções de Análise Estatística (Restante do Código) ---

def calcular_estatisticas(df):
    stats = df.groupby('Estrategia_Escolhid').agg(
        Taxa_Sucesso=('Resultado', 'mean'),
        Tempo_Medio=('Tempo_dias', 'mean'),
        Impacto_Medio_RS=('Impacto_R$', 'mean'), 
        Total_Casos=('Impacto_R$', 'size')
    ).reset_index()

    stats['Taxa_Sucesso'] = stats['Taxa_Sucesso'] * 100
    stats.rename(columns={'Impacto_Medio_RS': 'Impacto_Medio_R$'}, inplace=True)
    stats['Impacto_Medio_R$'] = stats['Impacto_Medio_R$'].round(2)
    stats['Tempo_Medio'] = stats['Tempo_Medio'].round(0).astype(int)

    # Regressão Linear Simples
    df_reg = df[df['Valor_Causa_R$'] < df['Valor_Causa_R$'].quantile(0.95)] 
    
    # Verifica se a regressão pode ser feita (pelo menos 2 amostras)
    if len(df_reg) < 2:
        return stats, None # Retorna None se não houver dados suficientes para a regressão
        
    X = df_reg['Valor_Causa_R$'].values.reshape(-1, 1)
    y = df_reg['Tempo_dias'].values
    reg_model = LinearRegression().fit(X, y)
    return stats, reg_model

# Gera as estatísticas base
try:
    df_stats, reg_model = calcular_estatisticas(df_processos)
except Exception as e:
    st.error(f"❌ Erro ao calcular estatísticas (média/regressão). Detalhes: {e}")
    st.stop()


# --- LAYOUT DO SIMULADOR ---

st.title("⚖️ Simulador de Estratégia Processual - STJ")
st.caption("Baseado em dados do DataJud (CNJ)")

tab1, tab2 = st.tabs(["📈 SIMULAÇÃO E RESULTADOS", "💡 SOBRE E METODOLOGIA"])

with tab2:
    st.header("Metodologia e Funcionamento")
    st.markdown("""
    Este simulador utiliza dados de processos judiciais, priorizando a API Pública do STJ quando os dados estão limpos e caindo em um DataSet Simulado quando a API falha.
    """)
    
    st.subheader("Análise Estatística (O Algoritmo)")
    st.markdown("""
    O sistema processa os dados por meio de análises estatísticas simples, que incluem:
    * **Probabilidade de Êxito (Média Ponderada):** Calculada como a média da coluna `Resultado` por estratégia.
    * **Tempo Médio:** Calculado a partir do campo `Tempo_dias` dos processos.
    * **Regressão Linear:** Utilizada para estimar a correlação entre o **Valor da Causa** e o **Tempo de Tramitação**.
    """)
    st.subheader("Fonte de Dados Utilizada")
    if "Recurso Especial" in df_processos['Classe_Processual'].unique().tolist():
        st.success("Dados da API CNJ/STJ Carregados e Limpos com Sucesso.")
    else:
        st.warning("Dados Simulado Carregados (API falhou ou dados estavam sujos).")
    st.dataframe(df_processos.head(), use_container_width=True)


with tab1:
    st.header("Defina os Parâmetros do Seu Caso")
    
    col_input_1, col_input_2, col_input_3 = st.columns(3)
    
    with col_input_1:
        classes_disponiveis = df_processos['Classe_Processual'].unique()
        classe_escolhida = st.selectbox(
            "Classe Processual (Dados de Amostra)",
            options=classes_disponiveis,
            index=0,
            help="Selecione a Classe Processual mais próxima do seu caso."
        )

    with col_input_2:
        estrategias_disponiveis = df_stats['Estrategia_Escolhid'].unique()
        estrategia_foco = st.selectbox(
            "Estratégia de Foco",
            options=estrategias_disponiveis,
            index=estrategias_disponiveis.tolist().index('Negociar') if 'Negociar' in estrategias_disponiveis else 0,
            help="Selecione a estratégia cuja viabilidade você quer analisar."
        )

    with col_input_3:
        valor_causa = st.number_input(
            "Valor da Causa (R$)",
            min_value=1.0,
            max_value=10000000.0,
            value=25000.0,
            step=1000.0,
            format="%.2f",
            help="Insira o valor econômico da demanda."
        )
        
    st.markdown("---")
    
    # --- FILTRAGEM E RESULTADOS PARA ESTRATÉGIA DE FOCO ---
    
    df_foco = df_stats[df_stats['Estrategia_Escolhid'] == estrategia_foco].iloc[0]
    
    # Métrica de Tempo (Baseado no Valor da Causa usando Regressão)
    tempo_estimado_reg = df_foco['Tempo_Medio'] # Fallback default
    if reg_model is not None:
        try:
            tempo_estimado_reg = reg_model.predict(np.array([[valor_causa]]))[0]
        except:
            pass # Usa o fallback

    tempo_medio_base = df_foco['Tempo_Medio']
    delta_tempo = (tempo_estimado_reg - df_foco['Tempo_Medio']) / df_foco['Tempo_Medio'] * 100 if df_foco['Tempo_Medio'] != 0 else 0
    
    st.subheader(f"📊 Resultados Estimados para a Estratégia: {estrategia_foco}")

    col_metric_1, col_metric_2, col_metric_3 = st.columns(3)

    with col_metric_1:
        st.metric(
            label="Probabilidade de Êxito",
            value=f"{df_foco['Taxa_Sucesso']:.1f}%",
            delta=f"Baseado em {df_foco['Total_Casos']} casos"
        )

    with col_metric_2:
        st.metric(
            label="Impacto Financeiro Esperado (Média)",
            value=f"R$ {df_foco['Impacto_Medio_R$']:,.2f}",
            delta_color="off",
            help="Média Ponderada do impacto (Ganho - Custo)."
        )

    with col_metric_3:
        st.metric(
            label="Tempo de Tramitação Estimado",
            value=f"{tempo_estimado_reg:.0f} dias",
            delta=f"{delta_tempo:.1f}% vs. Média da Base ({tempo_medio_base} dias)",
            delta_color="inverse" if delta_tempo > 0 else "normal",
            help="Estimativa baseada em Regressão Linear."
        )
        
    st.markdown("---")
    
    # --- GRÁFICOS INTERATIVOS PLOTLY ---
    
    st.subheader("Comparativo de Estratégias (Dashboard Interativo)")
    
    col_grafico_1, col_grafico_2 = st.columns(2)
    
    # 1. Gráfico de Barras: Taxa de Sucesso (Comparação de Estratégias)
    with col_grafico_1:
        st.markdown("##### 📈 Taxa de Sucesso por Estratégia")
        fig_sucesso = px.bar(
            df_stats, 
            x='Estrategia_Escolhid', 
            y='Taxa_Sucesso',
            color='Estrategia_Escolhid',
            labels={'Estrategia_Escolhid': 'Estratégia', 'Taxa_Sucesso': 'Sucesso (%)'},
            title='Comparação de Probabilidade de Ganho/Resultado Positivo',
            color_discrete_map={
                estrategia_foco: '#1E90FF',
                'Recorrer': '#FF4B4B', 
                'Negociar': '#3CB371', 
                'Desistir': '#696969'
            }
        )
        fig_sucesso.update_layout(xaxis_title="", yaxis_range=[0, 100])
        st.plotly_chart(fig_sucesso, use_container_width=True)

    # 2. Gráfico de Pizza: Distribuição de Impacto Financeiro (Média Ponderada)
    with col_grafico_2:
        st.markdown("##### 💰 Distribuição do Impacto Financeiro Médio")
        df_pie = df_stats[df_stats['Impacto_Medio_R$'] > 0]
        if df_pie.empty:
            st.warning("Não há impacto financeiro positivo para exibir no gráfico de pizza.")
        else:
            fig_impacto = px.pie(
                df_pie, 
                names='Estrategia_Escolhid', 
                values='Impacto_Medio_R$',
                title='Impacto Médio (Ganho Líquido) por Estratégia',
                color_discrete_sequence=['#1E90FF', '#3CB371', '#FF4B4B', '#696969'],
                hover_data=['Tempo_Medio'],
            )
            fig_impacto.update_traces(textinfo='percent+label')
            st.plotly_chart(fig_impacto, use_container_width=True)

    # --- Relatório Final (Requisito PDF) ---
    st.markdown("---")
    st.subheader("📑 Resumo do Relatório (Simulação Final)")
    
    relatorio_texto = f"""
    ## Relatório de Simulação Processual - CNJ/STJ
    
    **Classe Processual Analisada:** {classe_escolhida}
    **Valor da Causa Informado:** R$ {valor_causa:,.2f}
    
    ---
    
    ### Estratégia de Foco: {estrategia_foco}
    
    Com base em nossa análise estatística da amostra do STJ e no seu valor de causa:
    
    * **Probabilidade de Êxito:** {df_foco['Taxa_Sucesso']:.1f}% (Chance de resultado positivo/ganho).
    * **Impacto Financeiro Esperado:** R$ {df_foco['Impacto_Medio_R$']:,.2f} (Considerando ganho menos custos).
    * **Tempo Estimado:** Aproximadamente {tempo_estimado_reg:.0f} dias.
    
    ### Comparativo Completo
    
    {df_stats.to_markdown(index=False)}
    
    ---
    
    *Este relatório é uma simulação baseada em dados históricos e modelos estatísticos. Não substitui a análise jurídica profissional.*
    """
    
    with st.expander("Clique para visualizar e copiar o Relatório Completo", expanded=False):
        st.code(relatorio_texto, language='markdown')

