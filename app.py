# +
import streamlit as st
import pandas as pd
import pyodbc
import plotly.express as px
from datetime import datetime, date
import time

# --- Configuração da Página ---
st.set_page_config(page_title="Dashboard Cirúrgico", layout="wide")

# --- Função de Login ---
def check_password():
    """Retorna True se o usuário estiver logado com sucesso."""
    if 'logged_in' not in st.session_state:
        st.session_state['logged_in'] = False

    if st.session_state['logged_in']:
        return True

    # Layout da tela de login
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.markdown("## 🔒 Acesso Restrito - Clianest")
        st.caption("Por favor, faça login para acessar os dados cirúrgicos.")
        
        # Inputs de usuário e senha
        user_input = st.text_input("Usuário")
        pass_input = st.text_input("Senha", type="password")
        
        if st.button("Entrar"):
            # Verifica com as senhas salvas no secrets (ou hardcoded se preferir arriscar)
            # Usei st.secrets para proteger você de expor a senha no GitHub
            valida_user = st.secrets["admin_user"]
            valida_pass = st.secrets["admin_password"]

            if user_input == valida_user and pass_input == valida_pass:
                st.session_state['logged_in'] = True
                st.success("Login realizado com sucesso!")
                time.sleep(1) # Aguarda um pouco para mostrar a mensagem
                st.rerun() # Recarrega a página para entrar no painel
            else:
                st.error("Usuário ou senha incorretos.")
                
    return False

# --- Se NÃO estiver logado, para o script aqui ---
if not check_password():
    st.stop()

# ==============================================================================
# DAQUI PARA BAIXO É O SEU DASHBOARD ORIGINAL (SÓ EXECUTA SE ESTIVER LOGADO)
# ==============================================================================

# --- Conexão (Segura) ---
@st.cache_resource
def init_connection():
    try:
        # Tenta conectar usando secrets
        if "db_server" in st.secrets:
            server = st.secrets["db_server"]
            database = st.secrets["db_name"]
            uid = st.secrets["db_user"]
            pwd = st.secrets["db_password"]
        else:
            return None 

        conn = pyodbc.connect(
            "DRIVER={ODBC Driver 17 for SQL Server};" # Driver 17 para compatibilidade
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

            # Padronização de Texto
            cols_texto = ['HOSPITAL', 'ANESTESISTA', 'NOME_CONVENIO', 'NOME_DO_PACIENTE', 'CIRURGIAO1']
            for col in cols_texto:
                df[col] = df[col].astype(str).str.upper().str.strip()
                df[col] = df[col].replace(['NAN', 'NONE', 'NULL', ''], 'NÃO INFORMADO')

            return df.sort_values('DATA_INTERNACAO')
        except Exception as e:
            st.error(f"Erro ao ler tabela: {e}")
            return pd.DataFrame()
    return pd.DataFrame()

# --- Adiciona Botão de Logout na Sidebar ---
st.sidebar.button("Sair / Logout", on_click=lambda: st.session_state.update(logged_in=False))

# --- Sidebar (Filtros) ---
st.sidebar.header("Filtros")

# Filtro de Data
data_inicial = st.sidebar.date_input("Data Inicial", date(2025, 1, 1))
data_final = st.sidebar.date_input("Data Final", datetime.now())

if data_inicial > data_final:
    st.sidebar.error("A data inicial não pode ser maior que a final.")

# Carregar dados
df = load_data(data_inicial, data_final)

if not df.empty:
    lista_hospitais = sorted(df['HOSPITAL'].unique().tolist())
    lista_convenios = sorted(df['NOME_CONVENIO'].unique().tolist())
    lista_anestesistas = sorted(df['ANESTESISTA'].unique().tolist())

    st.sidebar.markdown("---")
    st.sidebar.caption("Deixe em branco para selecionar TODOS")

    sel_hospitais = st.sidebar.multiselect("Hospitais", options=lista_hospitais)
    sel_convenios = st.sidebar.multiselect("Convênios", options=lista_convenios)
    sel_anestesistas = st.sidebar.multiselect("Anestesistas", options=lista_anestesistas)

    df_filtered = df.copy()

    if sel_hospitais:
        df_filtered = df_filtered[df_filtered['HOSPITAL'].isin(sel_hospitais)]
    if sel_convenios:
        df_filtered = df_filtered[df_filtered['NOME_CONVENIO'].isin(sel_convenios)]
    if sel_anestesistas:
        df_filtered = df_filtered[df_filtered['ANESTESISTA'].isin(sel_anestesistas)]

    # --- Dashboard Principal ---
    st.title("📊 Painel Multiselect")
    st.markdown(f"**Período:** {data_inicial.strftime('%d/%m/%Y')} a {data_final.strftime('%d/%m/%Y')}")

    total_val = df_filtered['VALOR'].sum()
    df_pagantes = df_filtered[df_filtered['VALOR'] > 0]
    ticket_medio = df_pagantes['VALOR'].mean() if not df_pagantes.empty else 0

    c1, c2, c3 = st.columns(3)
    c1.metric("Faturamento Filtrado", f"R$ {total_val:,.2f}")
    c2.metric("Ticket Médio", f"R$ {ticket_medio:,.2f}")
    c3.metric("Procedimentos", len(df_filtered))

    st.divider()

    with st.expander("🔍 Pesquisa por Nome", expanded=False):
        nome_busca = st.text_input("Nome do Paciente:")
        if nome_busca:
            df_busca = df_filtered[df_filtered['NOME_DO_PACIENTE'].str.contains(nome_busca.upper())]
            st.dataframe(df_busca, use_container_width=True)

    tab1, tab2, tab3 = st.tabs(["Evolução", "Convênios", "Hospitais"])

    with tab1:
        df_filtered['Mes'] = df_filtered['DATA_INTERNACAO'].dt.strftime('%Y-%m')
        df_trend = df_filtered.groupby('Mes')['VALOR'].sum().reset_index()
        fig1 = px.bar(df_trend, x='Mes', y='VALOR', title="Evolução Mensal")
        st.plotly_chart(fig1, use_container_width=True)

    with tab2:
        df_conv = df_filtered.groupby('NOME_CONVENIO')['NUMERO_DA_FICHA'].count().reset_index()
        df_conv = df_conv.sort_values('NUMERO_DA_FICHA', ascending=False).head(10)
        fig2 = px.pie(df_conv, values='NUMERO_DA_FICHA', names='NOME_CONVENIO', title="Distribuição por Convênio")
        st.plotly_chart(fig2, use_container_width=True)

    with tab3:
        df_hosp = df_filtered.groupby('HOSPITAL')['VALOR'].sum().reset_index()
        df_hosp = df_hosp.sort_values('VALOR', ascending=False)
        fig3 = px.bar(df_hosp, x='HOSPITAL', y='VALOR', title="Faturamento por Hospital")
        st.plotly_chart(fig3, use_container_width=True)

    st.subheader("Dados Detalhados")
    st.dataframe(df_filtered, use_container_width=True)
    st.caption("Developed by Tarcisio Buettel, MD")

else:
    st.warning("Nenhum dado encontrado para o período selecionado.")
