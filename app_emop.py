import pandas as pd
import streamlit as st

# 1. TRAVA DE SEGURANÇA E CONFIGURAÇÃO INICIAL
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
    token_input = st.text_input("Insira seu Token de Licença:", type="password")
    if st.button("Validar Acesso"):
        if validar_token(token_input):
            st.session_state.autenticado = True
            st.rerun()
        else:
            st.error("Token inválido ou expirado.")
    st.stop() # Interrompe o script aqui se não estiver logado

# 2. LOGICA DO SEU SISTEMA (Só roda após o Token)
@st.cache_data
def load_db(path):
    try:
        df = pd.read_excel(path)
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

st.title("🏗️ Gestor de Obras EMOP - Jan/2026")
st.markdown("**Desenvolvido por Eng. Emerson Simões**")

# Carregando o arquivo que você subiu no GitHub
dados = load_db('emop 0126.xlsm')

if dados:
    lista = [f"{i['c']} | {i['d']}" for i in dados]
    sel = st.selectbox("Selecione ou digite o Item para analisar:", options=[""] + lista)

    if sel:
        it = next(i for i in dados if i['c'] == sel.split(" | ")[0])
        st.divider()
        st.subheader(f"📍 {it['c']} - {it['d']}")
        
        c1, c2, c3 = st.columns(3)
        with c1:
            q_o = st.number_input(f"Quantidade da Obra ({it['u']}):", min_value=0.01, value=100.0)
        with c2:
            jor = st.number_input("Jornada de Trabalho (h/dia):", min_value=1.0, value=8.0)
        with c3:
            v_t = q_o * it['p']
            st.metric("VALOR TOTAL ITEM", f"
