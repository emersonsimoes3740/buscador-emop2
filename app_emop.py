import pandas as pd
import streamlit as st
from supabase import create_client
from fpdf import FPDF
import pdfplumber
import os
import time
import re

# 1. CONEXÃO E CONFIGURAÇÃO
url = st.secrets["SUPABASE_URL"]
key = st.secrets["SUPABASE_KEY"]
supabase = create_client(url, key)

st.set_page_config(page_title="Gestor EMOP - Eng. Emerson Simões", layout="wide")

# Inicialização de estados
if "cesta_itens" not in st.session_state: st.session_state.cesta_itens = []
if "autenticado" not in st.session_state: st.session_state.autenticado = False

# --- FUNÇÕES TÉCNICAS ---
@st.cache_data
def load_db(path):
    if not os.path.exists(path): return None, None
    try:
        df = pd.read_excel(path)
        if len(df.columns) >= 7:
            df = df.iloc[:, :7]
            df.columns = ['C','D','U','Q','P','PC','T']
        
        db_map = {} # Dicionário para busca rápida
        db_list = [] # Lista para o selectbox
        
        pai = None
        for _, r in df.iterrows():
            if pd.notna(r['C']) and pd.isna(r['Q']):
                item_info = {
                    'c': str(r['C']).replace('.', '').strip(), 
                    'd': str(r['D']), 
                    'u': str(r['U']),
                    'p': float(r['P']) if pd.notna(r['P']) else 0.0, 
                    'comp': []
                }
                pai = item_info
                db_map[item_info['c']] = item_info
                db_list.append(f"{r['C']} | {r['D']}")
            elif pd.notna(r['Q']) and pai:
                pai['comp'].append({
                    'c': str(r['C']), 'd': str(r['D']), 'u': str(r['U']),
                    'q': float(r['Q']), 'p': float(r['P']) if pd.notna(r['P']) else 0.0
                })
        return db_map, db_list
    except Exception: return None, None

def gerar_pdf(itens, titulo="RELATÓRIO DE ORÇAMENTO"):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Helvetica", "B", 14)
    pdf.cell(190, 10, f"CELULA ENGENHARIA - {titulo}", 0, 1, "C")
    pdf.set_font("Helvetica", "", 9)
    pdf.cell(190, 8, f"Ref: EMOP Jan/2026 | Emitido: {time.strftime('%d/%m/%Y')}", 0, 1, "C")
    pdf.ln(5)
    
    pdf.set_fill_color(230, 230, 230)
    pdf.set_font("Helvetica", "B", 8)
    pdf.cell(20, 10, "Cod", 1, 0, "C", True)
    pdf.cell(90, 10, "Descricao", 1, 0, "C", True)
    pdf.cell(15, 10, "Unid", 1, 0, "C", True)
    pdf.cell(25, 10, "Qtd", 1, 0, "C", True)
    pdf.cell(40, 10, "Total (R$)", 1, 1, "C", True)
    
    total = 0
    pdf.set_font("Helvetica", "", 7)
    for it in itens:
        v_total = float(it['valor_total'])
        pdf.cell(20, 8, str(it['codigo']), 1)
        pdf.cell(90, 8, str(it['descricao'])[:50], 1)
        pdf.cell(15, 8, str(it['unid']), 1, 0, "C")
        pdf.cell(25, 8, f"{float(it['quantidade']):.2f}", 1, 0, "C")
        pdf.cell(40, 8, f"R$ {v_total:,.2f}", 1, 1, "R")
        total += v_total
    
    pdf.ln(5)
    pdf.set_font("Helvetica", "B", 11)
    pdf.cell(150, 10, "TOTAL GERAL ATUALIZADO:", 0, 0, "R")
    pdf.cell(40, 10, f"R$ {total:,.2f}", 0, 1, "R")
    return bytes(pdf.output())

# --- SISTEMA DE LOGIN ---
if not st.session_state.autenticado:
    st.title("🏗️ Portal Célula Engenharia - Eng. Emerson Simões")
    token = st.text_input("Token de Acesso:", type="password")
    if st.button("Acessar Sistema"):
        if token == "TESTE-GRATIS-30MIN":
            st.session_state.update({"autenticado": True, "tipo_acesso": "gratis", "inicio_teste": time.time()})
            st.rerun()
        else:
            res = supabase.table("licencas").select("*").eq("token", token).execute()
            if res.data and not res.data[0]["em_uso"]:
                supabase.table("licencas").update({"em_uso": True}).eq("token", token).execute()
                st.session_state.update({"autenticado": True, "tipo_acesso": "pago", "token_ativo": token})
                st.rerun()
            else: st.error("Token inválido.")
    st.stop()

