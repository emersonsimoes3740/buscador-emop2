import pandas as pd
import streamlit as st
from supabase import create_client

# 1. CONEXÃO SEGURA COM SUPABASE (Proteção contra uso simultâneo)
# Certifique-se de que estas chaves estão nos 'Secrets' do Streamlit Cloud
url = st.secrets["SUPABASE_URL"]
key = st.secrets["SUPABASE_KEY"]
supabase = create_client(url, key)

# Configuração da página para o padrão de engenharia
st.set_page_config(page_title="Gestor EMOP - Eng. Emerson Simões", layout="wide")

def validar_acesso():
    if "autenticado" not in st.session_state:
        st.session_state.autenticado = False

    if not st.session_state.autenticado:
        st.title("🏗️ Portal de Engenharia - Eng. Emerson Simões")
        st.write("Acesse a base de dados EMOP 01/2026 com sua licença exclusiva.")
        
        token = st.text_input("Insira seu Token de Licença:", type="password")
        
        if st.button("Acessar Sistema"):
            # Consulta o banco de dados Supabase
            res = supabase.table("licencas").select("*").eq("token", token).execute()
            if res.data:
                dados_token = res.data[0]
                if not dados_token["ativa"]:
                    st.error("Esta licença foi desativada pelo administrador.")
                elif dados_token["em_uso"]:
                    st.warning("⚠️ Este token já está em uso noutro dispositivo. Encerre a outra sessão.")
                else:
                    # Bloqueia o token no banco para uso exclusivo
                    supabase.table("licencas").update({"em_uso": True}).eq("token", token).execute()
                    st.session_state.autenticado = True
                    st.session_state.token_ativo = token
                    st.rerun()
            else:
                st.error("Token não encontrado ou inválido.")
        st.stop()

# Executa a trava de segurança
validar_acesso()

# Botão de Logout no Menu Lateral para liberar o token no banco de dados
if st.sidebar.button("Encerrar Sessão (Sair)"):
    supabase.table("licencas").update({"em_uso": False}).eq("token", st.session_state.token_ativo).execute()
    st.session_state.autenticado = False
    st.rerun()

# 2. FUNÇÕES DE PROCESSAMENTO DA PLANILHA EMOP
@st.cache_data
def load_db(path):
    try:
        df = pd.read_excel(path)
        # Padronização das colunas conforme a estrutura EMOP identificada
        df.columns = ['C','D','U','Q','P','PC','T'] 
        db, pai = [], None
        for _, r in df.iterrows():
            # Identifica Item Principal (Serviço) - Geralmente sem quantidade na linha do título
            if pd.isna(r['Q']) and pd.notna(r['C']):
                pai = {
                    'c': str(r['C']), 
                    'd': str(r['D']), 
                    'u': str(r['U']),
                    'p': float(r['P']) if pd.notna(r['P']) else 0.0, 
                    'comp': []
                }
                db.append(pai)
            # Identifica Insumos da Composição (Filhos)
            elif pd.notna(r['Q']) and pai:
                pai['comp'].append({
                    'c': str(r['C']), 
                    'd': str(r['D']), 
                    'u': str(r['U']),
                    'q': float(r['Q']), 
                    'p': float(r['P']) if pd.notna(r['P']) else 0.0
                })
        return db
    except Exception as e:
        st.error(f"Erro ao carregar a planilha EMOP: {e}")
        return []

st.title("🔍 Buscador EMOP - Janeiro/2026")
# Carrega os dados da planilha que você subiu para o GitHub
dados = load_db('emop 0126.xlsm')

if dados:
