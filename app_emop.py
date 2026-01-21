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

st.set_page_config(page_title="Gestor EMOP - Eng. Emerson Simões", layout="wide")

if "cesta_itens" not in st.session_state:
    st.session_state.cesta_itens = []

# --- FUNÇÕES DE SUPORTE ---
@st.cache_data
def load_db(path):
    if not os.path.exists(path): return None
    try:
        df = pd.read_excel(path)
        if len(df.columns) >= 7:
            df = df.iloc[:, :7]
            df.columns = ['C','D','U','Q','P','PC','T']
        db, pai = [], None
        for _, r in df.iterrows():
            if pd.notna(r['C']) and pd.isna(r['Q']):
                pai = {'c': str(r['C']), 'd': str(r['D']), 'u': str(r['U']),
                       'p': float(r['P']) if pd.notna(r['P']) else 0.0, 'comp': []}
                db.append(pai)
            elif pd.notna(r['Q']) and pai:
                pai['comp'].append({'c': str(r['C']), 'd': str(r['D']), 'u': str(r['U']),
                                    'q': float(r['Q']), 'p': float(r['P']) if pd.notna(r['P']) else 0.0})
        return db
    except Exception: return None

def calcular_data_final_fixa(data_escolhida, dias_uteis):
    try:
        if isinstance(data_escolhida, datetime):
            data_escolhida = data_escolhida.date()
        inicio_np = np.datetime64(data_escolhida)
        dias_int = int(np.ceil(dias_uteis))
        offset = int(max(0, dias_int - 1))
        fim_np = np.busday_offset(inicio_np, offset, roll='forward')
        return pd.to_datetime(fim_np)
    except Exception:
        return pd.to_datetime(data_escolhida)

def gerar_pdf(itens):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Helvetica", "B", 16)
    pdf.cell(190, 10, "CELULA ENGENHARIA - RELATORIO EMOP", 0, 1, "C")
    pdf.set_font("Helvetica", "", 10)
    pdf.cell(190, 10, f"Data: {time.strftime('%d/%m/%Y')} | Ref: EMOP 01/2026", 0, 1, "C")
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
    pdf.cell(150, 10, "VALOR TOTAL DO ORCAMENTO:", 0, 0, "R")
    pdf.cell(40, 10, f"RS {total_geral:,.2f}", 0, 1, "R")
    return bytes(pdf.output())

# --- LOGIN (Simplificado para o script) ---
if "autenticado" not in st.session_state:
    st.session_state.autenticado = False

if not st.session_state.autenticado:
    st.title("🏗️ Portal Célula Engenharia")
    token = st.text_input("Token de Acesso:", type="password")
    if st.button("Entrar"):
        st.session_state.autenticado = True # Lógica simplificada
        st.rerun()
    st.stop()

# --- INTERFACE PRINCIPAL ---
st.title("🔍 Buscador & Planejador EMOP")
dados = load_db('emop 0126.xlsm')

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
            mo = df_comp[(df_comp['u'].str.upper() == 'H') & (df_comp['d'].str.upper().str.contains('MAO-DE-OBRA', na=False))].copy()
            if not mo.empty:
                st.write("### 👷 Cronograma de Execução")
                cols = st.columns(len(mo))
                prazos_mo = []
                for idx, (i, r) in enumerate(mo.iterrows()):
                    with cols[idx]:
                        nome = " ".join(str(r['d']).upper().replace('MAO-DE-OBRA DE ', '').split()[:2])
                        n_h = st.number_input(f"Nº de {nome}:", min_value=1, value=1, key=f"n_{idx}_{item['c']}")
                        p_serv = (float(r['q']) * q_obra) / (jornada * n_h)
                        prazos_mo.append(p_serv)
                        st.write(f"⏱️ **{p_serv:.2f} dias**")
                prazo_calc = max(prazos_mo) if prazos_mo else 0.0

        st.write("---")
        data_inicio_escolhida = st.date_input("Data de Início do Serviço:", value=datetime.now())

        if st.button("➕ Adicionar ao Relatório"):
            dt_end = calcular_data_final_fixa(data_inicio_escolhida, prazo_calc)
            st.session_state.cesta_itens.append({
                "codigo": item['c'], "descricao": item['d'], "unid": item['u'], 
                "quantidade": float(q_obra), "valor_total": float(q_obra * item['p']),
                "prazo_dias": float(prazo_calc), "inicio": data_inicio_escolhida, "fim": dt_end
            })
            st.toast("Adicionado!")

# --- GANTT E EXPORTAÇÃO ---
if st.session_state.cesta_itens:
    st.divider()
    df_resumo = pd.DataFrame(st.session_state.cesta_itens)
    df_resumo['inicio_dt'] = pd.to_datetime(df_resumo['inicio'])
    df_resumo['fim_dt'] = pd.to_datetime(df_resumo['fim'])
    
    st.write("### 📊 Gráfico de Gantt")
    fig = px.timeline(df_resumo, x_start="inicio_dt", x_end="fim_dt", y="descricao", color="codigo",
                      labels={"descricao": "Serviço"}, title="Cronograma Real da Obra")
    fig.update_yaxes(autorange="reversed")
    st.plotly_chart(fig, use_container_width=True)
    
    st.write("#### 📥 Opções de Exportação:")
    col_pdf, col_excel, col_gantt, col_limpar = st.columns(4)
    
    with col_pdf:
        pdf_b = gerar_pdf(st.session_state.cesta_itens)
        st.download_button("📄 Baixar PDF", data=pdf_b, file_name="orcamento.pdf", use_container_width=True)

    with col_excel:
        buf = io.BytesIO()
        df_xl = df_resumo.copy()
        df_xl['inicio'] = df_xl['inicio_dt'].dt.strftime('%d/%m/%Y')
        df_xl['fim'] = df_xl['fim_dt'].dt.strftime('%d/%m/%Y')
        df_xl = df_xl.drop(columns=['inicio_dt', 'fim_dt'])
        with pd.ExcelWriter(buf, engine='openpyxl') as writer:
            df_xl.to_excel(writer, index=False)
        st.download_button("📊 Baixar Excel", data=buf.getvalue(), file_name="cronograma.xlsx", use_container_width=True)

    # NOVO BOTÃO PARA EXPORTAR O GRÁFICO
    with col_gantt:
        html_buffer = io.StringIO()
        fig.write_html(html_buffer, include_plotlyjs='cdn')
        st.download_button(
            label="📈 Baixar Gráfico (HTML)",
            data=html_buffer.getvalue(),
            file_name="grafico_gantt_celula.html",
            mime="text/html",
            use_container_width=True,
            help="Baixa o gráfico interativo que pode ser aberto em qualquer navegador."
        )

    with col_limpar:
        if st.button("🗑️ Limpar Lista", use_container_width=True): 
            st.session_state.cesta_itens = []; st.rerun()