# --- CARGA DE DADOS ---
db_map, db_list = load_db('emop 0126.xlsm')

# --- NAVEGAÇÃO ---
st.sidebar.title("🛠️ Menu Principal")
tela = st.sidebar.radio("Navegar para:", ["Buscador Individual", "Atualizador Inteligente (PDF/Excel)"])

# TELA 1: BUSCADOR
if tela == "Buscador Individual":
    st.title("🔍 Buscador EMOP - Jan/2026")
    selecao = st.selectbox("Pesquise por código ou descrição:", options=[""] + db_list)
    if selecao and db_map:
        cod_sel = selecao.split(" | ")[0].replace('.', '').strip()
        item = db_map[cod_sel]
        st.subheader(f"📍 {item['c']} - {item['d']}")
        
        c1, c2, c3 = st.columns(3)
        with c1: q_obra = st.number_input(f"Qtd ({item['u']}):", min_value=0.01, value=1.0)
        with c2: jornada = st.number_input("Horas/Dia:", min_value=1.0, value=8.0)
        with c3: st.metric("VALOR TOTAL", f"R$ {q_obra * item['p']:,.2f}")
        
        if st.button("➕ Adicionar ao Orçamento"):
            st.session_state.cesta_itens.append({"codigo": item['c'], "descricao": item['d'], "unid": item['u'], "quantidade": q_obra, "valor_total": q_obra * item['p']})
            st.toast("Adicionado!")

# TELA 2: ATUALIZADOR (EXTRAÇÃO DE PDF)
elif tela == "Atualizador Inteligente (PDF/Excel)":
    st.title("🔄 Atualizador Automático")
    st.write("Extraia códigos de orçamentos antigos e atualize para **Janeiro/2026**.")
    arq = st.file_uploader("Suba seu arquivo (PDF ou Excel)", type=["xlsx", "xls", "pdf"])
    
    if arq and db_map:
        itens_novos = []
        if arq.name.endswith(".pdf"):
            with pdfplumber.open(arq) as pdf:
                for page in pdf.pages:
                    texto = page.extract_text()
                    if texto:
                        for linha in texto.split('\n'):
                            # Regex para identificar códigos EMOP (Ex: 01.001.001 ou 01001001)
                            match = re.search(r'(\d{2}\.\d{3}\.\d{3}|\d{5,10})', linha)
                            if match:
                                cod = match.group(1).replace('.', '').strip()
                                if cod in db_map:
                                    it = db_map[cod]
                                    # Busca número decimal que indique quantidade
                                    qtd_match = re.findall(r'(\d+[.,]\d+)', linha)
                                    q = float(qtd_match[-1].replace(',', '.')) if qtd_match else 1.0
                                    itens_novos.append({"codigo": cod, "descricao": it['d'], "unid": it['u'], "quantidade": q, "valor_total": q * it['p']})
        else:
            df_up = pd.read_excel(arq)
            c_cod = st.selectbox("Coluna Código:", df_up.columns)
            c_qtd = st.selectbox("Coluna Quantidade:", df_up.columns)
            if st.button("🚀 Processar Excel"):
                for _, r in df_up.iterrows():
                    c = str(r[c_cod]).strip().replace('.', '')
                    if c in db_map:
                        it = db_map[c]; q = float(r[c_qtd])
                        itens_novos.append({"codigo": c, "descricao": it['d'], "unid": it['u'], "quantidade": q, "valor_total": q * it['p']})

        if itens_novos:
            st.success(f"{len(itens_novos)} itens identificados e atualizados!")
            df_final = pd.DataFrame(itens_novos)
            st.dataframe(df_final.style.format({'valor_total': 'R$ {:,.2f}'}))
            st.download_button("📥 Baixar PDF Atualizado", gerar_pdf(itens_novos, "ORÇAMENTO REESTRUTURADO"), "atualizado_emop.pdf")

if st.sidebar.button("Encerrar Sessão"):
    if st.session_state.get("token_ativo"):
        supabase.table("licencas").update({"em_uso": False}).eq("token", st.session_state.token_ativo).execute()
    st.session_state.autenticado = False; st.rerun()
