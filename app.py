import streamlit as st
import pandas as pd
import requests
import json
import io
import matplotlib.pyplot as plt
import numpy as np

# --- 1. Configuração da Página, URL da API CNJ/STJ e Autenticação ---
st.set_page_config(
    page_title="Simulador de Estratégia Processual (API CNJ)",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.title("⚖️ Simulador de Estratégia Processual (Dados CNJ/STJ Autenticados)")
st.markdown("Busca de dados brutos na API Pública do STJ (DataJud) e simulação de análise estatística. A chave de autenticação (API Key) está incorporada no código.")

# Endpoint da API (ElasticSearch)
API_URL = "https://api-publica.datajud.cnj.jus.br/api_publica_stj/_search"

# CHAVE PÚBLICA FORNECIDA PELO CNJ (Obrigatório para Autenticação)
# Fonte: https://api-publica.datajud.cnj.jus.br/api_publica_stj/wiki/index
API_KEY = "cDZHYzlZa0JadVREZDJCendQbXY6SkJlTzNjLV9TRENyQk1RdnFKZGRQdw=="

HEADERS = {
    "Content-Type": "application/json",
    "Authorization": f"APIKey {API_KEY}" # Autenticação com a chave pública
}

# Payload JSON Mínimo para Busca (POST Body)
# Limitamos a 50 resultados e buscamos informações relevantes
QUERY_JSON = {
    "size": 50,  # Limite de documentos retornados
    "query": {
        "match_all": {} # Busca todos os documentos
    },
    "_source": ["classeProcessual.nome", "valorDaCausa", "dataAjuizamento", "assunto", "tribunal.nome"]
}

# --- 2. Função de Busca e Processamento (API POST Request) ---
@st.cache_data(ttl=3600) # Cache por 1 hora para não sobrecarregar a API
def buscar_e_processar_dados_cnj():
    """Realiza a requisição POST AUTENTICADA à API do CNJ e processa o JSON retornado."""
    st.sidebar.info("Tentando buscar dados jurídicos via API CNJ (requests.post e API Key)...")
    
    try:
        # AQUI ESTÁ O USO DA API COM POST, JSON BODY E AUTENTICAÇÃO
        response = requests.post(API_URL, headers=HEADERS, data=json.dumps(QUERY_JSON), timeout=30)
        response.raise_for_status() # Lança erro para status ruins (4xx ou 5xx)
        
        data_json = response.json()
        
        # Verifica se há resultados
        if not 'hits' in data_json or not data_json['hits']['hits']:
            st.warning("API CNJ retornou 0 resultados (Hits). Verifique o JSON da consulta.")
            return pd.DataFrame()

        # Extração e Normalização
        lista_processos = []
        for hit in data_json['hits']['hits']:
            source = hit['_source']
            
            # Extrai campos brutos
            classe = source.get('classeProcessual', {}).get('nome', 'N/A')
            valor = source.get('valorDaCausa', 0)
            
            # --- SIMULAÇÃO DE DADOS ANALÍTICOS PARA O SIMULADOR ---
            # Simulamos 'Estratégia' e 'Resultado' com base na Classe Real da API
            if 'Recurso Especial' in classe or 'Agravo' in classe:
                estrategia = 'Recorrer'
                # Simula que recursos de classes complexas tendem a ter sucesso baixo e tempo alto
                resultado = 1 if valor > 100000 and np.random.rand() < 0.4 else 0
                tempo = np.random.randint(500, 1500) 
            elif 'Embargos' in classe:
                estrategia = 'Negociar'
                resultado = 1 if np.random.rand() < 0.7 else 0
                tempo = np.random.randint(100, 400)
            else:
                estrategia = 'Desistir'
                resultado = 0 # Assume-se que desistir é resultado 0 (perda do objeto)
                tempo = np.random.randint(30, 150)
            
            # Simulação de Custo/Ganho (Ajuste conforme sua lógica)
            custo_rs = np.random.uniform(500, 5000)
            
            lista_processos.append({
                'Classe_Processual': classe,
                'Estrategia_Escolhid': estrategia,
                'Resultado': resultado, # 1=Sucesso, 0=Insucesso
                'Tempo_dias': tempo,
                'Custo_R$': custo_rs,
                'Valor_R$': valor
            })
            
        st.sidebar.success(f"Dados brutos CNJ extraídos e {len(lista_processos)} registros simulados para análise.")
        return pd.DataFrame(lista_processos)
        
    except requests.exceptions.HTTPError as e:
        # Este é o erro mais comum (Ex: 401 Unauthorized ou 403 Forbidden)
        st.error(f"Erro HTTP ao acessar a API: {e}. **Autenticação com a API Key falhou ou o servidor rejeitou a requisição.**")
        st.error("Verifique se a chave pública fornecida ainda está ativa. A chave CNJ pode ser alterada a qualquer momento.")
        st.stop()
    except requests.exceptions.RequestException as e:
        st.error(f"Erro de conexão: {e}. Verifique sua internet ou o endpoint da API.")
        st.stop()
    except json.JSONDecodeError:
        st.error("A resposta da API não está em JSON. Problema no servidor da API.")
        st.stop()
    except Exception as e:
        st.error(f"Ocorreu um erro durante o processamento: {e}")
        st.stop()
        
    return pd.DataFrame() # Retorna vazio em caso de falha

df_processado = buscar_e_processar_dados_cnj()

# --- Verificação e Continuação da Análise ---
if df_processado.empty:
    st.warning("Não há dados para realizar a simulação. A conexão com a API CNJ/STJ falhou.")
    st.stop()

# --- 3. Sidebar e Filtros de Entrada do Usuário ---
st.sidebar.header("Parâmetros do Caso")

# Filtros baseados nas classes extraídas
classes_disponiveis = df_processado['Classe_Processual'].unique()
if 'N/A' in classes_disponiveis:
    classes_disponiveis = np.insert(classes_disponiveis[classes_disponiveis != 'N/A'], 0, 'N/A')

classe_selecionada = st.sidebar.selectbox(
    "1. Classe Processual (Amostra da API):",
    classes_disponiveis
)

# Filtra o DataFrame com base na classe
df_filtrado = df_processado[df_processado['Classe_Processual'] == classe_selecionada]

# Inputs de Valor e Estratégia Desejada
valor_causa = st.sidebar.number_input(
    "2. Valor da Causa (R$):",
    min_value=1000.00,
    max_value=10000000.00,
    value=df_filtrado['Valor_R$'].mean() if not df_filtrado.empty and df_filtrado['Valor_R$'].sum() > 0 else 50000.00,
    step=1000.00,
    format="%.2f"
)

estrategia_desejada = st.sidebar.selectbox(
    "3. Estratégia a ser Simulada:",
    df_processado['Estrategia_Escolhid'].unique()
)

# --- 4. Algoritmo de Análise Estatística Simples (Média Ponderada/Regressão) ---
st.header(f"Resultados da Análise para: {classe_selecionada}")
st.subheader("Comparação Estatística de Estratégias")

if df_filtrado.empty or len(df_filtrado) < 2:
    st.warning(f"Não há dados suficientes na amostra da API para a classe '{classe_selecionada}'. Tente selecionar outra classe ou aumentar o 'size' na query JSON.")
    st.stop()

# Agrupa os dados e calcula as métricas-chave para cada estratégia
analise_estatistica = df_filtrado.groupby('Estrategia_Escolhid').agg(
    Probabilidade_Exito=('Resultado', 'mean'), # Probabilidade de Êxito
    Tempo_Medio_dias=('Tempo_dias', 'mean'), # Tempo Médio de Duração
    Custo_Medio=('Custo_R$', 'mean') # Custo Médio
).reset_index()

# 💡 Cálculo do Impacto Financeiro Esperado (Média Ponderada Simplificada)
analise_estatistica['Impacto_Esperado_R$'] = (
    valor_causa * analise_estatistica['Probabilidade_Exito']
) - analise_estatistica['Custo_Medio']

# Regressão Simples (Simulação de cálculo preditivo - Regressão manual com numpy)
def calcular_regressao_simples(df_estrat, valor_causa_input):
    """Simula Regressão (y = a + bx) para estimar o Tempo com base no Valor da Causa."""
    if len(df_estrat) < 2:
        return df_estrat['Tempo_dias'].mean() if not df_estrat.empty else 0
    
    # Prepara variáveis, removendo NaNs e Infinitos
    X = df_estrat['Valor_R$'].replace([np.inf, -np.inf], np.nan).dropna()
    Y = df_estrat.loc[X.index, 'Tempo_dias']
    
    if len(X) < 2: return Y.mean() if not Y.empty else 0
    
    # Cálculo da Regressão (lstsq para evitar dependência externa)
    A = np.vstack([X, np.ones(len(X))]).T
    try:
        m, c = np.linalg.lstsq(A, Y, rcond=None)[0]
    except np.linalg.LinAlgError:
        return Y.mean()
    
    # Previsão: y_previsto = m * x_novo + c
    tempo_previsto = m * valor_causa_input + c
    return max(1, tempo_previsto) 

# Adiciona uma coluna de Previsão de Tempo ajustada pela Regressão
analise_estatistica['Tempo_Regressao_dias'] = analise_estatistica.apply(
    lambda row: calcular_regressao_simples(
        df_filtrado[df_filtrado['Estrategia_Escolhid'] == row['Estrategia_Escolhid']],
        valor_causa
    ), axis=1
)

# --- 5. Apresentação dos Dados e Visualizações (Dashboards Interativos) ---
col1, col2 = st.columns(2)

# Gráfico 1: Barras para Taxa de Sucesso (Comparar Estratégias)
with col1:
    st.markdown("#### Taxa de Sucesso (%)")
    fig1, ax1 = plt.subplots(figsize=(10, 5))
    
    prob_percent = analise_estatistica['Probabilidade_Exito'] * 100
    estrategias = analise_estatistica['Estrategia_Escolhid']
    
    cores = ['skyblue' if e != estrategia_desejada else 'coral' for e in estrategias]
    
    ax1.bar(estrategias, prob_percent, color=cores)
    ax1.set_ylabel("Probabilidade de Êxito (%)")
    ax1.set_title("Comparativo de Taxa de Sucesso por Estratégia")
    ax1.tick_params(axis='x', rotation=0)
    st.pyplot(fig1)

# Gráfico 2: Linha para Tempo Médio de Duração (Regressão)
with col2:
    st.markdown("#### Previsão de Tempo de Duração (Regressão)")
    fig2, ax2 = plt.subplots(figsize=(10, 5))
    
    tempo_previsto = analise_estatistica['Tempo_Regressao_dias']
    
    ax2.plot(estrategias, tempo_previsto, marker='o', linestyle='-', color='purple')
    ax2.set_ylabel("Tempo de Duração Previsto (dias)")
    ax2.set_title("Projeção de Tempo de Tramitação")
    ax2.grid(True, linestyle='--', alpha=0.6)
    st.pyplot(fig2)

# Gráfico 3: Pizza para Distribuição de Estratégias Vantajosas (Impacto Esperado)
st.markdown("#### Distribuição Percentual de Vantajosidade (Impacto Esperado)")
df_vantajoso = analise_estatistica[analise_estatistica['Impacto_Esperado_R$'] > 0]

if not df_vantajoso.empty:
    fig3, ax3 = plt.subplots(figsize=(8, 8))
    
    ax3.pie(
        df_vantajoso['Impacto_Esperado_R$'],
        labels=df_vantajoso['Estrategia_Escolhid'],
        autopct='%1.1f%%',
        startangle=90,
        wedgeprops={'edgecolor': 'black'}
    )
    ax3.set_title("Estratégias Mais Vantajosas (Baseado no Impacto Esperado)")
    st.pyplot(fig3)
else:
    st.info("Nenhuma estratégia resultou em Impacto Financeiro Esperado positivo nesta simulação.")


# --- 6. Relatório Resumido (Simulação de PDF) ---
st.subheader("Relatório e Estatísticas Detalhadas")
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

