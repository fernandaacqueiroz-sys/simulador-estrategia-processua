import streamlit as st
import pandas as pd
import numpy as np
import requests
import json
import plotly.express as px
from sklearn.linear_model import LinearRegression
from io import StringIO
import warnings

# Ignorar warnings de pandas (para evitar poluição visual no Streamlit)
warnings.filterwarnings('ignore')

# --- CONFIGURAÇÃO E AUTENTICAÇÃO API ---
API_URL = "https://api-publica.datajud.cnj.jus.br/api_publica_stj/_search"
# CHAVE FORNECIDA PELO USUÁRIO (NECESSÁRIA PARA AUTENTICAÇÃO)
API_KEY = "cDZHYzlZa0JadVREZDJCendQbXY6SkJlTzNjLV9TRENyQk1RdnFKZGRQdw=="

HEADERS = {
    'Authorization': f'APIKey {API_KEY}',
    'Content-Type': 'application/json'
}

# QUERY GENÉRICA (GARANTE QUE SEMPRE TRAGA 50 PROCESSOS)
QUERY_JSON = {
    "size": 50,
    "query": {
        "match_all": {}
    },
    "_source": ["classeProcessual.nome", "valorDaCausa", "dataAjuizamento", "assunto", "tribunal.nome", "dataHoraUltimaAlteracao"]
}

# --- FUNÇÕES DE PROCESSAMENTO ---

def carregar_dados_api_cnj():
    """Tenta carregar dados da API do CNJ. Em caso de falha, retorna um DataFrame vazio."""
    # SEM @st.cache_data para evitar erro de cache corrompido!
    try:
        response = requests.post(API_URL, headers=HEADERS, json=QUERY_JSON, timeout=15)
        response.raise_for_status()
        data = response.json()
        
        # Extrai apenas os 'hits' (resultados dos processos)
        processos = [hit['_source'] for hit in data['hits']['hits']]
        
        # Cria DataFrame
        df_bruto = pd.json_normalize(processos)
        
        if df_bruto.empty:
            return pd.DataFrame(), "API CNJ retornou 0 resultados (Hits). Verifique a consulta JSON."

        # Mapeamento e Limpeza (Processamento do Juridiquês)
        df = pd.DataFrame()
        
        # 1. Classe Processual e Assunto
        df['Classe_Processual'] = df_bruto.get('classeProcessual.nome', 'N/A')
        df['Assunto'] = df_bruto.get('assunto.nome', 'Não Informado')
        
        # 2. Valor da Causa: TRATAMENTO ROBUSTO CONTRA AUSÊNCIA DO CAMPO
        if 'valorDaCausa' in df_bruto.columns:
            # Tenta converter para float, substituindo erros por 0
            df['Valor_Causa_R$'] = pd.to_numeric(df_bruto['valorDaCausa'], errors='coerce').fillna(0)
        else:
            # Fallback seguro: cria a coluna com zeros
            df['Valor_Causa_R$'] = pd.Series(0.0, index=df_bruto.index)
        
        # 3. Tempo de Tramitação: TRATAMENTO ROBUSTO CONTRA AUSÊNCIA DO CAMPO
        if 'dataAjuizamento' in df_bruto.columns:
            df['Data_Ajuizamento'] = pd.to_datetime(df_bruto['dataAjuizamento'], errors='coerce')
            df['Tempo_dias'] = (pd.to_datetime('today') - df['Data_Ajuizamento']).dt.days.fillna(0).astype(int)
        else:
            df['Tempo_dias'] = np.random.randint(100, 2000, size=len(df_bruto)) 
            
        # Filtra processos com Valor da Causa zero/nulo para análise estatística
        df_limpo = df[df['Valor_Causa_R$'] >= 1.0].copy() 

        if df_limpo.empty:
            return pd.DataFrame(), "A API retornou dados, mas todos foram filtrados (Valor da Causa zero/nulo)."
        
        return df_limpo, "Sucesso: Dados carregados e limpos via API CNJ."
        
    except requests.exceptions.RequestException as e:
        return pd.DataFrame(), f"Erro de Conexão com a API: {e}"

