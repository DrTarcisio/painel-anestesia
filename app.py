# +
import streamlit as st
import pandas as pd
import pyodbc
import plotly.express as px
from datetime import datetime, date

# --- Configuração da Página ---
st.set_page_config(page_title="Dashboard Cirúrgico", layout="wide")

# --- Conexão (Segura) ---
@st.cache_resource
def init_connection():
    try:
        # Tenta conectar usando secrets (nuvem/local seguro) ou direto (fallback)
        if "db_server" in st.secrets:
            server = st.secrets["db_server"]
            database = st.secrets["db_name"]
            uid = st.secrets["db_user"]
            pwd = st.secrets["db_password"]
        else:
            # Caso não tenha secrets configurado, usa valores padrão (cuidado com segurança)
            # Retorne None ou use variáveis de ambiente aqui se preferir
            return None 

        conn = pyodbc.connect(
            "DRIVER={ODBC Driver 17 for SQL Server};"
            f"SERVER={server};" 
            "PORT=1433;"
            f"DATABASE={database};"
            f"UID={uid};"
            f"PWD={pwd};"
            "Encrypt=no"
        )
        return conn
    except Exception as e:
        st.error(f"Erro de conexão: {e}")
        return None

# --- Leitura de Dados ---
@st.cache_data(ttl=600)
def load_data(start_date, end_date):
    conn = init_connection()
    if conn:
        query = f"""
            SELECT NUMERO_DA_FICHA, HOSPITAL, DATA_INTERNACAO, NOME_DO_PACIENTE,
                   IDADE, SEXO, NOME_CONVENIO, ANESTESISTA, CIRURGIAO1,
                   OBSERVACAO, SITUACAO, VALOR
            FROM dbo.FICHA
            WHERE DATA_INTERNACAO BETWEEN ? AND ?
        """
        try:
            df = pd.read_sql(query, conn, params=[start_date, end_date], parse_dates=['DATA_INTERNACAO'])
            
            # Tratamento de Nulos e Tipos
            df['IDADE'] = pd.to_numeric(df['IDADE'], errors='coerce').fillna(0)
            df['VALOR'] = pd.to_numeric(df['VALOR'], errors='coerce').fillna(0)

            # Padronização de Texto (Maiúsculas e sem espaços extras)
            cols_texto = ['HOSPITAL', 'ANESTESISTA', 'NOME_CONVENIO', 'NOME_DO_PACIENTE', 'CIRURGIAO1']
            for col in cols_texto:
                df[col] = df[col].astype(str).str.upper().str.strip()
                df[col] = df[col].replace(['NAN', 'NONE', 'NULL', ''], 'NÃO INFORMADO')

            return df.sort_values('DATA_INTERNACAO')
        except Exception as e:
            st.error(f"Erro ao ler tabela: {e}")
            return pd.DataFrame()
    return pd.DataFrame()

# --- Sidebar (Filtros Múltiplos) ---
st.sidebar.header("Filtros")

# 1. Filtro de Data
data_inicial = st.sidebar.date_input("Data Inicial", date(2025, 1, 1))
data_final = st.sidebar.date_input("Data Final", datetime.now())

if data_inicial > data_final:
    st.sidebar.error("A data inicial não pode ser maior que a final.")

# Carregar dados iniciais
df = load_data(data_inicial, data_final)

if not df.empty:
    # Preparar listas únicas (Removi o "Todos" manual, pois o multiselect vazio já faz isso)
    lista_hospitais = sorted(df['HOSPITAL'].unique().tolist())
    lista_convenios = sorted(df['NOME_CONVENIO'].unique().tolist())
    lista_anestesistas = sorted(df['ANESTESISTA'].unique().tolist())

    st.sidebar.markdown("---")
    st.sidebar.caption("Deixe em branco para selecionar TODOS")

    # 2. Seletores Múltiplos (Multiselect)
    sel_hospitais = st.sidebar.multiselect("Hospitais", options=lista_hospitais)
    sel_convenios = st.sidebar.multiselect("Convênios", options=lista_convenios)
    sel_anestesistas = st.sidebar.multiselect("Anestesistas", options=lista_anestesistas)

    # Lógica de Filtragem
    df_filtered = df.copy()

    # Se a lista não estiver vazia, filtra. Se estiver vazia, mantém tudo.
    if sel_hospitais:
        df_filtered = df_filtered[df_filtered['HOSPITAL'].isin(sel_hospitais)]
    
    if sel_convenios:
        df_filtered = df_filtered[df_filtered['NOME_CONVENIO'].isin(sel_convenios)]
        
    if sel_anestesistas:
        df_filtered = df_filtered[df_filtered['ANESTESISTA'].isin(sel_anestesistas)]

    # --- Dashboard Principal ---
    st.title("📊 Painel Multiselect")
    st.markdown(f"**Período:** {data_inicial.strftime('%d/%m/%Y')} a {data_final.strftime('%d/%m/%Y')}")

    # KPIs
    total_val = df_filtered['VALOR'].sum()
    df_pagantes = df_filtered[df_filtered['VALOR'] > 0]
    ticket_medio = df_pagantes['VALOR'].mean() if not df_pagantes.empty else 0

    c1, c2, c3 = st.columns(3)
    c1.metric("Faturamento Filtrado", f"R$ {total_val:,.2f}")
    c2.metric("Ticket Médio", f"R$ {ticket_medio:,.2f}")
    c3.metric("Procedimentos", len(df_filtered))

    st.divider()

    # --- Pesquisa Individual ---
    with st.expander("🔍 Pesquisa por Nome", expanded=False):
        nome_busca = st.text_input("Nome do Paciente:")
        if nome_busca:
            df_busca = df_filtered[df_filtered['NOME_DO_PACIENTE'].str.contains(nome_busca.upper())]
            st.dataframe(df_busca, use_container_width=True)

    # --- Gráficos ---
    tab1, tab2, tab3 = st.tabs(["Evolução", "Convênios", "Hospitais"])

    with tab1:
        # Agrupamento Mensal
        df_filtered['Mes'] = df_filtered['DATA_INTERNACAO'].dt.strftime('%Y-%m')
        df_trend = df_filtered.groupby('Mes')['VALOR'].sum().reset_index()
        fig1 = px.bar(df_trend, x='Mes', y='VALOR', title="Evolução Mensal")
        st.plotly_chart(fig1, use_container_width=True)

    with tab2:
        # Top Convênios
        df_conv = df_filtered.groupby('NOME_CONVENIO')['NUMERO_DA_FICHA'].count().reset_index()
        df_conv = df_conv.sort_values('NUMERO_DA_FICHA', ascending=False).head(10)
        fig2 = px.pie(df_conv, values='NUMERO_DA_FICHA', names='NOME_CONVENIO', title="Distribuição por Convênio")
        st.plotly_chart(fig2, use_container_width=True)

    with tab3:
        # Ranking Hospitais
        df_hosp = df_filtered.groupby('HOSPITAL')['VALOR'].sum().reset_index()
        df_hosp = df_hosp.sort_values('VALOR', ascending=False)
        fig3 = px.bar(df_hosp, x='HOSPITAL', y='VALOR', title="Faturamento por Hospital")
        st.plotly_chart(fig3, use_container_width=True)

    st.subheader("Dados Detalhados")
    st.dataframe(df_filtered, use_container_width=True)

else:
    st.warning("Nenhum dado encontrado para o período selecionado.")
# -
# !streamlit run app.py



