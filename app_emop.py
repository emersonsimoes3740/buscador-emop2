import pandas as pd
import streamlit as st

# 1. CONFIGURAÇÃO INICIAL E SEGURANÇA
st.set_page_config(page_title="EMOP 2026 - Eng. Emerson Simões", layout="wide")

def validar_token(token_usuario):
    try:
        # Tenta ler a lista de 10 mil tokens que você gerou
        with open("tokens_validos.txt", "r") as f:
            tokens = [linha.strip() for linha in f.readlines()]
            return token_usuario in tokens
    except FileNotFoundError:
        # Token mestre caso o arquivo de 10 mil tokens ainda não esteja no GitHub
        return token_usuario == "ENG-EMERSON-2026"

if "autenticado" not in st.session_state:
    st.session_state.autenticado = False

if not st.session_state.autenticado:
    st.title("🔐 Acesso Restrito - Gestor EMOP")
    st.write("Insira sua licença de uso para acessar a base de dados.")
    
    token_input = st.text_input("Digite seu Token de Acesso:", type="password")
    
    if st.button("Validar Licença"):
        if validar_token(token_input):
            st.session_state.autenticado = True
            st.success("Acesso autorizado!")
            st.rerun()
        else:
            st.error("Token inválido ou expirado. Fale com o administrador.")
    st.stop() # Bloqueia o carregamento do restante do app

# 2. LÓGICA DO SISTEMA (Só executa após validação)
@st.cache_data
def load_db(path):
    try:
        df = pd.read_excel(path)
        # Padronizando as colunas da EMOP (A a G)
        df.columns = ['C','D','U','Q','P','PC','T']
        db, pai = [], None
        for _, r in df.iterrows():
            # Identifica Item Principal (Serviço)
            if pd.isna(r['Q']) and pd.notna(r['C']):
                pai = {'c':str(r['C']),'d':str(r['D']),'u':str(r['U']),'
