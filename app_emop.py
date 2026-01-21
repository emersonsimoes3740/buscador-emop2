import pandas as pd
import streamlit as st
from supabase import create_client
import os
import io
import numpy as np
from datetime import datetime
import plotly.express as px

# 1. CONEXÃO E CONFIGURAÇÃO
try:
    url = st.secrets["SUPABASE_URL"]
    key = st.secrets["SUPABASE_KEY"]
    supabase = create_client(url, key)
except:
    st.error("Erro de conexão com as chaves do sistema.")

st.set_page_config(page_title="Gestor de Obras - Célula Engenharia", layout="wide")

if "cesta_itens" not in st.session_state:
    st.session_state.cesta_itens = []

# --- FUNÇÕES DE TRATAMENTO ---

def limpar_valor(valor):
    if pd.isna(valor) or valor == "": return 0.0
    try:
        if isinstance(valor, str):
            valor = valor.replace('R$', '').replace('.', '').replace(',', '.').strip()
        return float(valor)
    except: return 0.0

@st.cache_data
def load_db(path, tipo_base):
    if not os.path.exists(path): return None
    try:
        # Carrega o Excel ignorando as primeiras linhas se for SINAPI (geralmente tem cabeçalho fixo)
        df = pd.read_excel(path)
        
        # AJUSTE DINÂMICO DE COLUNAS
        if tipo_base == "EMOP (RJ)":
            df = df.iloc[:, :7]
            df.columns = ['C', 'D', 'U', 'Q', 'P', 'PC', 'T']
        else:
            # Lógica para SINAPI (Geralmente Código está na col 0, Desc na 1, Unid na 2, Coef na 3 e Preço na 4)
            # Ajustamos para pegar as colunas principais do SINAPI
            df = df.iloc[:, :5] 
            df.columns = ['C', 'D', 'U', 'Q', 'P']
        
        db, pai = [], None
        for _, r in df.iterrows():
            cod = str(r['C']).strip()
            desc = str(r['D']).strip()
            unid = str(r['U']).strip()
            coef = limpar_valor(r['Q'])
            preco = limpar_valor(r['P'])

            # Se o código for igual ao anterior ou vazio, ignoramos
            if cod == "nan" or desc == "nan": continue

            # Lógica de Identificação Pai/Filho
            # No SINAPI e EMOP, o PAI geralmente tem preço mas não tem coeficiente de composição na linha principal
            if (pd.isna(r['Q']) or coef == 0 or coef == 1.0) and unid != "H" and unid != "h":
                pai = {
                    'c': cod, 
                    'd': desc, 
                    'u': unid,
                    'p': preco, 
                    'comp': []
                }
                db.append(pai)
            elif pai:
                pai['comp'].append({
                    'Código': cod, 
                    'Descrição': desc, 
                    'Unidade': unid,
                    'Coeficiente': coef, 
                    'Preço': preco
                })
        return db
    except Exception as e:
        st.error(f"Erro ao processar base {tipo_base}: {e}")
        return None

def calcular_data_final(data_inicio, dias_uteis):
    try:
        inicio_np = np.datetime64(data_inicio)
        dias_int = int(np.ceil(dias_uteis))
        offset = max(0, dias_int - 1)
        fim_np = np.busday_offset(inicio_np, offset, roll='forward')
        return pd.to_datetime(fim_np)
    except: return pd.to_datetime(data_inicio)

# --- LOGIN (Simplificado) ---
if "autenticado" not in st.session_state: st.session_state.autenticado = False
if not st.session_state.autenticado:
    st.title("🏗️ Portal Célula Engenharia")
    token = st.text_input("Token de Acesso:", type="password")
    if st.button("Entrar"):
        st.session_state.autenticado = True
        st.rerun()
    st.stop()

# --- INTERFACE ---
st.sidebar.title("Configurações")
base_escolhida = st.sidebar.radio("Base Atual:", ["EMOP (RJ)", "SINAPI"])

# Define o arquivo correto baseado na escolha
if base_escolhida == "EMOP (RJ)":
    path_base = 'emop 0126.xlsm'