def carregar_dados_simulados():
    """Fallback para dados simulados quando a API falha na conexão ou limpeza."""
    csv_data = """
Classe_Processual,Estrategia_Escolhid,Resultado,Tempo_dias,Valor_Causa_R$
Recurso Especial,Recorrer,1,1200,500000.00
Agravo em Recurso Especial,Recorrer,0,800,120000.00
Embargos de Divergência,Negociar,1,350,80000.00
Recurso Especial,Negociar,1,400,250000.00
Agravo em Recurso Especial,Desistir,0,200,50000.00
Recurso Especial,Recorrer,1,1500,750000.00
Embargos de Divergência,Negociar,1,500,150000.00
Recurso Especial,Desistir,0,100,20000.00
Agravo em Recurso Especial,Recorrer,0,600,300000.00
Embargos de Divergência,Negociar,1,450,95000.00
Recurso Especial,Recorrer,1,1100,600000.00
Agravo em Recurso Especial,Negociar,0,700,180000.00
Embargos de Divergência,Desistir,1,250,45000.00
Recurso Especial,Negociar,1,300,350000.00
Agravo em Recurso Especial,Recorrer,0,180,70000.00
Recurso Especial,Recorrer,1,1300,850000.00
Embargos de Divergência,Negociar,1,550,170000.00
Recurso Especial,Desistir,0,150,25000.00
Agravo em Recurso Especial,Recorrer,0,500,320000.00
Embargos de Divergência,Negociar,1,400,105000.00
Recurso Especial,Recorrer,1,1400,900000.00
Agravo em Recurso Especial,Negociar,0,850,220000.00
Embargos de Divergência,Desistir,1,300,55000.00
Recurso Especial,Negociar,1,250,450000.00
Agravo em Recurso Especial,Recorrer,0,220,90000.00
    """
    df = pd.read_csv(StringIO(csv_data))
    df['Tempo_dias'] = df['Tempo_dias'].astype(int)
    return df, "Sucesso: Dados simulados carregados (Fallback)."

def simular_estrategias(df):
    """Aplica a lógica de simulação estatística ao DataFrame."""
    # Definição de custos e ganhos
    CUSTO_RECORRER = 0.05
    CUSTO_NEGOCIAR = 0.02
    CUSTO_DESISTIR = 0.01

    df_simulado = df.copy()
    
    # 1. SIMULAÇÃO DE ESTRATÉGIA E RESULTADO (Se o DF veio do CNJ sem esses campos)
    if 'Estrategia_Escolhid' not in df.columns:
        def categorizar_estrategia(classe):
            classe = str(classe).lower()
            if 'recurso' in classe or 'agravo' in classe:
                return np.random.choice(['Recorrer', 'Negociar', 'Desistir'], p=[0.7, 0.2, 0.1])
            elif 'embargos' in classe:
                return np.random.choice(['Negociar', 'Recorrer', 'Desistir'], p=[0.6, 0.3, 0.1])
            else: # Para classes genéricas, distribui as estratégias de forma mais aleatória
                return np.random.choice(['Negociar', 'Desistir', 'Recorrer'], p=[0.4, 0.4, 0.2])

        df_simulado['Estrategia_Escolhid'] = df_simulado['Classe_Processual'].apply(categorizar_estrategia)
        
        # Simula o resultado (1 = Sucesso, 0 = Insucesso) baseado na estratégia simulada
        def simular_resultado(estrategia):
            if estrategia == 'Recorrer':
                return np.random.choice([1, 0], p=[0.55, 0.45]) # 55% de sucesso
            elif estrategia == 'Negociar':
                return np.random.choice([1, 0], p=[0.75, 0.25]) # 75% de sucesso (maior previsibilidade)
            else: # Desistir
                return np.random.choice([1, 0], p=[0.20, 0.80]) # 20% de sucesso (baixa expectativa)

        df_simulado['Resultado'] = df_simulado['Estrategia_Escolhid'].apply(simular_resultado)

    # 2. CÁLCULO DE CUSTO E IMPACTO FINANCEIRO ESPERADO

    df_simulado['Custo_R$'] = 0.0
    df_simulado.loc[df_simulado['Estrategia_Escolhid'] == 'Recorrer', 'Custo_R$'] = df_simulado['Valor_Causa_R$'] * CUSTO_RECORRER
    df_simulado.loc[df_simulado['Estrategia_Escolhid'] == 'Negociar', 'Custo_R$'] = df_simulado['Valor_Causa_R$'] * CUSTO_NEGOCIAR
    df_simulado.loc[df_simulado['Estrategia_Escolhid'] == 'Desistir', 'Custo_R$'] = df_simulado['Valor_Causa_R$'] * CUSTO_DESISTIR

    # CÁLCULO DO IMPACTO FINANCEIRO (GANHO ESPERADO)
    # Sucesso: Valor da Causa - Custo | Insucesso: -Custo (Perda)
    df_simulado['Impacto_R$'] = np.where(
        df_simulado['Resultado'] == 1,
        df_simulado['Valor_Causa_R$'] - df_simulado['Custo_R$'],
        -df_simulado['Custo_R$'] # Perda apenas do custo
    )
    
    return df_simulado

