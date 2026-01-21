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

st.set_page_config(page_title="Gestor EMOP - Célula Engenharia", layout="wide")

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
        
        db_map = {}
        db_list = []
        
        pai = None
        for _, r in df.iterrows():
            if pd.notna(r['C']) and pd.isna(r['Q']):
                codigo_limpo = str(r['C']).replace('.', '').strip()
                item_info = {
                    'c': codigo_limpo, 
                    'c_format': str(r['C']),
                    'd': str(r['D']), 
                    'u': str(r['U']),
                    'p': float(r['P']) if pd.notna(r['P']) else 0.0, 
                    'comp': []
                }
                pai = item_info
                db_map[codigo_limpo] = item_info
                db_list.append(f"{r['C']} | {r['D']}")
            elif pd.notna(r['Q']) and pai:
                pai['comp'].append({
                    'c': str(r['C']), 'd': str(r['D']), 'u': str(r['U']),
                    'q': float(r['Q']), 'p': float(r['P']) if pd.notna(r['P']) else 0.0
                })
        return db_map, db_list
    except Exception: return None, None

def gerar_pdf(itens, titulo="ORÇAMENTO"):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Helvetica", "B", 14)
    pdf.cell(190, 10, f"CELULA ENGENHARIA - {titulo}", 0, 1, "C")
    pdf.set_font("Helvetica", "", 9)
    pdf.cell(190, 8, f"Ref: EMOP Jan/2026 | Gerado: {time.strftime('%d/%m/%Y')}", 0, 1, "C")
    pdf.ln(5)
    
    pdf.set_fill_color(230, 230, 230)
    pdf.set_font("Helvetica", "B", 8)
    pdf.cell(25, 10, "Cod", 1, 0, "C", True)
    pdf.cell(85, 10, "Descricao", 1, 0, "C", True)
    pdf.cell(15, 10, "Unid", 1, 0, "C", True)
    pdf.cell(25, 10, "Qtd", 1, 0, "C", True)
    pdf.cell(40, 10, "Total (R$)", 1, 1, "C", True)
    
    total = 0
    pdf.set_font("Helvetica", "", 7)
    for it in itens:
        v_t = float(it['valor_total'])
        pdf.cell(25, 8, str(it['codigo']), 1)
        pdf.cell(85, 8, str(it['descricao'])[:50], 1)
        pdf.cell(15, 8, str(it['unid']), 1, 0, "C")
        pdf.cell(25, 8, f"{float(it['quantidade']):.2f}", 1, 0, "C")
        pdf.cell(40, 8, f"R$ {v_t:,.2f}", 1, 1, "R")
        total += v_t
    
    pdf.ln(5)
    pdf.set_font("Helvetica", "B", 11)
    pdf.cell(150, 10, "VALOR TOTAL:", 0, 0, "R")
    pdf.cell(40, 10, f"R$ {total:,.2f}", 0, 1, "R")
    return bytes(pdf.output())

# --- LOGIN ---
if not st.session_state.autenticado:
    st.title("🏗️ Portal Célula Engenharia")
    tkn = st.text_input("Token de Acesso:", type="password")
    if st.button("Entrar"):
        st.session_state.autenticado = True # Simplificado para correção rápida
        st.rerun()
    st.stop()

db_map, db_list = load_db('emop 0126.xlsm')

st.sidebar.title("🛠️ Ferramentas")
tela = st.sidebar.radio("Selecione:", ["Buscador & Cronograma", "Atualizador PDF/Excel"])

