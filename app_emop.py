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
        
        # AJUSTE EMOP: Forçamos os nomes das colunas por posição para evitar erros de cabeçalho
        if "emop" in path.lower():
            if len(df.columns) >= 7:
                df = df.iloc[:, :7]
                df.columns = ['Código', 'Descrição do Item', 'Unidade', 'Coeficiente', 'Custo Hipotético', 'PC', 'T']
        
        # Limpeza de nomes de colunas
        df.columns = [str(c).strip() for c in df.columns]
        
        # Tratamento de números para evitar erro de string/float (ex: 6,23 -> 6.23)
        df['Custo Hipotético'] = df['Custo Hipotético'].apply(limpar_valor)
        df['Coeficiente'] = df['Coeficiente'].apply(limpar_valor)
        
        db, pai = [], None
        for _, r in df.iterrows():
            cod = str(r['Código']).strip()
            # Identifica item PAI (Serviço) - Coeficiente é 0 ou Vazio (NaN)
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

st.title(f"🔍 Plane
