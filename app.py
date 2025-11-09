import streamlit as st
import pandas as pd
import requests
import json
import io
import matplotlib.pyplot as plt
import numpy as np

# --- 1. Configuração da Página, URL da API CNJ/STJ e Autenticação ---
# Configurações básicas de layout
st.set_page_config(
    page_title="Simulador de Estratégia Processual (P2 Direito)",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Endpoint da API (ElasticSearch)
API_URL = "https://api-publica.datajud.cnj.jus.br/api_publica_stj/_search"
API_KEY = "cDZHYzlZa0JadVREZDJCendQbXY6SkJlTzNjLV9TRENyQk1RdnFKZGRQdw=="

HEADERS = {
    "Content-Type": "application/json",
    "Authorization": f"APIKey {API_KEY}"
}

# Payload JSON Mínimo para Busca
QUERY_JSON = {
    "size": 50,
    "query": { "match_all": {} },
    "_source": ["classeProcessual.nome", "valorDaCausa", "dataAjuizamento", "assunto", "tribunal.nome"]
}

# --- 2. Função de Busca e Processamento (API POST Request) ---
@st.cache_data(ttl=3600)
def buscar_e_processar_dados_cnj():
    """Realiza a requisição POST AUTENTICADA à API do CNJ e processa o JSON retornado."""
    st.sidebar.info("🌐 Status da Conexão: Tentando acessar API Pública do CNJ/STJ...")
    
    try:
        # Requisição POST com autenticação
        response = requests.post(API_URL, headers=HEADERS, data=json.dumps(QUERY_JSON), timeout=30)
        response.raise_for_status()
        data_json = response.json()
        
        if not 'hits' in data_json or not data_json['hits']['hits']:
            st.warning("API CNJ retornou 0 resultados (Hits).")
            return pd.DataFrame()

        lista_processos = []
        for hit in data_json['hits']['hits']:
            source = hit['_source']
            
            classe = source.get('classeProcessual', {}).get('nome', 'N/A')
            valor = source.get('valorDaCausa', 0)
            
            # --- SIMULAÇÃO DE DADOS ANALÍTICOS (CRUCIAL PARA O SIMULADOR) ---
            # As colunas 'Estrategia' e 'Resultado' são simuladas com base na Classe real
            if 'Recurso Especial' in classe or 'Agravo' in classe:
                estrategia = 'Recorrer'
                resultado = 1 if valor > 100000 and np.random.rand() < 0.4 else 0
                tempo = np.random.randint(500, 1500) 
            elif 'Embargos' in classe:
                estrategia = 'Negociar'
                resultado = 1 if np.random.rand() < 0.7 else 0
                tempo = np.random.randint(100, 400)
            else:
                estrategia = 'Desistir'
                resultado = 0
                tempo = np.random.randint(30, 150)
            
            custo_rs = np.random.uniform(500, 5000)
            
            lista_processos.append({
                'Classe_Processual': classe,
                'Estrategia_Escolhid': estrategia,
                'Resultado': resultado,
                'Tempo_dias': tempo,
                'Custo_R$': custo_rs,
                'Valor_R$': valor
            })
            
        st.sidebar.success(f"✔️ {len(lista_processos)} registros de Classe Processual carregados da API CNJ/STJ.")
        return pd.DataFrame(lista_processos)
        
    except requests.exceptions.RequestException as e:
        st.sidebar.error("❌ Falha na conexão com a API CNJ. Dados não disponíveis.")
        st.error(f"Erro ao conectar ou autenticar: {e}")
        return pd.DataFrame()
    except Exception as e:
        st.sidebar.error("❌ Erro no processamento dos dados JSON.")
        st.error(f"Erro: {e}")
        return pd.DataFrame()

df_processado = buscar_e_processar_dados_cnj()

# --- 3. Estrutura do Layout (Tabs) ---

# Título Principal e Introdução
st.markdown("<h1 style='text-align: center; color: #1E90FF;'>Simulador de Estratégia Processual 🤖</h1>", unsafe_allow_html=True)
st.markdown("<h3 style='text-align: center; color: #333;'>Análise Preditiva em Dados Jurídicos (P2 Programação)</h3>", unsafe_allow_html=True)

# Tabs para organizar o conteúdo
tab_instrucoes, tab_simulador, tab_dados_brutos = st.tabs(["💡 Introdução e Instruções", "📈 O SIMULADOR", "💾 Dados Brutos da API"])

with tab_instrucoes:
    st.header("O que é o Simulador?")
    st.markdown("""
        Este aplicativo é uma **ferramenta de apoio à decisão processual** que utiliza a análise de dados para comparar os possíveis resultados de diferentes estratégias jurídicas: **Recorrer**, **Negociar** ou **Desistir**.
        
        Com base na **Classe Processual** real extraída da API pública do STJ (DataJud), o simulador projeta a probabilidade de sucesso, o tempo de duração e o impacto financeiro esperado para cada caminho.
        """)

    st.subheader("Como Funciona?")
    st.markdown("""
        1.  **Busca de Dados (API):** O sistema se conecta em tempo real à API Pública do STJ para obter uma amostra de Classes Processuais e Valores de Causa.
        2.  **Definição do Caso (Sidebar):** Você informa os parâmetros do seu caso (Classe Processual e Valor da Causa).
        3.  **Algoritmo Estatístico:** O sistema aplica **Média Ponderada** (para Impacto Financeiro) e **Regressão Simples** (para Previsão de Tempo) em cima dos dados simulados.
        4.  **Resultado:** Os gráficos e métricas interativas mostram a estratégia com maior **Impacto Financeiro Esperado** e menor **Tempo de Duração Previsto**.
        """)

# --- 4. Sidebar e Filtros de Entrada do Usuário (dentro da Tab do Simulador) ---
with tab_simulador:
    
    # -------------------------------------------------------------
    # Estrutura em Colunas para Input e Resultados Chave
    # -------------------------------------------------------------
    
    # Verifica se há dados antes de prosseguir
    if df_processado.empty:
        st.error("Não foi possível carregar dados da API para iniciar o Simulador. Verifique a seção '💾 Dados Brutos da API' para detalhes do erro.")
        st.stop()

    st.subheader("1. Parâmetros do Seu Caso")
    
    col_input_1, col_input_2, col_input_3 = st.columns(3)

    with col_input_1:
        classes_disponiveis = df_processado['Classe_Processual'].unique()
        classe_selecionada = st.selectbox(
            "Selecione a Classe Processual:",
            classes_disponiveis,
            help="Esta lista é baseada nas Classes obtidas na amostra atual da API do STJ."
        )

    df_filtrado = df_processado[df_processado['Classe_Processual'] == classe_selecionada]

    with col_input_2:
        valor_causa = st.number_input(
            "Valor da Causa (R$):",
            min_value=1000.00,
            max_value=10000000.00,
            value=df_filtrado['Valor_R$'].mean() if not df_filtrado.empty and df_filtrado['Valor_R$'].sum() > 0 else 50000.00,
            step=1000.00,
            format="%.2f",
            help="O valor que será usado no cálculo do Impacto Financeiro Esperado."
        )

    with col_input_3:
        estrategia_desejada = st.selectbox(
            "Estratégia Foco (Para Destaque nos Gráficos):",
            df_processado['Estrategia_Escolhid'].unique(),
            help="Selecione uma estratégia para ser destacada nas comparações."
        )
    
    st.markdown("---")
    
    st.subheader(f"2. Resultados da Análise para: {classe_selecionada}")
    
    # Algoritmo de Análise Estatística Simples (Média Ponderada/Regressão)
    if df_filtrado.empty or len(df_filtrado) < 2:
        st.warning(f"Não há dados suficientes na amostra da API para a classe '{classe_selecionada}'.")
        st.stop()

    analise_estatistica = df_filtrado.groupby('Estrategia_Escolhid').agg(
        Probabilidade_Exito=('Resultado', 'mean'), 
        Tempo_Medio_dias=('Tempo_dias', 'mean'), 
        Custo_Medio=('Custo_R$', 'mean') 
    ).reset_index()

    analise_estatistica['Impacto_Esperado_R$'] = (
        valor_causa * analise_estatistica['Probabilidade_Exito']
    ) - analise_estatistica['Custo_Medio']

    def calcular_regressao_simples(df_estrat, valor_causa_input):
        if len(df_estrat) < 2: return df_estrat['Tempo_dias'].mean() if not df_estrat.empty else 0
        X = df_estrat['Valor_R$'].replace([np.inf, -np.inf], np.nan).dropna()
        Y = df_estrat.loc[X.index, 'Tempo_dias']
        if len(X) < 2: return Y.mean() if not Y.empty else 0
        A = np.vstack([X, np.ones(len(X))]).T
        try:
            m, c = np.linalg.lstsq(A, Y, rcond=None)[0]
        except np.linalg.LinAlgError:
            return Y.mean()
        tempo_previsto = m * valor_causa_input + c
        return max(1, tempo_previsto) 

    analise_estatistica['Tempo_Regressao_dias'] = analise_estatistica.apply(
        lambda row: calcular_regressao_simples(
            df_filtrado[df_filtrado['Estrategia_Escolhid'] == row['Estrategia_Escolhid']],
            valor_causa
        ), axis=1
    )
    
    # -------------------------------------------------------------
    # Exibição de Métricas (Destaque para a Estratégia Foco)
    # -------------------------------------------------------------
    st.markdown("#### 🔑 Análise Rápida da Estratégia Selecionada")
    analise_estrategia = analise_estatistica[analise_estatistica['Estrategia_Escolhid'] == estrategia_desejada].iloc[0]
    
    col_metric_1, col_metric_2, col_metric_3 = st.columns(3)
    
    with col_metric_1:
        st.metric(
            label=f"Probabilidade de Êxito ({estrategia_desejada})",
            value=f"{analise_estrategia['Probabilidade_Exito'] * 100:.1f}%",
            delta_color="normal"
        )
    with col_metric_2:
        # Encontra a estratégia com o melhor impacto para comparação
        melhor_impacto = analise_estatistica['Impacto_Esperado_R$'].max()
        delta_impacto = analise_estrategia['Impacto_Esperado_R$'] - analise_estatistica['Impacto_Esperado_R$'].mean()
        
        st.metric(
            label=f"Impacto Financeiro Esperado ({estrategia_desejada})",
            value=f"R$ {analise_estrategia['Impacto_Esperado_R$']:,.2f}",
            delta=f"Dif. Média: R$ {delta_impacto:,.2f}",
            delta_color="normal"
        )
    with col_metric_3:
        # Encontra a estratégia com o menor tempo para comparação
        melhor_tempo = analise_estatistica['Tempo_Regressao_dias'].min()
        delta_tempo = melhor_tempo - analise_estrategia['Tempo_Regressao_dias'] # Se for negativo, está mais rápido que o melhor.
        
        st.metric(
            label=f"Tempo Previsto (Regressão)",
            value=f"{analise_estrategia['Tempo_Regressao_dias']:.0f} dias",
            delta=f"Dif. Mínimo: {delta_tempo:.0f} dias",
            delta_color="inverse" if delta_tempo < 0 else "normal" # Tempo menor é melhor (inverse)
        )
        
    st.markdown("---")
    
    # -------------------------------------------------------------
    # Visualizações (Gráficos)
    # -------------------------------------------------------------
    st.subheader("3. Comparação Visual e Relatório Detalhado")
    
    col_grafico_1, col_grafico_2 = st.columns([1, 1.5]) # Colunas de tamanhos diferentes

    # Gráfico 1: Barras para Taxa de Sucesso (Comparar Estratégias)
    with col_grafico_1:
        st.markdown("#### 🏆 Taxa de Sucesso por Estratégia")
        fig1, ax1 = plt.subplots(figsize=(8, 4))
        
        prob_percent = analise_estatistica['Probabilidade_Exito'] * 100
        estrategias = analise_estatistica['Estrategia_Escolhid']
        
        cores = ['#1E90FF' if e != estrategia_desejada else '#FFA500' for e in estrategias] # Cores mais vibrantes
        
        ax1.bar(estrategias, prob_percent, color=cores)
        ax1.set_ylabel("Probabilidade de Êxito (%)")
        ax1.set_title("Comparativo de Taxa de Sucesso")
        ax1.tick_params(axis='x', rotation=0)
        st.pyplot(fig1)

    # Gráfico 2: Pizza para Impacto Esperado
    with col_grafico_2:
        st.markdown("#### 💰 Distribuição do Impacto Financeiro Esperado")
        df_vantajoso = analise_estatistica[analise_estatistica['Impacto_Esperado_R$'] > 0]

        if not df_vantajoso.empty:
            fig3, ax3 = plt.subplots(figsize=(7, 7))
            
            # Ajuste para cores mais legíveis no Streamlit
            cores_pizza = ['#20B2AA', '#87CEEB', '#FF6347'] 
            
            ax3.pie(
                df_vantajoso['Impacto_Esperado_R$'],
                labels=df_vantajoso['Estrategia_Escolhid'],
                autopct='%1.1f%%',
                startangle=90,
                wedgeprops={'edgecolor': 'white'},
                colors=cores_pizza
            )
            ax3.set_title("Estratégias Mais Vantajosas (Baseado no Impacto)")
            st.pyplot(fig3)
        else:
            st.info("Nenhuma estratégia resultou em Impacto Financeiro Esperado positivo nesta simulação.")
    
    # Relatório Detalhado
    st.markdown("#### 📋 Tabela de Comparação (Dados Brutos)")
    st.dataframe(
        analise_estatistica.rename(columns={
            'Probabilidade_Exito': 'Probabilidade de Êxito (0-1)',
            'Tempo_Medio_dias': 'Tempo Médio (Amostra)',
            'Custo_Medio': 'Custo Médio (R$)',
            'Impacto_Esperado_R$': f'Impacto Esperado (R$ {valor_causa:,.2f})',
            'Tempo_Regressao_dias': 'Tempo Previsto (Regressão)'
        }).set_index('Estrategia_Escolhid').style.format({
            'Probabilidade de Êxito (0-1)': '{:.2f}',
            'Custo Médio (R$)': 'R$ {:,.2f}',
            f'Impacto Esperado (R$ {valor_causa:,.2f})': 'R$ {:,.2f}',
            'Tempo Médio (Amostra)': '{:.0f} dias',
            'Tempo Previsto (Regressão)': '{:.0f} dias'
        })
    )


# --- 5. Dados Brutos da API (para transparência) ---
with tab_dados_brutos:
    st.header("Amostra de Dados Brutos da API CNJ/STJ")
    st.info("Esta tabela mostra os 50 processos brutos retornados pela API antes do nosso processamento e simulação estatística.")
    if not df_processado.empty:
        st.dataframe(df_processado.head(50))
    else:
        st.warning("Nenhum dado bruto foi carregado da API.")

