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

st.set_page_config(page_title="Gestor de Obras - Célula Engenharia", layout="wide")

if "cesta_itens" not in st.session_state:
    st.session_state.cesta_itens = []

# --- FUNÇÕES DE TRATAMENTO ---

def limpar_valor(valor):
    """Converte strings brasileiras (6,23) para float (6.23) limpando resíduos."""
    if pd.isna(valor) or valor == "":
        return 0.0
    try:
        if isinstance(valor, str):
            # Remove R$, pontos de milhar e troca vírgula por ponto decimal
            valor = valor.replace('R$', '').replace('.', '').replace(',', '.').strip()
        return float(valor)
    except:
        return 0.0

@st.cache_data
def load_db(path):
    if not os.path.exists(path): 
        return None
    try:
        # Carregamento inicial
        df = pd.read_excel(path)
        
        # AJUSTE EMOP: Se for EMOP, forçamos os nomes das colunas por posição
        if "emop" in path.lower():
            if len(df.columns) >= 7:
                df = df.iloc[:, :7]
                df.columns = ['Código', 'Descrição do Item', 'Unidade', 'Coeficiente', 'Custo Hipotético', 'PC', 'T']
        
        # Limpeza Universal de cabeçalhos
        df.columns = [str(c).strip() for c in df.columns]
        
        # Tratamento de números para evitar erro de string/float
        df['Custo Hipotético'] = df['Custo Hipotético'].apply(limpar_valor)
        df['Coeficiente'] = df['Coeficiente'].apply(limpar_valor)
        
        db, pai = [], None
        for _, r in df.iterrows():
            cod = str(r['Código']).strip()
            # Identifica item PAI (Serviço) - Coeficiente é 0 ou Vazio
            if pd.isna(r['Coeficiente']) or r['Coeficiente'] == 0:
                pai = {
                    'c': cod, 
                    'd': str(r['Descrição do Item']).strip(), 
                    'u': str(r['Unidade']).strip(),
                    'p': float(r['Custo Hipotético']), 
                    'comp': []
                }
                db.append(pai)
            # Identifica item FILHO (Insumo)
            elif pai:
                pai['comp'].append({
                    'Código': cod, 
                    'Descrição do Item': str(r['Descrição do Item']).strip(), 
                    'Unidade': str(r['Unidade']).strip(),
                    'Coeficiente': float(r['Coeficiente']), 
                    'Custo Hipotético': float(r['Custo Hipotético'])
                })
        return db
    except Exception as e:
        st.error(f"Erro ao processar a base {path}: {e}")
        return None

def calcular_data_final(data_inicio, dias_uteis):
    try:
        if isinstance(data_inicio, datetime): data_inicio = data_inicio.date()
        inicio_np = np.datetime64(data_inicio)
        dias_int = int(np.ceil(dias_uteis))
        offset = int(max(0, dias_int - 1))
        fim_np = np.busday_offset(inicio_np, offset, roll='forward')
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
st.sidebar.title("Configurações de Base")
base_escolhida = st.sidebar.radio("Base Atual:", ["EMOP (RJ)", "SINAPI (Nacional)"])
path_base = 'emop 0126.xlsm' if base_escolhida == "EMOP (RJ)" else 'sinapi_ref.xlsx'

st.title(f"🔍 Planejador - {base_escolhida}")
dados = load_db(path_base)

if dados:
    lista_opcoes = [f"{i['c']} | {i['d']}" for i in dados]
    selecao = st.selectbox("Pesquise o serviço:", options=[""] + lista_opcoes)
    
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
            # Identificação de Mão de Obra para Cronograma
            mo = df_comp[df_comp['Descrição do Item'].str.upper().str.contains('MAO-DE-OBRA|OFICIAL|AJUDANTE|PEDREIRO|SERVENTE|ARMADOR|CARPINTEIRO', na=False)].copy()
            
            if not mo.empty:
                st.write("### 👷 Cronograma Estimado")
                cols = st.columns(min(len(mo), 4))
                prazos_mo = []
                for idx, (i, r) in enumerate(mo.iterrows()):
                    with cols[idx % 4]:
                        nome = str(r['Descrição do Item']).split()[:2]
                        n_h = st.number_input(f"Nº de {' '.join(nome)}:", min_value=1, value=1, key=f"n_{idx}_{item['c']}")
                        p_serv = (float(r['Coeficiente']) * q_obra) / (jornada * n_h)
                        prazos_mo.append(p_serv)
                        st.write(f"⏱️ **{p_serv:.2f} dias**")
                prazo_calc = max(prazos_mo) if prazos_mo else 0.0

            st.write("### 📋 Composição Detalhada")
            df_comp['Total'] = df_comp['Coeficiente'] * q_obra * df_comp['Custo Hipotético']
            st.dataframe(df_comp.style.format({'Coeficiente': '{:.4f}', 'Custo Hipotético': 'R$ {:.2f}', 'Total': 'R$ {:.2f}'}), use_container_width=True)

        st.write("---")
        data_ini = st.date_input("Início deste serviço:", value=datetime.now())

        if st.button("➕ Adicionar ao Cronograma"):
            dt_fim = calcular_data_final(data_ini, prazo_calc)
            st.session_state.cesta_itens.append({
                "codigo": item['c'], "descricao": item['d'], "unid": item['u'], 
                "quantidade": float(q_obra), "valor_total": float(q_obra * item['p']),
                "prazo": float(prazo_calc), "inicio": data_ini, "fim": dt_fim, "base": base_escolhida
            })
            st.toast("Adicionado com sucesso!")

# --- GANTT E EXPORTAÇÃO ---
if st.session_state.cesta_itens:
    st.divider()
    df_resumo = pd.DataFrame(st.session_state.cesta_itens)
    df_resumo['inicio_dt'] = pd.to_datetime(df_resumo['inicio'])
    df_resumo['fim_dt'] = pd.to_datetime(df_resumo['fim'])
    
    st.write("### 📊 Gráfico de Gantt")
    fig = px.timeline(df_resumo, x_start="inicio_dt", x_end="fim_dt", y="descricao", color="base",
                      title="Cronograma de Obra - Célula Engenharia")
    fig.update_yaxes(autorange="reversed")
    st.plotly_chart(fig, use_container_width=True)
    
    col_xl, col_html, col_limpar = st.columns(3)
    with col_xl:
        buf = io.BytesIO()
        with pd.ExcelWriter(buf, engine='openpyxl') as writer:
            df_resumo.drop(columns=['inicio_dt', 'fim_dt']).to_excel(writer, index=False)
        st.download_button("📊 Baixar Excel", data=buf.getvalue(), file_name="cronograma.xlsx", use_container_width=True)
    
    with col_html:
        html_buf = io.StringIO()
        fig.write_html(html_buf, include_plotlyjs='cdn')
        st.download_button("📈 Baixar Gráfico (HTML)", data=html_buf.getvalue(), file_name="gantt.html", use_container_width=True)

    with col_limpar:
        if st.button("🗑️ Limpar Tudo", use_container_width=True): 
            st.session_state.cesta_itens = []; st.rerun()
