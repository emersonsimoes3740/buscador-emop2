import pandas as pd
import streamlit as st
from supabase import create_client

# 1. CONEXÃO SEGURA COM SUPABASE (Secrets do Streamlit)
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
            st.error("❌ Esta licença foi desativada pelo administrador.")
            return False
        
        # TRAVA DE USO SIMULTÂNEO
        if licenca["em_uso"]:
            st.warning("⚠️ Este token já está em uso noutro dispositivo.")
            return False
        
        # Marca como em uso ao entrar
        supabase.table("licencas").update({"em_uso": True}).eq("token", token_input).execute()
        return True
    
    st.error("❌ Token inválido.")
    return False

# 3. INTERFACE DE LOGIN
if "autenticado" not in st.session_state:
    st.session_state.autenticado = False

if not st.session_state.autenticado:
    st.title("🏗️ Acesso Restrito - Eng. Emerson Simões")
    st.write("Insira sua licença para acessar a base EMOP 01/2026.")
    
    token_digitado = st.text_input("Token de Acesso:", type="password")
    
    if st.button("Validar e Entrar"):
        if validar_acesso_exclusivo(token_digitado):
            st.session_state.autenticado = True
            st.session_state.token_atual = token_digitado
            st.rerun()
    st.stop() 

# 4. BOTÃO DE LOGOUT NO MENU LATERAL
if st.sidebar.button("Encerrar Sessão (Sair)"):
    # Libera o token no banco de dados ao sair
    supabase.table("licencas").update({"em_uso": False}).eq("token", st.session_state.token_atual).execute()
    st.session_state.autenticado = False
    st.rerun()

# 5. CARREGAMENTO E PROCESSAMENTO DA PLANILHA EMOP
@st.cache_data
def load_db(path):
    try:
        df = pd.read_excel(path)
        df.columns = ['C','D','U','Q','P','PC','T'] # Padronização EMOP
        db, pai = [], None
        for _, r in df.iterrows():
            if pd.isna(r['Q']) and pd.notna(r['C']):
                pai = {
                    'c': str(r['C']), 'd': str(r['D']), 'u': str(r['U']),
                    'p': float(r['P']) if pd.notna(r['P']) else 0.0, 'comp': []
                }
                db.append(pai)
            elif pd.notna(r['Q']) and pai:
                pai['comp'].append({
                    'c': str(r['C']), 'd': str(r['D']), 'u': str(r['U']),
                    'q': float(r['Q']), 'p': float(r['P']) if pd.notna(r['P']) else 0.0
                })
        return db
    except Exception as e:
        st.error(f"Erro ao carregar Excel: {e}")
        return []

st.title("🔍 Buscador EMOP - Jan/2026")
dados = load_db('emop 0126.xlsm') # Arquivo no seu repositório

if dados:
    lista = [f"{i['c']} | {i['d']}" for i in dados]
    sel = st.selectbox("Selecione o Item:", options=[""] + lista)

    if sel:
        it = next(i for i in dados if i['c'] == sel.split(" | ")[0])
        st.subheader(f"📍 {it['c']} - {it['d']}")
        
        q_o = st.number_input(f"Quantidade da Obra ({it['u']}):", min_value=0.01, value=1.0)
        v_t = q_o * it['p']
        st.metric("VALOR TOTAL ITEM", f"R$ {v_t:,.2f}")

        if it['comp']:
            st.write("### 📋 Composição e Insumos")
            df_c = pd.DataFrame(it['comp'])
            df_c['Total'] = df_c['q'] * q_o * df_c['p']
            st.dataframe(df_c, use_container_width=True)

st.sidebar.markdown("---")
st.sidebar.write(f"Conectado: {st.session_state.token_atual}")
