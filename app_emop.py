import pandas as pd
import streamlit as st
from supabase import create_client
import os
import time

# 1. CONEXÃO SEGURA COM SUPABASE
url = st.secrets["SUPABASE_URL"]
key = st.secrets["SUPABASE_KEY"]
supabase = create_client(url, key)

st.set_page_config(page_title="Gestor EMOP - Eng. Emerson Simões", layout="wide")

# --- LÓGICA DE ACESSO (PAGANTE + DEGUSTAÇÃO) ---
def gerenciar_acesso():
    if "autenticado" not in st.session_state:
        st.session_state.autenticado = False
    
    if not st.session_state.autenticado:
        st.title("🏗️ Portal Célula Engenharia - Eng. Emerson Simões")
        st.subheader("Buscador EMOP Janeiro/2026 - Atualização Mensal")
        
        token = st.text_input("Insira seu Token ou use o cupom de teste:", type="password")
        
        # CONFIGURAÇÃO DO TESTE GRÁTIS
        TOKEN_TESTE = "TESTE-GRATIS-30MIN" # Este é o token que você vai divulgar
        
        if st.button("Acessar Sistema"):
            # CASO 1: TOKEN DE TESTE
            if token == TOKEN_TESTE:
                if "inicio_teste" not in st.session_state:
                    st.session_state.inicio_teste = time.time()
                st.session_state.autenticado = True
                st.session_state.tipo_acesso = "gratis"
                st.session_state.token_ativo = TOKEN_TESTE
                st.rerun()
            
            # CASO 2: TOKEN PAGO (SUPABASE)
            else:
                res = supabase.table("licencas").select("*").eq("token", token).execute()
                if res.data:
                    item = res.data[0]
                    if not item["ativa"]:
                        st.error("Licença desativada.")
                    elif item["em_uso"]:
                        st.warning("⚠️ Token em uso noutro dispositivo.")
                    else:
                        supabase.table("licencas").update({"em_uso": True}).eq("token", token).execute()
                        st.session_state.autenticado = True
                        st.session_state.tipo_acesso = "pago"
                        st.session_state.token_ativo = token
                        st.rerun()
                else:
                    st.error("Token inválido.")
        st.stop()

gerenciar_acesso()

# --- VERIFICAÇÃO DE TEMPO PARA ACESSO GRÁTIS ---
if st.session_state.get("tipo_acesso") == "gratis":
    tempo_passado = (time.time() - st.session_state.inicio_teste) / 60
    tempo_restante = 30 - tempo_passado # Limite de 30 minutos
    
    if tempo_restante <= 0:
        st.error("⏳ Seu tempo de teste de 30 minutos expirou!")
        st.info("Entre em contato com a Célula Engenharia para adquirir sua licença completa.")
        if st.button("Voltar ao Início"):
            st.session_state.autenticado = False
            st.rerun()
        st.stop()
    else:
        st.sidebar.warning(f"⏱️ Tempo de Teste: {int(tempo_restante)} min restantes")

# Botão Sair (Libera token se for pago)
if st.sidebar.button("Encerrar Sessão"):
    if st.session_state.get("tipo_acesso") == "pago":
        supabase.table("licencas").update({"em_uso": False}).eq("token", st.session_state.token_ativo).execute()
    st.session_state.autenticado = False
    st.rerun()

# --- BUSCADOR E CALCULADORA (SUA INTELIGÊNCIA) ---
@st.cache_data
def load_db(path):
    if not os.path.exists(path): return []
    df = pd.read_excel(path)
    if len(df.columns) >= 7:
        df = df.iloc[:, :7]
        df.columns = ['C','D','U','Q','P','PC','T']
    db, pai = [], None
    for _, r in df.iterrows():
        if pd.notna(r['C']) and pd.isna(r['Q']):
            pai = {'c': str(r['C']), 'd': str(r['D']), 'u': str(r['U']), 'p': float(r['P']) if pd.notna(r['P']) else 0.0, 'comp': []}
            db.append(pai)
        elif pd.notna(r['Q']) and pai:
            pai['comp'].append({'c': str(r['C']), 'd': str(r['D']), 'u': str(r['U']), 'q': float(r['Q']), 'p': float(r['P']) if pd.notna(r['P']) else 0.0})
    return db

dados = load_db('emop 0126.xlsm') # Planilha EMOP Janeiro/2026

if dados:
    st.title("🔍 Buscador EMOP - Jan/2026")
    lista = [f"{i['c']} | {i['d']}" for i in dados]
    sel = st.selectbox("Busque pelo código ou nome do serviço:", options=[""] + lista)
    
    if sel:
        it = next(i for i in dados if i['c'] == sel.split(" | ")[0])
        st.divider()
        st.subheader(f"📍 {it['c']} - {it['d']}")
        
        c1, c2, c3 = st.columns(3)
        with c1: q_obra = st.number_input(f"Quantidade ({it['u']}):", min_value=0.01, value=1.0)
        with c2: jor = st.number_input("Jornada (h/dia):", min_value=1.0, value=8.0)
        with c3: st.metric("VALOR TOTAL ITEM", f"R$ {q_obra * it['p']:,.2f}")

        if it['comp']:
            df_c = pd.DataFrame(it['comp'])
            mo = df_c[(df_c['u'].str.upper() == 'H') & (df_c['d'].str.upper().str.contains('MAO-DE-OBRA', na=False))].copy()
            
            if not mo.empty:
                st.write("### 👷 Cronograma de Execução")
                pzs = []
                cols = st.columns(len(mo))
                for idx, (i, r) in enumerate(mo.iterrows()):
                    with cols[idx]:
                        nome_prof = " ".join(str(r['d']).upper().replace('MAO-DE-OBRA DE ', '').split()[:2])
                        n = st.number_input(f"Nº de {nome_prof}:", min_value=1, value=1, key=f"n_{i}")
                        dias = (r['q'] * q_obra) / (jor * n)
                        pzs.append(dias)
                        st.write(f"⏱️ **{dias:.2f} dias**")
                if pzs: st.info(f"📅 **PRAZO ESTIMADO:** {max(pzs):.2f} dias úteis.")
            
            st.write("### 📋 Composição Detalhada")
            df_c['Total'] = df_c['q'] * q_obra * df_c['p']
            st.dataframe(df_c.style.format({'q': '{:.4f}', 'p': 'R$ {:.2f}', 'Total': 'R$ {:.2f}'}), use_container_width=True)
