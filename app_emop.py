import pandas as pd
import streamlit as st
from supabase import create_client
import os

# 1. SEGURANÇA (Supabase - Bloqueio de uso simultâneo)
url = st.secrets["SUPABASE_URL"]
key = st.secrets["SUPABASE_KEY"]
supabase = create_client(url, key)

st.set_page_config(page_title="Gestor EMOP - Eng. Emerson Simões", layout="wide")

# --- SISTEMA DE LOGIN PROFISSIONAL ---
if "autenticado" not in st.session_state:
    st.session_state.autenticado = False

if not st.session_state.autenticado:
    st.title("🏗️ Portal de Engenharia - Eng. Emerson Simões")
    token = st.text_input("Insira seu Token de Licença:", type="password")
    if st.button("Acessar Sistema"):
        res = supabase.table("licencas").select("*").eq("token", token).execute()
        if res.data:
            item_token = res.data[0]
            if not item_token["ativa"]:
                st.error("Esta licença foi desativada.")
            elif item_token["em_uso"]:
                st.warning("⚠️ Este token já está em uso em outro dispositivo.")
            else:
                supabase.table("licencas").update({"em_uso": True}).eq("token", token).execute()
                st.session_state.autenticado = True
                st.session_state.token_ativo = token
                st.rerun()
        else:
            st.error("Token inválido.")
    st.stop()

# --- BUSCADOR E CALCULADORA DE ENGENHARIA ---
st.title("🔍 Buscador EMOP - Jan/2026")

@st.cache_data
def load_db(path):
    if not os.path.exists(path):
        return f"Erro: Arquivo {path} não encontrado."
    try:
        df = pd.read_excel(path)
        if len(df.columns) >= 7:
            df = df.iloc[:, :7]
            df.columns = ['C','D','U','Q','P','PC','T']
        
        db, pai = [], None
        for _, r in df.iterrows():
            # Identifica Item Principal
            if pd.notna(r['C']) and pd.isna(r['Q']):
                pai = {'c': str(r['C']), 'd': str(r['D']), 'u': str(r['U']),
                       'p': float(r['P']) if pd.notna(r['P']) else 0.0, 'comp': []}
                db.append(pai)
            # Identifica Insumos da Composição
            elif pd.notna(r['Q']) and pai:
                pai['comp'].append({'c': str(r['C']), 'd': str(r['D']), 'u': str(r['U']),
                                    'q': float(r['Q']), 'p': float(r['P']) if pd.notna(r['P']) else 0.0})
        return db
    except Exception as e:
        return f"Erro ao processar: {e}"

dados = load_db('emop 0126.xlsm')

if isinstance(dados, list) and dados:
    lista = [f"{i['c']} | {i['d']}" for i in dados]
    sel = st.selectbox("Selecione ou digite o código do serviço:", options=[""] + lista)
    
    if sel:
        it = next(i for i in dados if i['c'] == sel.split(" | ")[0])
        st.divider()
        st.subheader(f"📍 {it['c']} - {it['d']}")
        
        # Painel de Quantitativos
        col1, col2, col3 = st.columns(3)
        with col1:
            q_obra = st.number_input(f"Quantidade da Obra ({it['u']}):", min_value=0.01, value=1.0)
        with col2:
            jor = st.number_input("Jornada (h/dia):", min_value=1.0, value=8.0)
        with col3:
            st.metric("VALOR TOTAL", f"R$ {q_obra * it['p']:,.2f}")

        # --- CALCULADORA DE MÃO DE OBRA E CRONOGRAMA ---
        if it['comp']:
            df_c = pd.DataFrame(it['comp'])
            # Filtra insumos que têm 'H' (Hora) na unidade
            mo = df_c[df_c['u'].str.upper().str.contains('H', na=False)].copy()
            
            if not mo.empty:
                st.write("### 👷 Cronograma de Execução")
                pzs = []
                cols = st.columns(len(mo))
                for idx, (i, r) in enumerate(mo.iterrows()):
                    with cols[idx]:
                        # Pega o nome do profissional (ex: PEDREIRO)
                        nome_prof = " ".join(str(r['d']).split()[:2]).upper()
                        n = st.number_input(f"Nº de {nome_prof}:", min_value=1, value=1, key=f"n_{i}")
                        dias = (r['q'] * q_obra) / (jor * n)
                        pzs.append(dias)
                        st.write(f"⏱️ **{dias:.2f} dias**")
                
                if pzs:
                    st.info(f"📅 **PRAZO ESTIMADO DO SERVIÇO:** {max(pzs):.2f} dias úteis.")

            # Tabela Detalhada
            st.write("### 📋 Composição Detalhada")
            df_c['Total'] = df_c['q'] * q_obra * df_c['p']
            st.dataframe(df_c.style.format({'q': '{:.4f}', 'p': 'R$ {:.2f}', 'Total': 'R$ {:.2f}'}), use_container_width=True)

# Botão de Logout para liberar o token
if st.sidebar.button("Encerrar Sessão (Sair)"):
    supabase.table("licencas").update({"em_uso": False}).eq("token", st.session_state.token_ativo).execute()
    st.session_state.autenticado = False
    st.rerun()
