import pandas as pd
import streamlit as st
from supabase import create_client
from fpdf import FPDF
import os
import time
import io
import numpy as np
from datetime import datetime
import plotly.express as px

# 1. CONEXÃO E CONFIGURAÇÃO (SUPABASE)
url = st.secrets["SUPABASE_URL"]
key = st.secrets["SUPABASE_KEY"]
supabase = create_client(url, key)

st.set_page_config(page_title="Gestor Célula Engenharia - Emerson Simões", layout="wide")

if "cesta_itens" not in st.session_state:
    st.session_state.cesta_itens = []

# --- FUNÇÕES DE SUPORTE ---
def limpar_valor(valor):
    """Trata strings brasileiras (ex: 6,23) para conversão em float."""
    if pd.isna(valor) or valor == "": return 0.0
    try:
        if isinstance(valor, str):
            valor = valor.replace('R$', '').replace('.', '').replace(',', '.').strip()
        return float(valor)
    except: return 0.0

@st.cache_data
def load_db(path):
    if not os.path.exists(path): return None
    try:
        df = pd.read_excel(path)
        df.columns = [str(c).strip() for c in df.columns]
        db, pai = [], None

        if "emop" in path.lower():
            for _, r in df.iterrows():
                cod = str(r.iloc[0]).strip()
                # Item PAI na EMOP (Coluna de coeficiente vazia)
                if pd.isna(r.iloc[3]) or r.iloc[3] == 0:
                    pai = {'c': cod, 'd': str(r.iloc[1]).strip(), 'u': str(r.iloc[2]).strip(),
                           'p': limpar_valor(r.iloc[4]), 'comp': []}
                    db.append(pai)
                elif pai:
                    pai['comp'].append({'Código': cod, 'Descrição do Item': str(r.iloc[1]).strip(),
                                        'Unidade': str(r.iloc[2]).strip(), 'Coeficiente': limpar_valor(r.iloc[3]),
                                        'Custo Hipotético': limpar_valor(r.iloc[4])})
        else: # SINAPI
            for _, r in df.iterrows():
                cod = str(r['Código']).strip()
                if pd.isna(r['Coeficiente']) or r['Coeficiente'] == 0:
                    pai = {'c': cod, 'd': str(r['Descrição do Item']), 'u': str(r['Unidade']),
                           'p': limpar_valor(r['Custo Hipotético']), 'comp': []}
                    db.append(pai)
                elif pai:
                    pai['comp'].append({'Código': cod, 'Descrição do Item': str(r['Descrição do Item']),
                                       'Unidade': str(r['Unidade']), 'Coeficiente': limpar_valor(r['Coeficiente']),
                                       'Custo Hipotético': limpar_valor(r['Custo Hipotético'])})
        return db
    except Exception as e:
        st.error(f"Erro no banco: {e}")
        return None

def calcular_data_final(data_inicio, dias_uteis):
    try:
        inicio_np = np.datetime64(data_inicio)
        fim_np = np.busday_offset(inicio_np, int(np.ceil(dias_uteis)), roll='forward')
        return pd.to_datetime(fim_np)
    except: return pd.to_datetime(data_inicio)

# --- LOGIN ---
if "autenticado" not in st.session_state: st.session_state.autenticado = False
if not st.session_state.autenticado:
    st.title("🏗️ Portal Célula Engenharia")
    token = st.text_input("Token de Acesso:", type="password")
    if st.button("Entrar"):
        st.session_state.autenticado = True
        st.rerun()
    st.stop()

# --- INTERFACE ---
st.sidebar.title("Bases de Dados")
base_escolhida = st.sidebar.radio("Selecione:", ["EMOP (RJ)", "SINAPI (Nacional)"])
path_base = 'emop 0126.xlsm' if base_escolhida == "EMOP (RJ)" else 'sinapi_ref.xlsx'

st.title(f"🔍 Planejador - {base_escolhida}")
dados = load_db(path_base)

if dados:
    lista_opcoes = [f"{i['c']} | {i['d']}" for i in dados]
    selecao = st.selectbox("Pesquise por serviço:", options=[""] + lista_opcoes)
    
    if selecao:
        item = next(i for i in dados if i['c'] == selecao.split(" | ")[0])
        st.subheader(f"📍 {item['c']} - {item['d']}")
        
        c1, c2, c3 = st.columns(3)
        with c1: q_obra = st.number_input(f"Quantidade ({item['u']}):", min_value=0.01, value=1.0)
        with c2: jornada = st.number_input("Jornada (h/dia):", min_value=1.0, value=8.0)
        with c3: st.metric("VALOR TOTAL", f"R$ {q_obra * item['p']:,.2f}")
        
        prazo_calc = 0.0
        if item['comp']:
            df_comp = pd.DataFrame(item['comp'])
            # Filtro de cronograma híbrido
            termos_mo = 'MAO-DE-OBRA|OFICIAL|AJUDANTE|PEDREIRO|SERVENTE|OPERADOR|ENCANADOR|ELETRICISTA'
            mo = df_comp[(df_comp['Unidade'].str.upper().str.contains('H|HORA', na=False)) | 
                         (df_comp['Descrição do Item'].str.upper().str.contains(termos_mo, na=False))].copy()
            
            if not mo.empty:
                st.write("### 👷 Cronograma Estimado")
                cols = st.columns(min(len(mo), 3))
                prazos_lista = []
                for idx, (i, r) in enumerate(mo.iterrows()):
                    with cols[idx % 3]:
                        n_p = st.number_input(f"{str(r['Descrição do Item'])[:20]}:", min_value=1, value=1, key=f"n_{idx}_{item['c']}")
                        p = (float(r['Coeficiente']) * q_obra) / (jornada * n_p)
                        prazos_lista.append(p)
                        st.write(f"⏱️ {p:.2f} dias")
                prazo_calc = max(prazos_lista) if prazos_lista else 0.0

            st.write("### 📋 Insumos")
            df_comp['Total'] = df_comp['Coeficiente'] * q_obra * df_comp['Custo Hipotético']
            st.dataframe(df_comp.style.format({'Coeficiente': '{:.4f}', 'Custo Hipotético': 'R$ {:.2f}', 'Total': 'R$ {:.2f}'}), use_container_width=True)

        st.divider()
        data_ini = st.date_input("Início do Serviço:", value=datetime.now())

        if st.button("➕ Adicionar ao Projeto"):
            dt_fim = calcular_data_final(data_ini, prazo_calc)
            st.session_state.cesta_itens.append({
                "codigo": item['c'], "descricao": item['d'], "unid": item['u'], 
                "quantidade": q_obra, "valor_total": q_obra * item['p'],
                "prazo": prazo_calc, "inicio": data_ini, "fim": dt_fim, "base": base_escolhida
            })
            st.toast("Item adicionado!")

# --- GANTT E EXPORTAÇÃO ---
if st.session_state.cesta_itens:
    st.divider()
    df_resumo = pd.DataFrame(st.session_state.cesta_itens)
    st.write("### 📊 Gráfico de Gantt")
    fig = px.timeline(df_resumo, x_start="inicio", x_end="fim", y="descricao", color="base")
    fig.update_yaxes(autorange="reversed")
    st.plotly_chart(fig, use_container_width=True)
    
    if st.button("🗑️ Limpar Tudo"): 
        st.session_state.cesta_itens = []; st.rerun()
