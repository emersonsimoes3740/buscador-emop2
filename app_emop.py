import pandas as pd
import streamlit as st
from supabase import create_client
from fpdf import FPDF
import os
import time

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
    if not os.path.exists(path): return None
    try:
        df = pd.read_excel(path)
        if len(df.columns) >= 7:
            df = df.iloc[:, :7]
            df.columns = ['C','D','U','Q','P','PC','T']
        
        db_map = {} # Dicionário para busca por código
        db_list = [] # Lista para o Selectbox
        
        pai = None
        for _, r in df.iterrows():
            if pd.notna(r['C']) and pd.isna(r['Q']):
                item_info = {
                    'c': str(r['C']), 
                    'd': str(r['D']), 
                    'u': str(r['U']),
                    'p': float(r['P']) if pd.notna(r['P']) else 0.0, 
                    'comp': []
                }
                pai = item_info
                db_map[str(r['C'])] = item_info
                db_list.append(f"{r['C']} | {r['D']}")
            elif pd.notna(r['Q']) and pai:
                pai['comp'].append({
                    'c': str(r['C']), 'd': str(r['D']), 'u': str(r['U']),
                    'q': float(r['Q']), 'p': float(r['P']) if pd.notna(r['P']) else 0.0
                })
        return db_map, db_list
    except Exception as e:
        st.error(f"Erro ao carregar banco: {e}")
        return None, None

def gerar_pdf(itens, titulo="RELATÓRIO DE ORÇAMENTO"):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Helvetica", "B", 14)
    pdf.cell(190, 10, f"CELULA ENGENHARIA - {titulo}", 0, 1, "C")
    pdf.set_font("Helvetica", "", 9)
    pdf.cell(190, 8, f"Ref: EMOP Janeiro/2026 | Emitido: {time.strftime('%d/%m/%Y')}", 0, 1, "C")
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
    pdf.cell(150, 10, "TOTAL GERAL:", 0, 0, "R")
    pdf.cell(40, 10, f"R$ {total:,.2f}", 0, 1, "R")
    return bytes(pdf.output())

# --- LOGIN --- (Simplificado para o exemplo)
if not st.session_state.autenticado:
    st.title("🏗️ Portal Célula Engenharia")
    token = st.text_input("Token:", type="password")
    if st.button("Entrar"):
        st.session_state.autenticado = True
        st.rerun()
    st.stop()

# --- CARREGAMENTO DE DADOS ---
db_map, db_list = load_db('emop 0126.xlsm')

# --- NAVEGAÇÃO ---
st.sidebar.title("🛠️ Menu Célula Eng.")
tela = st.sidebar.radio("Selecione:", ["Buscador Individual", "Atualizador de Planilha"])

# --- TELA 1: BUSCADOR INDIVIDUAL ---
if tela == "Buscador Individual":
    st.title("🔍 Buscador EMOP - Jan/2026")
    
    selecao = st.selectbox("Pesquise serviço:", options=[""] + db_list)
    
    if selecao and db_map:
        cod_sel = selecao.split(" | ")[0]
        item = db_map[cod_sel]
        
        st.subheader(f"📍 {item['c']} - {item['d']}")
        c1, c2, c3 = st.columns(3)
        with c1: q_obra = st.number_input(f"Qtd ({item['u']}):", min_value=0.01, value=1.0)
        with c2: jornada = st.number_input("Horas/Dia:", min_value=1.0, value=8.0)
        with c3: st.metric("VALOR TOTAL", f"R$ {q_obra * item['p']:,.2f}")
        
        if item['comp']:
            df_comp = pd.DataFrame(item['comp'])
            st.write("### 📋 Composição e Insumos")
            df_comp['Total'] = df_comp['q'] * q_obra * df_comp['p']
            st.dataframe(df_comp.style.format({'q': '{:.4f}', 'p': 'R$ {:.2f}', 'Total': 'R$ {:.2f}'}), use_container_width=True)

        if st.button("➕ Adicionar ao Orçamento"):
            st.session_state.cesta_itens.append({
                "codigo": item['c'], "descricao": item['d'], "unid": item['u'], 
                "quantidade": q_obra, "valor_total": q_obra * item['p']
            })
            st.toast("Adicionado!")

    if st.session_state.cesta_itens:
        st.divider()
        st.write("### 📋 Resumo")
        df_res = pd.DataFrame(st.session_state.cesta_itens)
        st.dataframe(df_res.style.format({'valor_total': 'R$ {:,.2f}'}), use_container_width=True)
        
        col1, col2 = st.columns(2)
        with col1:
            pdf_b = gerar_pdf(st.session_state.cesta_itens)
            st.download_button("📥 Baixar PDF", pdf_b, "orcamento.pdf")
        with col2:
            if st.button("🗑️ Limpar Tudo"): st.session_state.cesta_itens = []; st.rerun()

# --- TELA 2: ATUALIZADOR DE PLANILHA ---
elif tela == "Atualizador de Planilha":
    st.title("🔄 Atualizar Orçamento Antigo")
    st.info("Suba um Excel com colunas 'Código' e 'Quantidade'.")
    
    arq = st.file_uploader("Upload Excel", type=["xlsx", "xls"])
    if arq and db_map:
        df_up = pd.read_excel(arq)
        c_cod = st.selectbox("Coluna do Código:", df_up.columns)
        c_qtd = st.selectbox("Coluna da Quantidade:", df_up.columns)
        
        if st.button("🚀 Atualizar para Janeiro/2026"):
            novos = []
            for _, row in df_up.iterrows():
                c = str(row[c_cod]).strip()
                if c in db_map:
                    it = db_map[c]
                    q = float(row[c_qtd])
                    novos.append({
                        "codigo": c, "descricao": it['d'], "unid": it['u'],
                        "quantidade": q, "valor_total": q * it['p']
                    })
            
            if novos:
                st.success(f"{len(novos)} itens processados!")
                st.dataframe(pd.DataFrame(novos).style.format({'valor_total': 'R$ {:,.2f}'}))
                st.download_button("📥 Baixar PDF Atualizado", gerar_pdf(novos, "ORÇAMENTO ATUALIZADO"), "atualizado.pdf")