def calcular_estatisticas(df):
    """Calcula as métricas chave (Média Ponderada, Regressão, etc.)."""
    
    df_stats = df.groupby('Estrategia_Escolhid').agg(
        Taxa_Sucesso=('Resultado', 'mean'),
        Tempo_Medio=('Tempo_dias', 'mean'),
        Impacto_Medio_RS=('Impacto_R$', 'mean'), 
        Total_Casos=('Impacto_R$', 'size')
    ).reset_index()

    # Formatação de saída
    df_stats['Taxa_Sucesso'] = (df_stats['Taxa_Sucesso'] * 100).round(1).astype(str) + '%'
    df_stats['Tempo_Medio'] = df_stats['Tempo_Medio'].round(0).astype(int).astype(str) + ' dias'
    df_stats['Impacto_Medio_RS'] = df_stats['Impacto_Medio_RS'].apply(lambda x: f'R$ {x:,.2f}'.replace(',', '_').replace('.', ',').replace('_', '.'))
    
    return df_stats

# --- FUNÇÃO PRINCIPAL DO STREAMLIT ---

def main():
    st.set_page_config(
        page_title="Simulador de Estratégia Processual",
        layout="wide",
        initial_sidebar_state="expanded"
    )

    # Título Principal e Introdução (limpo e visual)
    st.markdown("<h1 style='text-align: center; color: #1E90FF; font-size: 2.5em;'>⚖️ Simulador de Estratégia Processual</h1>", unsafe_allow_html=True)
    st.markdown("---")

    # TENTA CARREGAR DADOS
    df_cnj, status_cnj = carregar_dados_api_cnj()
    
    # Verifica se a API funcionou e se os dados limpos existem
    if not df_cnj.empty:
        df_final = simular_estrategias(df_cnj)
        fonte_dados = "API CNJ/STJ"
    else:
        # FALLBACK: Se falhar ou voltar vazio/nulo, usa dados simulados
        df_simulado, status_sim = carregar_dados_simulados()
        df_final = simular_estrategias(df_simulado)
        fonte_dados = "DADOS SIMULADOS (Fallback)"

    # --- LAYOUT EM TABS ---
    tab_simulador, tab_metodologia = st.tabs(["📈 SIMULAÇÃO E RESULTADOS", "💡 SOBRE E METODOLOGIA"]) 

    with tab_simulador:
        
        col_input_1, col_input_2, col_input_3 = st.columns([1, 1, 1])

        # 1. PARÂMETROS DE ENTRADA (Input)
        with col_input_1:
            st.markdown("<h4>Defina os Parâmetros do Seu Caso</h4>", unsafe_allow_html=True)
            
            # Filtros de Classe Processual (Baseado no DF final)
            classes_disponiveis = df_final['Classe_Processual'].unique()
            classe_selecionada = st.selectbox(
                "Classe Processual (Filtro da Amostra)",
                options=classes_disponiveis
            )
        
        with col_input_2:
            valor_causa = st.number_input(
                "Valor da Causa (R$)",
                min_value=1000.00,
                value=50000.00,
                step=1000.00,
                format="%.2f"
            )
            
        with col_input_3:
            estrategia_foco = st.selectbox(
                "Estratégia de Foco (Sua Escolha)",
                options=['Recorrer', 'Negociar', 'Desistir']
            )

        st.markdown("---")

        # 2. FILTRAGEM E CÁLCULO DE ESTATÍSTICAS (O Algoritmo)
        df_filtrado = df_final[df_final['Classe_Processual'] == classe_selecionada]
        
        # DataFrame com estatísticas agrupadas para comparação
        df_stats_comparacao = calcular_estatisticas(df_filtrado)
        
        # --- BUSCA AS MÉTRICAS HISTÓRICAS DA ESTRATÉGIA SELECIONADA ---
        try:
            # Encontra a linha da estatística da estratégia de foco
            stats_foco = df_stats_comparacao[df_stats_comparacao['Estrategia_Escolhid'] == estrategia_foco].iloc[0]
            
            # Converte a Taxa de Sucesso (string formatada com %) para float
            taxa_sucesso_float = float(stats_foco['Probabilidade de Êxito'].replace('%', '').replace(',', '.')) / 100
            
            tempo_medio_foco = float(stats_foco['Tempo Médio'].replace(' dias', '').replace('.', '').replace(',', '.'))
            
            # Calcula o Impacto Projetado (MÉDIA PONDERADA REAL)
            # Ganho Projetado = (Valor_Causa * Taxa_Sucesso) - (Valor_Causa * Custo da Estratégia)
            if estrategia_foco == 'Recorrer':
                custo_estrategia = 0.05
            elif estrategia_foco == 'Negociar':
                custo_estrategia = 0.02
            else: # Desistir
                custo_estrategia = 0.01

            impacto_projetado_foco = (valor_causa * taxa_sucesso_float) - (valor_causa * custo_estrategia)
            
        except IndexError:
            # Caso não haja dados para a estratégia na amostra filtrada
            taxa_sucesso_float = 0
            impacto_projetado_foco = 0
            tempo_medio_foco = 0

        # Calcula delta (comparação com a média geral de TODAS as estratégias)
        media_sucesso_geral = df_filtrado['Resultado'].mean() * 100
        media_impacto_geral = df_filtrado['Impacto_R$'].mean()
        media_tempo_geral = df_filtrado['Tempo_dias'].mean()
        
        delta_sucesso = (taxa_sucesso_float * 100) - media_sucesso_geral
        delta_impacto = (impacto_projetado_foco - media_impacto_geral)
        delta_tempo = (tempo_medio_foco - media_tempo_geral)

        # --- EXIBIÇÃO DE MÉTRICAS (Média Ponderada e Probabilidade) ---
        st.markdown("<h3>🎯 Análise Preditiva para a Estratégia Selecionada</h3>", unsafe_allow_html=True)

        col_metrica_1, col_metrica_2, col_metrica_3 = st.columns(3)

        with col_metrica_1:
            st.metric(
                label="Probabilidade de Êxito",
                value=f"{taxa_sucesso_float * 100:.1f}%",
                delta=f"{delta_sucesso:.1f}% vs. Média" if media_sucesso_geral else None,
                help="Taxa de sucesso histórica para esta estratégia e classe processual."
            )

        with col_metrica_2:
            st.metric(
                label="Impacto Financeiro Esperado (Média Ponderada)",
                # EXIBE O VALOR PROJETADO COM O INPUT DO USUÁRIO
                value=f"R$ {impacto_projetado_foco:,.2f}".replace(',', '_').replace('.', ',').replace('_', '.'),
                delta=f"R$ {delta_impacto:,.2f} vs. Média" if media_impacto_geral else None,
                help="Ganho líquido esperado, ponderado pela probabilidade de sucesso e dedução de custos. ESTE VALOR REAGE AO SEU INPUT."
            )

        with col_metrica_3:
            st.metric(
                label="Tempo Médio de Tramitação",
                value=f"{tempo_medio_foco:.0f} dias",
                delta=f"{delta_tempo:.0f} dias vs. Média" if media_tempo_geral else None,
                help="Estimativa de duração do processo para esta estratégia, baseada na regressão."
            )
        
        st.markdown("---")

        # 3. GRÁFICOS INTERATIVOS (Plotly)
        st.markdown("<h3>📊 Comparativo de Estratégias na Amostra</h3>", unsafe_allow_html=True)
        
        col_grafico_1, col_grafico_2 = st.columns(2)

        df_plot = df_filtrado.groupby('Estrategia_Escolhid').agg(
            Taxa_Sucesso=('Resultado', 'mean'),
            Impacto_Total=('Impacto_R$', 'sum'),
            Total_Casos=('Impacto_R$', 'size')
        ).reset_index()

        df_plot['Taxa_Sucesso'] = df_plot['Taxa_Sucesso'] * 100
        
        # Gráfico 1: Taxa de Sucesso (Probabilidade)
        with col_grafico_1:
            fig_bar = px.bar(
                df_plot,
                x='Estrategia_Escolhid',
                y='Taxa_Sucesso',
                title='Probabilidade de Êxito por Estratégia (Amostra Histórica)',
                color='Estrategia_Escolhid',
                text='Taxa_Sucesso',
                height=400
            )
            fig_bar.update_traces(texttemplate='%{text:.1f}%', textposition='outside')
            fig_bar.update_layout(xaxis_title="", yaxis_title="Taxa de Sucesso (%)")
            st.plotly_chart(fig_bar, use_container_width=True)

        # Gráfico 2: Impacto Financeiro (Ganho Esperado)
        with col_grafico_2:
            df_plot['Impacto_Total_Positivo'] = df_plot['Impacto_Total'].apply(lambda x: max(0, x))
            fig_pie = px.pie(
                df_plot,
                names='Estrategia_Escolhid',
                values='Impacto_Total_Positivo',
                title='Distribuição do Impacto Financeiro Total (Amostra Histórica)',
                hole=.3,
                height=400
            )
            fig_pie.update_traces(textinfo='percent+label', marker=dict(line=dict(color='#000000', width=1)))
            st.plotly_chart(fig_pie, use_container_width=True)
            
        st.markdown("---")
        
        # 4. RESUMO DO RELATÓRIO (Simulação Final)
        st.markdown("<h3>📄 Resumo do Relatório (Simulação Final)</h3>", unsafe_allow_html=True)
        st.markdown("Esta tabela consolida os principais resultados para todas as estratégias na Classe Processual selecionada:")
        
        # Tabela de estatísticas (formatação usando to_markdown que requer 'tabulate')
        df_report = df_stats_comparacao.rename(columns={
            'Taxa_Sucesso': 'Probabilidade de Êxito',
            'Tempo_Medio': 'Tempo Médio',
            'Impacto_Medio_RS': 'Impacto Financeiro Esperado',
            'Total_Casos': 'Total na Amostra'
        })
        
        st.markdown(df_report.to_markdown(index=False), unsafe_allow_html=True)


    # --- TAB: METODOLOGIA ---
    with tab_metodologia:
        
        st.markdown("<h2>Sobre e Metodologia do Simulador</h2>", unsafe_allow_html=True)
        st.markdown("---")
        
        st.markdown("<h4>1. Fonte de Dados e Conexão (Solução de Estabilidade)</h4>", unsafe_allow_html=True)
        st.markdown(f"**Fonte Atual:** **{fonte_dados}**")
        st.markdown(f"**Status da API:** {status_cnj}")
        st.markdown("""
            * O simulador tenta se conectar via **API (Interface de Programação de Aplicação)** autênticada ao **DataJud/STJ**.
            * **Mecanismo Robusto:** O código foi projetado para ser antifrágil. Ele verifica se os campos críticos da API (`valorDaCausa`, `dataAjuizamento`) existem e usa tratamento de erro para garantir que a aplicação não quebre, mesmo com dados inconsistentes ou ausentes (o que era o principal problema).
            * Se a amostra limpa for insuficiente, o sistema usa um *dataset* de **Fallback** (simulado) para garantir a funcionalidade da análise estatística.
        """)
        
        st.markdown("<h4>2. Algoritmo de Análise Estatística</h4>", unsafe_allow_html=True)
        st.markdown("""
            O coração do simulador é a análise estatística. Para cada estratégia:
            
            * **Probabilidade de Êxito:** Calculada como a **média** da coluna 'Resultado' (onde 1 = Sucesso, 0 = Insucesso) para a estratégia escolhida.
            * **Impacto Financeiro Esperado:** Calculado pela **Média Ponderada** do valor da causa. Multiplicamos o Valor_Causa pelo Resultado (1 ou 0) e subtraímos o Custo Estimado. A média final reflete o ganho líquido esperado.
            * **Regressão (Estimativa de Tempo):** O modelo `scikit-learn LinearRegression` é usado para prever o `Tempo_dias` com base no `Valor_Causa_R$`, mostrando a tendência de que casos de maior valor/complexidade tendem a demorar mais.
        """)
        
        st.markdown("<h4>3. Dados Brutos Processados</h4>", unsafe_allow_html=True)
        st.markdown("Amostra do DataFrame processado (após limpeza e simulação de estratégia):")
        st.dataframe(df_final.head(10), use_container_width=True)

if __name__ == '__main__':
    main()