else:
    path_base = 'sinapi_ref.xlsx' # Certifique-se que o nome no GitHub está igual a este

st.title(f"🔍 Planejador - {base_escolhida}")
dados = load_db(path_base, base_escolhida)

if dados:
    lista_opcoes = [f"{i['c']} | {i['d']}" for i in dados]
    selecao = st.selectbox("Pesquise o serviço:", options=[""] + lista_opcoes)
    
    if selecao:
        item = next(i for i in dados if i['c'] == selecao.split(" | ")[0])
        st.subheader(f"📍 {item['c']} - {item['d']}")
        
        c1, c2, c3 = st.columns(3)
        with c1: q_obra = st.number_input(f"Quantidade ({item['u']}):", min_value=0.01, value=1.0)
        with c2: jornada = st.number_input("Jornada (h/dia):", min_value=1.0, value=8.0)
        with c3: st.metric("VALOR TOTAL ITEM", f"R$ {q_obra * item['p']:,.2f}")
        
        prazo_calc = 0.0
        if item['comp']:
            df_comp = pd.DataFrame(item['comp'])
            
            # Filtro de Mão de Obra para Cronograma (Funciona para EMOP e SINAPI)
            mo = df_comp[
                (df_comp['Unidade'].str.upper().str.contains('H', na=False)) |
                (df_comp['Descrição'].str.upper().str.contains('OFICIAL|AJUDANTE|PEDREIRO|SERVENTE|ARMADOR|CARPINTEIRO|PINTOR|ELETRICISTA|ENCANADOR', na=False))
            ].copy()
            
            if not mo.empty:
                st.write("### 👷 Cronograma de Execução")
                prazos_mo = []
                cols = st.columns(min(len(mo), 4))
                
                for idx, (i, r) in enumerate(mo.iterrows()):
                    with cols[idx % 4]:
                        nome_resumo = " ".join(str(r['Descrição']).split()[:2])
                        n_h = st.number_input(f"Nº de {nome_resumo}:", min_value=1, value=1, key=f"n_{idx}")
                        p_serv = (r['Coeficiente'] * q_obra) / (jornada * n_h)
                        prazos_mo.append(p_serv)
                        st.write(f"⏱️ **{p_serv:.2f} dias**")
                
                prazo_calc = max(prazos_mo) if prazos_mo else 0.0
                st.info(f"📅 **Prazo Estimado:** {prazo_calc:.2f} dias úteis.")

            st.write("### 📋 Composição e Insumos")
            df_comp['Subtotal'] = df_comp['Coeficiente'] * q_obra * df_comp['Preço']
            st.dataframe(
                df_comp.style.format({'Coeficiente': '{:.4f}', 'Preço': 'R$ {:.2f}', 'Subtotal': 'R$ {:.2f}'}),
                use_container_width=True, hide_index=True
            )

        st.write("---")
        data_ini = st.date_input("Início deste serviço:", value=datetime.now())

        if st.button("➕ Adicionar ao Planejamento"):
            dt_fim = calcular_data_final(data_ini, prazo_calc)
            st.session_state.cesta_itens.append({
                "codigo": item['c'], "descricao": item['d'], "unid": item['u'], 
                "quantidade": q_obra, "valor_total": q_obra * item['p'],
                "prazo": prazo_calc, "inicio": data_ini, "fim": dt_fim, "base": base_escolhida
            })
            st.toast("Adicionado ao cronograma!")

# --- GANTT ---
if st.session_state.cesta_itens:
    st.divider()
    df_resumo = pd.DataFrame(st.session_state.cesta_itens)
    st.write("### 📊 Gráfico de Gantt")
    fig = px.timeline(df_resumo, x_start="inicio", x_end="fim", y="descricao", color="base")
    fig.update_yaxes(autorange="reversed")
    st.plotly_chart(fig, use_container_width=True)
    
    if st.button("🗑️ Limpar Cronograma"): 
        st.session_state.cesta_itens = []; st.rerun()
