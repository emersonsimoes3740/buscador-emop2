import pandas as pd
import streamlit as st
from supabase import create_client, Client

# --- 1. CONFIGURAÇÃO E SEGURANÇA ---
st.set_page_config(page_title="EMOP 2026 - Eng. Emerson Simões", layout="wide")

# Inicialização do Supabase via Secrets
try:
    url = st.secrets["SUPABASE_URL"]
    key = st.secrets["SUPABASE_KEY"]
    supabase: Client = create_client(url, key)
except Exception as e:
    st.error("Erro ao carregar credenciais do banco de dados (Secrets).")
    st.stop()

# Função de Validação de Token
def validar_acesso(token_input):
    try:
        res = supabase.table("licencas").select("*").eq("token", token_input).execute()
        return len(res.data) > 0
    except:
        return False

# --- 2. CONTROLE DE ACESSO (LOGIN) ---
if "autenticado" not in st.session_state:
    st.session_state.autenticado = False

if not st.session_state.autenticado:
    st.title("🏗️ Acesso ao Gestor EMOP")
    token = st.text_input("Insira seu Token de Acesso:", type="password")
    if st.button("Entrar"):
        if validar_acesso(token):
            st.session_state.autenticado = True
            st.rerun()
        else:
            st.error("Token inválido.")
    st.stop() # Interrompe o script aqui se não estiver logado

# --- 3. SEU SCRIPT ORIGINAL (ÁREA LOGADA) ---

@st.cache_data
def load_db(path):
    try:
        df = pd.read_excel(path)
        # Padronizando as colunas da EMOP (A a G)
        df.columns = ['C','D','U','Q','P','PC','T']
        db, pai = [], None
        for _, r in df.iterrows():
            if pd.isna(r['Q']) and pd.notna(r['C']):
                pai = {'c':str(r['C']),'d':str(r['D']),'u':str(r['U']),'p':float(r['P']) if pd.notna(r['P']) else 0.0,'comp':[]}
                db.append(pai)
            elif pd.notna(r['Q']) and pai:
                pai['comp'].append({'c':str(r['C']),'d':str(r['D']),'u':str(r['U']),'q':float(r['Q']),'p':float(r['P']) if pd.notna(r['P']) else 0.0})
        return db
    except Exception as e:
        st.error(f"Erro ao carregar Excel: {e}")
        return []

st.sidebar.button("Sair", on_click=lambda: st.session_state.update({"autenticado": False}))
st.title("🏗️ Gestor de Obras EMOP - Jan/2026")
st.markdown("**Desenvolvido por Eng. Emerson Simões**")

# Carrega o arquivo (Certifique-se que o arquivo está na mesma pasta no GitHub)
dados = load_db('emop 0126.xlsm')

if dados:
    lista = [f"{i['c']} | {i['d
