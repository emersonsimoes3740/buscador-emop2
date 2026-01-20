import pandas as pd
import streamlit as st
from supabase import create_client
import os

# 1. SEGURANÇA (Supabase)
url = st.secrets["SUPABASE_URL"]
key = st.secrets["SUPABASE_KEY"]
supabase = create_client(url, key)

st.set_page_config(page_title="Gestor EMOP - Eng. Emerson Simões", layout="wide")

# --- TRAVA DE ACESSO ---
if "autenticado" not in st.session_state:
    st.session_state.autenticado = False

if not st.session_state.autenticado:
    st.title("🏗️ Portal de Engenharia - Eng. Emerson Simões")
    token = st.text_input("Insira seu Token:", type="password")
    if st.button("Acessar"):
        res = supabase.table("licencas").select("*").eq("token", token).execute()
        if res.data and not res.data[0]["em_uso"]:
            supabase.table("licencas").update({"em_uso": True}).eq("token", token).execute()
            st.session_state.autenticado = True
            st.session_state.token_ativo = token
            st.rerun()
        else:
            st.error("Erro no token ou já em uso.")
    st.stop()

# --- BUSCADOR DE ENGENHARIA ---
st.title("🔍 Buscador EMOP - Jan/2026")

@st.cache_data
def load_db(path):
    # Verificação de arquivo (Diagnóstico)
    if not os.path.exists(path):
        return f"ERRO: O arquivo {path} não foi encontrado no GitHub."
    
    try:
        df = pd.read_excel(path)
        # Se a planilha tiver mais ou menos colunas, ajustamos aqui:
        if len(df.columns) >= 7:
            df = df.iloc[:, :7] # Garante que pegamos as 7 colunas da EMOP
            df.columns = ['C','D','U','Q','P','PC','T']
        
        db, pai = [], None
        for _, r in df.iterrows():
            # Critério EMOP: Se tem Código e não tem Quantidade, é o Item Principal
            if pd.notna(r['C']) and pd.isna(r['Q']):
                pai = {'c': str(r['C']), 'd': str(r['D']), 'u': str(r['U']),
                       'p': float(r['P']) if pd.notna(r['P']) else 0.0, 'comp': []}
                db.append(pai)
            elif pd.notna(r['Q']) and pai:
                pai['comp'].append({'c': str(r['C']), 'd': str(r['D']), 'u': str(r['U']),
                                    'q': float(r['Q']), 'p': float(r['P']) if pd.notna(r['P']) else 0.0})
        return db
    except Exception as e:
        return f"Erro ao processar Excel: {e}"

# Tenta carregar os dados
dados = load_db('emop 0126.xlsm')

# Verificador de erros
if isinstance(dados, str):
    st.error(dados)
    st.info("Verifique se o arquivo 'emop 0126.xlsm' está na pasta raiz do seu GitHub.")
elif dados:
    lista = [f"{i['c']} | {i['d']}" for i in dados]
    sel = st.selectbox("Selecione o Item:", options=[""] + lista)
    
    if sel:
        it = next(i for i in dados if i['c'] == sel.split(" | ")[0])
        st.subheader(f"📍 {it['c']} - {it['d']}")
        st.write(f"**Unidade:** {it['u']} | **Preço Unitário:** R$ {it['p']:.2f}")
        
        if it['comp']:
            st.write("### 📋 Composição")
            st.table(pd.DataFrame(it['comp']))
else:
    st.warning("Nenhum dado encontrado na planilha. Verifique a formatação.")

# Logout
if st.sidebar.button("Sair"):
    supabase.table("licencas").update({"em_uso": False}).eq("token", st.session_state.token_ativo).execute()
    st.session_state.autenticado = False
    st.rerun()
