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

# --- FUNÇÕES DE SUPORTE ---
@st.cache_data
def load_db(path):
    if not os.path.exists(path): return None
    try:
        # Lê o Excel (Padrão formatado: Código, Descrição do Item, Unidade, Coeficiente, Custo Hipotético)
        df = pd.read_excel(path)
        
        db, pai = [], None
        for _, r in df.iterrows():
            # Identifica o item PAI (Serviço) pela ausência de Coeficiente
            if pd.isna(r['Coeficiente']):
                pai = {
                    'c': str(r['Código']), 
                    'd': str(r['Descrição do Item']), 
                    'u': str(r['Unidade']),
                    'p': float(r['Custo Hipotético']) if pd.notna(r['Custo Hipotético']) else 0.0, 
                    'comp': []
                }
                db.append(pai)
            # Identifica o item FILHO (Insumo) pela presença de Coeficiente
            elif pd.notna(r['Coeficiente']) and pai:
                pai['comp'].append({
                    'Código': str(r['Código']), 
                    'Descrição do Item': str(r['Descrição do Item']), 
                    'Unidade': str(r['Unidade']),
                    'Coeficiente': float(r['Coeficiente']), 
                    'Custo Hipotético': float(r['Custo Hipotético']) if pd.notna(r['Custo Hipotético']) else 0.0
                })
        return db
    except Exception as e:
        st.error(f"Erro ao carregar base {path}: {e}")
        return None

def calcular_data_final_fixa(data_escolhida, dias_uteis):
    try:
        if isinstance(data_escolhida, datetime): data_escolhida = data_escolhida.date()
        inicio_np = np.datetime64(data_escolhida)
        dias_int = int(np.ceil(dias_uteis))
        offset = int(max(0, dias_int - 1))
        fim_np = np.busday_offset(inicio_np, offset, roll='forward')
        return pd.to_datetime(fim_np)
    except Exception: return pd.to_datetime(data_escolhida)

def gerar_pdf(itens):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Helvetica", "B", 16)
    pdf.cell(190, 10, "CELULA ENGENHARIA - RELATORIO TECNICO", 0, 1, "C")
    pdf.set_font("Helvetica", "", 10)
    pdf.cell(190, 10, f"Data: {time.strftime('%d/%m/%Y')} | Ref: Orcamento Multi-Base", 0, 1, "C")
    pdf.ln(10)
    
    pdf.set_fill_color(220, 220, 220)
    pdf.set_font("Helvetica", "B", 9)
    pdf.cell(25, 10, "Codigo", 1, 0, "C", True)
    pdf.cell(85, 10, "Descricao", 1, 0, "C", True)
    pdf.cell(15, 10, "Unid", 1, 0, "C", True)
    pdf.cell(25, 10, "Qtd", 1, 0, "C", True)
    pdf.cell(40, 10, "Total (RS)", 1, 1, "C", True)
    
    total_geral = 0
    pdf.set_font("Helvetica", "", 8)
    for it in itens:
        v_total = float(it.get('valor_total', 0))
        pdf.cell(25, 10, str(it.get('codigo', '')), 1)
        pdf.cell(85, 10, str(it.get('descricao', ''))[:45], 1)
        pdf.cell(15, 10, str(it.get('unid', '')), 1, 0, "C")
        pdf.cell(25, 10, f"{it.get('quantidade', 0):.2f}", 1, 0, "C")
        pdf.cell(40, 10, f"RS {v_total:,.2f}", 1, 1, "R")
        total_geral += v_total
        
    pdf.ln(5)
    pdf.set_font("Helvetica", "B", 12)
    pdf.cell(150, 10, "VALOR TOTAL:", 0, 0, "R")
    pdf.cell(40, 10, f"RS {total_geral:,.2f}", 0, 1, "R")
    return bytes(pdf.output())

# --- LOGIN (Mantido) ---
if "autenticado" not in st.session_state: st.session_state.autenticado = False
if not st.session_state.autenticado:
    st.title("🏗️ Portal Célula Engenharia")
    token = st.text_input("Token de Acesso:", type="password")
    if st.button("Entrar"):
        st.session_state.autenticado = True
        st.rerun()
    st.stop()

# --- SELEÇÃO DE BASE ---
st.sidebar.title("Configurações")
base_escolhida = st.sidebar.radio("Selecione a Base de Dados:", ["EMOP (RJ)", "SINAPI (Nacional)"])
path_base = 'emop 0126.xlsm' if base_escolhida == "EMOP (RJ)" else 'sinapi_ref.xlsx'

