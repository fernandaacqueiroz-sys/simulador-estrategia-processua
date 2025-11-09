import streamlit as st
import pandas as pd
import requests
import json
import io
import matplotlib.pyplot as plt
import numpy as np

# --- 1. Configuração da Página, URL da API CNJ/STJ e Autenticação ---
st.set_page_config(
    page_title="Simulador de Estratégia Processual",
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

# Payload JSON para Busca FOCADA (NOVO: Força a API a buscar classes relevantes)
# Buscamos por classes que contenham os termos 'Recurso', 'Embargos' ou 'Agravo' 
# para garantir que teremos dados para as estratégias 'Recorrer' e 'Negociar'.
QUERY_JSON = {
    "size": 50,
    "query": {
        "query_string": {
            "query": "Recurso OR Embargos OR Agravo",
            "fields": ["classeProcessual.nome"]
        }
    },
    "_source": ["classeProcessual.nome", "valorDaCausa", "dataAjuizamento", "assunto", "tribunal.nome"]
}

# --- 2. Função de Busca e Processamento (API POST Request) ---
@st.cache_data(ttl=3600)
def buscar_e_processar_dados_cnj():
    """Realiza a requisição POST AUTENTICADA à API do CNJ e processa o JSON retornado."""
    st.sidebar.info("🌐 Status da Conexão: Acessando API Pública do CNJ/STJ...")
    
    try:
        response = requests.post(API_URL, headers=HEADERS, data=json.dumps(QUERY_JSON), timeout=30)
        response.raise_for_status()
        data_json = response.json()
        
        if not 'hits' in data_json or not data_json['hits']['hits']:
            st.warning("API CNJ retornou 0 resultados (Hits). Verifique a consulta JSON.")
            return pd.DataFrame()

        lista_processos = []
        for hit in data_json['hits']['hits']:
            source = hit['_source']
            
            # Extrai e limpa a classe. Se o nome vier None/vazio, padronizamos para 'Caso Genérico'
            classe = source.get('classeProcessual', {}).get('nome', 'Caso Genérico')
            if not classe:
                 classe = 'Caso Genérico'
            
            valor = source.get('valorDaCausa', 0)
            
            # --- SIMULAÇÃO DE DADOS ANALÍTICOS (Lógica de Simulação Aprimorada) ---
            classe_lower = classe.lower()
            
            if 'recurso especial' in classe_lower or 'agravo' in classe_lower:
                estrategia = 'Recorrer'
                # Simula um resultado mais difícil (40% sucesso) e longo
                resultado = 1 if valor > 100000 and np.random.rand() < 0.4 else 0
                tempo = np.random.randint(500, 1500) 
            elif 'embargos' in classe_lower:
                estrategia = 'Negociar'
                # Simula maior probabilidade de acordo/negociação (70% sucesso)
                resultado = 1 if np.random.rand() < 0.7 else 0
                tempo = np.random.randint(100, 400)
            else:
                # NOVO: Em casos genéricos, distribui as estratégias de forma mais realista
                default_strategies = ['Negociar', 'Desistir']
                estrategia = np.random.choice(default_strategies, p=[0.7, 0.3]) 
                resultado = 1 if 'Negociar' in estrategia and np.random.rand() < 0.6 else 0
                tempo = np.random.randint(30, 400)
            
            custo_rs = np.random.uniform(500, 5000)
            
            lista_processos.append({
                'Classe_Processual': classe,
                'Estrategia_Escolhid': estrategia,
                'Resultado': resultado, # 1=Sucesso, 0=Insucesso
                'Tempo_dias': tempo,
                'Custo_R$': custo_rs,
                'Valor_R$': valor
            })
            
        st.sidebar.success(f"✔️ {len(lista_processos)} registros processados para análise.")
        return pd.DataFrame(lista_processos)
        
    except requests.exceptions.RequestException as e:
        st.sidebar.error("❌ Falha na conexão com a API CNJ. Dados não disponíveis.")
        st.error(f"Erro ao conectar ou autenticar: {e}")
        return pd.DataFrame()
    except Exception as e:
        st.sidebar.error("❌ Erro no processamento dos dados.")
        st.error(f"Erro: {e}")
        return pd.DataFrame()

df_processado = buscar_e_processar_dados_cnj()

# --- 3. Estrutura do Layout (Remoção da Aba de Introdução e Consolidação) ---

# Título Principal e Introdução Consolidada
st.markdown("<h1 style='text-align: center; color: #1E90FF;'>Simulador de Estratégia Processual 🤖</h1>", unsafe_allow_html=True)
st.markdown("""
    <p style='text-align: center; font-size: 1.1em; margin-bottom: 20px;'>
    Utiliza dados reais (API STJ/DataJud) e análise estatística para comparar 
    Probabilidade de Êxito, Tempo e Impacto Financeiro das estratégias: <b>Recorrer</b>, 
    <b>Negociar</b> ou <b>Desistir</b>.
    </p>
    """, unsafe_allow_html=True)
st.markdown("---")

# Tabs para organizar o conteúdo
tab_simulador, tab_instrucoes, tab_dados_brutos = st.tabs(["📈 SIMULAÇÃO E RESULTADOS", "💡 SOBRE E METODOLOGIA", "💾 DADOS BRUTOS DA API"])

# --- 4. Sidebar e Filtros de Entrada do Usuário (dentro da Tab do Simulador) ---
with tab_simulador:
    
    if df_processado.empty:
        st.error("Não foi possível carregar dados da API. Por favor, tente novamente mais tarde.")
        st.stop()

    st.subheader("1. Defina os Parâmetros do Seu Caso")
    
    col_input_1, col_input_2, col_input_3 = st.columns(3)

    # Garante que as opções de classe processual sejam únicas e não vazias
    classes_disponiveis = [c for c in df_processado['Classe_Processual'].unique() if c and c != 'N/A']
    if 'Caso Genérico' not in classes_disponiveis: classes_disponiveis.append('Caso Genérico') # Adiciona fallback
    
    with col_input_1:
        classe_selecionada = st.selectbox(
            "Classe Processual (Dados da API):",
            classes_disponiveis,
            index=classes_disponiveis.index('Caso Genérico') if 'Caso Genérico' in classes_disponiveis else 0,
            help="Selecione a Classe Processual que melhor representa o seu caso. A amostra é extraída da API do STJ."
        )

    df_filtrado = df_processado[df_processado['Classe_Processual'] == classe_selecionada]

    # Garante que as opções de estratégia sejam únicas
    estrategias_disponiveis = df_processado['Estrategia_Escolhid'].unique()
    
    with col_input_2:
        valor_causa = st.number_input(
            "Valor da Causa (R$):",
            min_value=1000.00,
            max_value=10000000.00,
            value=df_filtrado['Valor_R$'].mean() if not df_filtrado.empty and df_filtrado['Valor_R$'].sum() > 0 else 50000.00,
            step=1000.00,
            format="%.2f",
            help="O valor é utilizado no cálculo do Impacto Financeiro Esperado (Média Ponderada)."
        )

    with col_input_3:
        estrategia_desejada = st.selectbox(
            "Estratégia Foco:",
            estrategias_disponiveis,
            help="Selecione uma estratégia para ser destacada nos gráficos de comparação."
        )
    
    st.markdown("---")
    
    st.subheader(f"2. Análise Preditiva para: {classe_selecionada}")
    
    # Algoritmo de Análise Estatística Simples (Média Ponderada/Regressão)
    if df_filtrado.empty or len(df_filtrado) < 2:
        st.warning(f"Não há dados suficientes na amostra da API para a classe '{classe_selecionada}'.")
        st.stop()

    analise_estatistica = df_filtrado.groupby('Estrategia_Escolhid').agg(
        Probabilidade_Exito=('Resultado', 'mean'), 
        Tempo_Medio_dias=('Tempo_dias', 'mean'), 
        Custo_Medio=('Custo_R$', 'mean') 
    ).reset_index()

    # Média Ponderada
    analise_estatistica['Impacto_Esperado_R$'] = (
        valor_causa * analise_estatistica['Probabilidade_Exito']
    ) - analise_estatistica['Custo_Medio']

    # Regressão Simples
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
    
    # Exibição de Métricas (Destaque para a Estratégia Foco)
    st.markdown("#### 🔑 Resumo da Estratégia Selecionada")
    analise_estrategia = analise_estatistica[analise_estatistica['Estrategia_Escolhid'] == estrategia_desejada].iloc[0]
    
    col_metric_1, col_metric_2, col_metric_3 = st.columns(3)
    
    with col_metric_1:
        st.metric(
            label=f"Probabilidade de Êxito ({estrategia_desejada})",
            value=f"{analise_estrategia['Probabilidade_Exito'] * 100:.1f}%",
            delta_color="normal"
        )
    with col_metric_2:
        melhor_impacto = analise_estatistica['Impacto_Esperado_R$'].max()
        delta_impacto = analise_estrategia['Impacto_Esperado_R$'] - analise_estatistica['Impacto_Esperado_R$'].mean()
        
        st.metric(
            label=f"Impacto Financeiro Esperado",
            value=f"R$ {analise_estrategia['Impacto_Esperado_R$']:,.2f}",
            delta=f"Dif. Média: R$ {delta_impacto:,.2f}",
            delta_color="normal"
        )
    with col_metric_3:
        melhor_tempo = analise_estatistica['Tempo_Regressao_dias'].min()
        delta_tempo = melhor_tempo - analise_estrategia['Tempo_Regressao_dias']
        
        st.metric(
            label=f"Tempo Previsto (Regressão)",
            value=f"{analise_estrategia['Tempo_Regressao_dias']:.0f} dias",
            delta=f"Dif. Mínimo: {delta_tempo:.0f} dias",
            delta_color="inverse" if delta_tempo < 0 else "normal"
        )
        
    st.markdown("---")
    
    # Visualizações (Gráficos)
    st.subheader("3. Comparação Visual e Relatório Detalhado")
    
    col_grafico_1, col_grafico_2 = st.columns([1, 1.5]) 

    with col_grafico_1:
        st.markdown("#### 🏆 Taxa de Sucesso por Estratégia")
        fig1, ax1 = plt.subplots(figsize=(8, 4))
        
        prob_percent = analise_estatistica['Probabilidade_Exito'] * 100
        estrategias = analise_estatistica['Estrategia_Escolhid']
        
        cores = ['#1E90FF' if e != estrategia_desejada else '#FFA500' for e in estrategias] 
        
        ax1.bar(estrategias, prob_percent, color=cores)
        ax1.set_ylabel("Probabilidade de Êxito (%)")
        ax1.set_title("Comparativo de Taxa de Sucesso")
        ax1.tick_params(axis='x', rotation=0)
        st.pyplot(fig1)

    with col_grafico_2:
        st.markdown("#### 💰 Distribuição do Impacto Financeiro Esperado")
        df_vantajoso = analise_estatistica[analise_estatistica['Impacto_Esperado_R$'] > 0]

        if not df_vantajoso.empty:
            fig3, ax3 = plt.subplots(figsize=(7, 7))
            
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
    st.markdown("#### 📋 Tabela de Comparação Completa")
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

# --- 5. Abas de Instrução e Dados Brutos ---

with tab_instrucoes:
    st.header("💡 Sobre a Metodologia")
    st.markdown("""
        Este simulador combina dados reais (Classe Processual e Valor da Causa) da API do STJ/DataJud com uma análise estatística simulada para projeção de resultados.
        
        #### Como a Simulação Funciona:
        1.  **Fonte de Dados:** A Classe Processual e o Valor da Causa são extraídos em tempo real da **API Pública do STJ**.
        2.  **Mapeamento de Estratégias:** Como a API não informa a estratégia, mapeamos classes típicas de recursos (`Recurso Especial`, `Agravo`) para a estratégia **Recorrer**, e classes de petições mais simples ou iniciais para **Negociar** ou **Desistir**.
        3.  **Média Ponderada:** O **Impacto Financeiro Esperado** é calculado pela fórmula da Média Ponderada: `(Valor da Causa × Probabilidade de Êxito) - Custo Médio`.
        4.  **Regressão:** A **Previsão de Tempo de Tramitação** é feita com um modelo de **Regressão Linear Simples** (*least squares* do NumPy) que relaciona o **Valor da Causa** com o **Tempo Médio de Dias** de cada estratégia na amostra.
        """)
    st.markdown("---")
    st.caption("Desenvolvido para a disciplina de Programação para Advogados - 2º Período.")

with tab_dados_brutos:
    st.header("💾 Amostra de Dados Brutos da API CNJ/STJ")
    st.info("Esta tabela mostra os processos brutos (limitados a 50) retornados pela API APÓS nosso filtro. Utilize-a para verificar a qualidade da amostra.")
    if not df_processado.empty:
        st.dataframe(df_processado)
    else:
        st.warning("Nenhum dado bruto foi carregado da API.")

