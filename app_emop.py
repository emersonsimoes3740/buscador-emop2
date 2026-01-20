import pandas as pd
import streamlit as st
from supabase import create_client

# 1. CONEXÃO COM SUPABASE (Segurança contra uso simultâneo)
url = st.secrets["SUPABASE_URL"]
key = st.secrets["SUPABASE_KEY"]
supabase = create_client(url, key)

# Configuração da página
st.set_page_config(page_title="Gestor EMOP - Eng. Emerson Simões", layout="wide")

def validar_acesso():
    if "autenticado" not in st.session_state:
        st.session_state.autenticado = False

    if not st.session_state.autenticado:
        st.title("🏗️ Portal de Engenharia - Eng. Emerson Simões")
        token = st.text_input("Insira seu Token de Licença:", type="password")
        
        if st.button("Acessar Sistema"):
            res = supabase.table("licencas").select("*").eq("token", token).execute()
            if res.data:
                dados_token = res.data[0]
                if not dados_token["ativa"]:
                    st.error("Esta licença foi desativada.")
                elif dados_token["em_uso"]:
                    st.warning("⚠️ Token já está em uso noutro dispositivo.")
                else:
                    # Bloqueia o token no banco de dados
                    supabase.table("licencas").update({"em_uso": True}).eq("token", token).execute()
                    st.session_state.autenticado = True
                    st.session_state.token_ativo = token
                    st.rerun()
            else:
                st.error("Token não encontrado.")
        st.stop()

validar_login = validar_acesso()

# Botão de Logout para liberar o token no banco
if st.sidebar.button("Encerrar Sessão (Liberar Licença)"):
    supabase.table("licencas").update({"em_uso": False}).eq("token", st.session_state.token_ativo).execute()
    st.session_state.autenticado = False
    st.rerun()

# 2. FUNÇÕES DE ENGENHARIA (Reintegradas)
@st.cache_data
def load_db(path):
    try:
        df = pd.read_excel(path)
        df.columns = ['C','D','U','Q','P','PC','T'] # Estrutura EMOP
        db, pai = [], None
        for _, r in df.iterrows():
            # Identifica Item Principal (Serviço)
            if pd.isna(r['Q']) and pd.notna(r['C']):
                pai = {'c': str(r['C']), 'd': str(r['D']), 'u': str(r['U']),
                       'p': float(r['P']) if pd.notna(r['P']) else 0.0, 'comp': []}
                db.append(pai)
            # Identifica Insumo (Composição)
            elif pd.notna(r['Q']) and pai:
                pai['comp'].append({'c': str(r['C']), 'd': str(r['D']), 'u': str(r['U']),
                                    'q': float(r['Q']), 'p': float(r['P']) if pd.notna(r['P']) else 0.0})
        return db
    except Exception as e:
        st.error(f"Erro ao ler planilha: {e}")
        return []

st.title("🔍 Buscador EMOP - Jan/2026")
dados = load_db('emop 0126.xlsm')

if dados:
    lista = [f"{i['c']} | {i['d']}" for i in dados]
    sel = st.selectbox("Selecione ou digite o Item:", options=[""] + lista)

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
            st.metric("VALOR TOTAL ITEM", f"R$ {v_t:,.2f}")

        if it['comp']:
            df_c = pd.DataFrame(it['comp'])
            # Identifica Mão de Obra (unidade 'H') para calcular cronograma
            mo = df_c[df_c['u'].str.upper().str.contains('H', na=False)].copy()
            
            if not mo.empty:
                st.write("### 👷 Cronograma de Execução")
                pzs = []
                cols = st.columns(len(mo))
                for i, (idx, r) in enumerate(mo.iterrows()):
                    with cols[i]:
                        n = st.number_input(f"Nº de {r['d'][:15]}:", min_value=1, value=1, key=f"mo_{idx}")
                        dias = (r['q'] * q_o) / (jor * n)
                        pzs.append(dias)
                        st.write(f"⏱️ **{dias:.2f} dias**")
                
                if pzs:
                    st.info(f"📅 **PRAZO ESTIMADO:** {max(pzs):.2f} dias úteis.")

            st.write("### 📋 Detalhamento de Insumos")
            df_c['Total'] = df_c['q'] * q_o * df_c['p']
            st.dataframe(df_c.style.format({'q': '{:.4f}', 'p': 'R$ {:.2f}', 'Total': 'R$ {:.2f}'}), use_container_width=True)