# --- INTERFACE PRINCIPAL ---
st.title(f"🔍 Buscador & Planejador - Base {base_escolhida}")
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
            
            # Cronograma
            mo = df_comp[(df_comp['Unidade'].str.upper() == 'H') & (df_comp['Descrição do Item'].str.upper().str.contains('MAO-DE-OBRA|OFICIAL|AJUDANTE|PEDREIRO|SERVENTE', na=False))].copy()
            if not mo.empty:
                st.write("### 👷 Cronograma de Execução")
                cols = st.columns(min(len(mo), 4))
                prazos_mo = []
                for idx, (i, r) in enumerate(mo.iterrows()):
                    with cols[idx % 4]:
                        nome = str(r['Descrição do Item']).upper().split()[:2]
                        n_h = st.number_input(f"Nº de {' '.join(nome)}:", min_value=1, value=1, key=f"n_{idx}_{item['c']}")
                        p_serv = (float(r['Coeficiente']) * q_obra) / (jornada * n_h)
                        prazos_mo.append(p_serv)
                        st.write(f"⏱️ **{p_serv:.2f} dias**")
                prazo_calc = max(prazos_mo) if prazos_mo else 0.0

            st.write("### 📋 Composição e Insumos")
            df_comp['Total'] = df_comp['Coeficiente'] * q_obra * df_comp['Custo Hipotético']
            st.dataframe(df_comp.style.format({'Coeficiente': '{:.4f}', 'Custo Hipotético': 'R$ {:.2f}', 'Total': 'R$ {:.2f}'}), use_container_width=True)

        st.write("---")
        data_inicio = st.date_input("Data de Início do Serviço:", value=datetime.now())

        if st.button("➕ Adicionar ao Relatório"):
            dt_end = calcular_data_final_fixa(data_inicio, prazo_calc)
            st.session_state.cesta_itens.append({
                "codigo": item['c'], "descricao": item['d'], "unid": item['u'], 
                "quantidade": float(q_obra), "valor_total": float(q_obra * item['p']),
                "prazo_dias": float(prazo_calc), "inicio": data_inicio, "fim": dt_end,
                "base": base_escolhida
            })
            st.toast(f"Adicionado da base {base_escolhida}!")

# --- GANTT E EXPORTAÇÃO ---
if st.session_state.cesta_itens:
    st.divider()
    df_resumo = pd.DataFrame(st.session_state.cesta_itens)
    df_resumo['inicio_dt'] = pd.to_datetime(df_resumo['inicio'])
    df_resumo['fim_dt'] = pd.to_datetime(df_resumo['fim'])
    
    st.write("### 📊 Gráfico de Gantt Interativo")
    fig = px.timeline(df_resumo, x_start="inicio_dt", x_end="fim_dt", y="descricao", color="base",
                      labels={"descricao": "Serviço", "base": "Fonte"}, title="Cronograma da Obra (Multi-Base)")
    fig.update_yaxes(autorange="reversed")
    st.plotly_chart(fig, use_container_width=True)
    
    st.write("#### 📥 Opções de Exportação:")
    col_pdf, col_excel, col_gantt, col_limpar = st.columns(4)
    
    with col_pdf:
        pdf_b = gerar_pdf(st.session_state.cesta_itens)
        st.download_button("📄 Baixar PDF", data=pdf_b, file_name="orcamento_celula.pdf", use_container_width=True)

    with col_excel:
        buf = io.BytesIO()
        df_xl = df_resumo.copy()
        df_xl['inicio'] = df_xl['inicio_dt'].dt.strftime('%d/%m/%Y')
        df_xl['fim'] = df_xl['fim_dt'].dt.strftime('%d/%m/%Y')
        df_xl = df_xl.drop(columns=['inicio_dt', 'fim_dt'])
        with pd.ExcelWriter(buf, engine='openpyxl') as writer:
            df_xl.to_excel(writer, index=False)
        st.download_button("📊 Baixar Excel", data=buf.getvalue(), file_name="cronograma_celula.xlsx", use_container_width=True)

    with col_gantt:
        html_buffer = io.StringIO()
        fig.write_html(html_buffer, include_plotlyjs='cdn')
        st.download_button(label="📈 Baixar Gráfico (HTML)", data=html_buffer.getvalue(), 
                           file_name="grafico_gantt.html", mime="text/html", use_container_width=True)

    with col_limpar:
        if st.button("🗑️ Limpar Lista", use_container_width=True): 
            st.session_state.cesta_itens = []; st.rerun()
