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
                codigo_limpo = str(r['C']).replace('.', '').replace('-', '').replace(' ', '').strip()
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

# --- LOGIN (Simplificado) ---
if not st.session_state.autenticado:
    st.title("🏗️ Portal Célula Engenharia")
    if st.button("Acessar Sistema"):
        st.session_state.autenticado = True
        st.rerun()
    st.stop()

db_map, db_list = load_db('emop 0126.xlsm')

st.sidebar.title("🛠️ Menu")
tela = st.sidebar.radio("Selecione:", ["Buscador & Cronograma", "Atualizador Inteligente"])

# --- TELA 1: BUSCADOR & CRONOGRAMA ---
if tela == "Buscador & Cronograma":
    st.title("🔍 Buscador EMOP + Cronograma")
    sel = st.selectbox("Pesquisar Serviço:", options=[""] + db_list)
    
    if sel and db_map:
        cod_limpo = sel.split(" | ")[0].replace('.', '').replace('-', '').replace(' ', '').strip()
        item = db_map[cod_limpo]
        
        st.subheader(f"📍 {item['c_format']} - {item['d']}")
        c1, c2, c3 = st.columns(3)
        with c1: q_obra = st.number_input(f"Qtd ({item['u']}):", min_value=0.01, value=1.0)
        with c2: jornada = st.number_input("Jornada (h/dia):", min_value=1.0, value=8.0)
        with c3: st.metric("VALOR TOTAL", f"R$ {q_obra * item['p']:,.2f}")
        
        if item['comp']:
            df_c = pd.DataFrame(item['comp'])
            # Filtro refinado para Mão de Obra
            mo = df_c[df_c['u'].str.upper().isin(['H', 'HORA'])].copy()
            if not mo.empty:
                st.write("### 👷 Calculadora de Prazo")
                c_cols = st.columns(len(mo[:4]))
                for i, (_, r) in enumerate(mo[:4].iterrows()):
                    with c_cols[i]:
                        # Exibe o nome da Mão de Obra limpando o texto da EMOP
                        nome_limpo = r['d'].replace('MAO-DE-OBRA DE ', '').replace('ENCARGOS COMPLEMENTARES', '').split(' - ')[0][:15]
                        n_prof = st.number_input(f"Nº de {nome_limpo}:", min_value=1, value=1, key=f"p_{i}")
                        dias = (r['q'] * q_obra) / (jornada * n_prof)
                        st.info(f"⏱️ {dias:.1f} dias")

            st.write("### 📋 Composição Detalhada")
            df_c['Total'] = df_c['q'] * q_obra * df_c['p']
            st.dataframe(df_c.style.format({'q': '{:.4f}', 'p': 'R$ {:.2f}', 'Total': 'R$ {:.2f}'}), use_container_width=True)

        if st.button("➕ Adicionar ao Relatório"):
            st.session_state.cesta_itens.append({"codigo": item['c_format'], "descricao": item['d'], "unid": item['u'], "quantidade": q_obra, "valor_total": q_obra * item['p']})
            st.toast("Item salvo!")

    if st.session_state.cesta_itens:
        st.divider()
        st.write("### 📋 Resumo do Orçamento")
        df_res = pd.DataFrame(st.session_state.cesta_itens)
        st.dataframe(df_res.style.format({'valor_total': 'R$ {:,.2f}'}), use_container_width=True)
        st.download_button("📥 Baixar PDF Célula Engenharia", gerar_pdf(st.session_state.cesta_itens), "orcamento_emop.pdf")
        if st.button("🗑️ Limpar Lista"): st.session_state.cesta_itens = []; st.rerun()

# --- TELA 2: ATUALIZADOR INTELIGENTE (PDF FIX) ---
elif tela == "Atualizador Inteligente":
    st.title("🔄 Atualizador Automático (PDF / Excel)")
    st.info("O sistema buscará códigos EMOP no arquivo e atualizará para os preços de Jan/2026.")
    
    arq = st.file_uploader("Arraste o orçamento antigo aqui:", type=["pdf", "xlsx", "xls"])
    
    if arq and db_map:
        itens_extraidos = []
        
        if st.button("🚀 Iniciar Processamento Inteligente"):
            if arq.name.endswith(".pdf"):
                with pdfplumber.open(arq) as pdf:
                    for page in pdf.pages:
                        texto = page.extract_text()
                        if texto:
                            for linha in texto.split('\n'):
                                # Regex mais flexível: pega códigos com pontos, espaços ou traços
                                # Ex: 01.002.003 ou 01 002 003 ou 01002003
                                match = re.search(r'(\d{2}[\.\s-]?\d{3}[\.\s-]?\d{3})', linha)
                                if match:
                                    c_encontrado = match.group(1).replace('.','').replace('-','').replace(' ','').strip()
                                    if c_encontrado in db_map:
                                        it = db_map[c_encontrado]
                                        # Pega o último número da linha (geralmente a quantidade)
                                        numeros = re.findall(r'(\d+[.,]\d+)', linha)
                                        q = float(numeros[-1].replace(',', '.')) if numeros else 1.0
                                        itens_extraidos.append({"codigo": it['c_format'], "descricao": it['d'], "unid": it['u'], "quantidade": q, "valor_total": q * it['p']})
            else:
                df_up = pd.read_excel(arq)
                # Tenta achar colunas que pareçam código e quantidade automaticamente
                c_cod = [c for c in df_up.columns if 'cod' in str(c).lower()][0] if any('cod' in str(c).lower() for c in df_up.columns) else df_up.columns[0]
                c_qtd = [c for c in df_up.columns if 'qtd' in str(c).lower() or 'quant' in str(c).lower()][0] if any('qtd' in str(c).lower() for c in df_up.columns) else df_up.columns[1]
                
                for _, r in df_up.iterrows():
                    c = str(r[c_cod]).replace('.','').replace('-','').replace(' ','').strip()
                    if c in db_map:
                        it = db_map[c]; q = float(r[c_qtd])
                        itens_extraidos.append({"codigo": it['c_format'], "descricao": it['d'], "unid": it['u'], "quantidade": q, "valor_total": q * it['p']})

            if itens_extraidos:
                st.success(f"Encontramos {len(itens_extraidos)} serviços compatíveis!")
                df_f = pd.DataFrame(itens_extraidos)
                st.dataframe(df_f.style.format({'valor_total': 'R$ {:,.2f}'}), use_container_width=True)
                st.download_button("📥 Baixar PDF Atualizado", gerar_pdf(itens_extraidos, "ATUALIZAÇÃO DE PREÇOS"), "atualizado_celula.pdf")
            else:
                st.error("Nenhum código EMOP foi reconhecido no arquivo. Verifique se o PDF possui texto selecionável.")