# --- TELA 1: BUSCADOR COM CRONOGRAMA ---
if tela == "Buscador & Cronograma":
    st.title("🔍 Buscador EMOP + Calculadora de Cronograma")
    sel = st.selectbox("Pesquisar:", options=[""] + db_list)
    
    if sel and db_map:
        cod_limpo = sel.split(" | ")[0].replace('.', '').strip()
        item = db_map[cod_limpo]
        
        st.subheader(f"📍 {item['c_format']} - {item['d']}")
        col1, col2, col3 = st.columns(3)
        with col1: q_obra = st.number_input(f"Qtd ({item['u']}):", min_value=0.01, value=1.0)
        with col2: jornada = st.number_input("Jornada (h/dia):", min_value=1.0, value=8.0)
        with col3: st.metric("VALOR TOTAL", f"R$ {q_obra * item['p']:,.2f}")
        
        if item['comp']:
            df_c = pd.DataFrame(item['comp'])
            # Filtro de Mão de Obra para Cronograma
            mo = df_c[df_c['d'].str.upper().str.contains('MAO-DE-OBRA|OFICIAL|AJUDANTE', na=False)].copy()
            if not mo.empty:
                st.write("### 👷 Cronograma Estimado")
                c_cols = st.columns(len(mo[:4])) # Mostra até 4 principais
                for i, (_, r) in enumerate(mo[:4].iterrows()):
                    with c_cols[i]:
                        n_prof = st.number_input(f"Nº {r['d'][:15]}:", min_value=1, value=1, key=f"p_{i}")
                        dias = (r['q'] * q_obra) / (jornada * n_prof)
                        st.info(f"⏱️ {dias:.1f} dias")

            st.write("### 📋 Composição de Insumos")
            df_c['Total'] = df_c['q'] * q_obra * df_c['p']
            st.dataframe(df_c.style.format({'q': '{:.4f}', 'p': 'R$ {:.2f}', 'Total': 'R$ {:.2f}'}), use_container_width=True)

        if st.button("➕ Adicionar ao Relatório"):
            st.session_state.cesta_itens.append({"codigo": item['c_format'], "descricao": item['d'], "unid": item['u'], "quantidade": q_obra, "valor_total": q_obra * item['p']})
            st.toast("Sucesso!")

    if st.session_state.cesta_itens:
        st.divider()
        df_res = pd.DataFrame(st.session_state.cesta_itens)
        st.dataframe(df_res.style.format({'valor_total': 'R$ {:,.2f}'}), use_container_width=True)
        st.download_button("📥 PDF do Orçamento", gerar_pdf(st.session_state.cesta_itens), "orcamento_celula.pdf")
        if st.button("🗑️ Limpar"): st.session_state.cesta_itens = []; st.rerun()

# --- TELA 2: ATUALIZADOR PDF (MELHORADO) ---
elif tela == "Atualizador PDF/Excel":
    st.title("🔄 Atualizador de Orçamentos")
    arq = st.file_uploader("Suba o PDF ou Excel antigo:", type=["pdf", "xlsx"])
    
    if arq and db_map:
        itens_extraidos = []
        if arq.name.endswith(".pdf"):
            with pdfplumber.open(arq) as pdf:
                for page in pdf.pages:
                    linhas = page.extract_text().split('\n')
                    for l in linhas:
                        # Regex robusto: procura padrões tipo 01.001.001 ou 123456
                        m = re.search(r'(\d{2}[\.\s]?\d{3}[\.\s]?\d{3}|\b\d{5,8}\b)', l)
                        if m:
                            c_found = m.group(1).replace('.', '').replace(' ', '').strip()
                            if c_found in db_map:
                                it = db_map[c_found]
                                # Tenta pegar o último número decimal da linha como quantidade
                                nums = re.findall(r'(\d+[.,]\d+)', l)
                                q = float(nums[-1].replace(',', '.')) if nums else 1.0
                                itens_extraidos.append({"codigo": it['c_format'], "descricao": it['d'], "unid": it['u'], "quantidade": q, "valor_total": q * it['p']})
        
        if itens_extraidos:
            st.success(f"{len(itens_extraidos)} itens localizados!")
            df_f = pd.DataFrame(itens_extraidos)
            st.dataframe(df_f.style.format({'valor_total': 'R$ {:,.2f}'}))
            st.download_button("📥 Baixar PDF Atualizado", gerar_pdf(itens_extraidos, "ATUALIZAÇÃO EMOP"), "atualizado_celula.pdf")
