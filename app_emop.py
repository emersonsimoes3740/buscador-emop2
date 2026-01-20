import pandas as pd
import streamlit as st
from supabase import create_client

# 1. CONEXÃO SEGURA COM SUPABASE
url = st.secrets["SUPABASE_URL"]
key = st.secrets["SUPABASE_KEY"]
supabase = create_client(url, key)

# 2. CONFIGURAÇÃO DA PÁGINA
st.set_page_config(page_title="Gestor EMOP - Eng. Emerson Simões", layout="wide")

def validar_acesso_exclusivo(token_input):
    # Busca o token no banco de dados
    res = supabase.table("licencas").select("*").eq("token", token_input).execute()
    
    if res.data:
        licenca = res.data[0]
        if not licenca["ativa"]:
            st.error("❌ Esta licença foi desativada.")
            return False
        
        # TRAVA DE USO SIMULTÂNEO
        if licenca["em_uso"]:
            st.warning("⚠️ Este token já está em uso em outro dispositivo.")
            return False
        
        # Se livre, marca como em uso no banco
        supabase.table("licencas").update({"em_uso": True}).eq("token", token_input).execute()
        return True
    
    st.error("❌ Token inválido.")
    return False

# 3. LÓGICA DE LOGIN
if "autenticado" not in st.session_state:
    st.session_state.autenticado = False

if not st.session_state.autenticado:
    st.title("🏗️ Acesso Restrito - Eng. Emerson Simões")
    st.write("Consulte a tabela EMOP 01/2026 com exclusividade.")
    
    token_digitado = st.text_input("Digite seu Token de Acesso:", type="password")
    
    if st.button("Entrar no Sistema"):
        if validar_acesso_exclusivo(token_digitado):
            st.session_state.autenticado = True
            st.session_state.token_atual = token_digitado
            st.rerun()
    st.stop()

# 4. BOTÃO DE SAÍDA (LIBERA O TOKEN)
if st.sidebar.button("Encerrar Sessão (Sair)"):
    supabase.table("licencas").update({"em_uso": False}).eq("token", st.session_state.token_atual).execute()
    st.session_state.autenticado = False
    st.rerun()

# 5. CARREGAMENTO DOS DADOS (SUA PLANILHA EMOP)
@st.cache_data
def load_db(path):
    df = pd.read_excel(path)
    # Padronização de colunas conforme sua planilha EMOP
    df.columns = ['C','D','U','Q','P','PC','T']
    # ... (sua lógica de processamento aqui)
    return df

st.title("🔍 Buscador EMOP - Jan/2026")
# Use o nome do arquivo que você subiu para o GitHub
dados = load_db('emop 0126.xlsm')

# Exiba seus dados e cálculos de engenharia abaixo...
st.success(f"Conectado com o token: {st.session_state.token_atual}")
