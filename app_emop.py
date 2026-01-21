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
        db = {}
        for _, r in df.iterrows():
            if pd.notna(r['C']) and pd.isna(r['Q']):
                db[str(r['C'])] = {'d': str(r['D']), 'u': str(r['U']), 'p': float(r['P']) if pd.notna(r['P']) else 0.0}
        return db
    except Exception: return None

def gerar_pdf(itens, titulo="RELATÓRIO DE ORÇAMENTO"):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Helvetica", "B", 14)
    pdf.cell(190, 10, f"CÉLULA ENGENHARIA - {titulo}", 0, 1, "C")
    pdf.set_font("Helvetica", "", 9)
    pdf.cell(190, 8, f"Referência Base: EMOP Janeiro/2026 | Gerado em: {time.strftime('%d/%m/%Y')}", 0, 1, "C")
    pdf.ln(5)
    
    pdf.set_fill_color(230, 230, 230)
    pdf.set_font("Helvetica", "B", 8)
    pdf.cell(20, 10, "Cód", 1, 0, "C", True)
    pdf.cell(90, 10, "Descrição", 1, 0, "C", True)
    pdf.cell(15, 10, "Unid", 1, 0, "C", True)
    pdf.cell(25, 10, "Qtd", 1, 0, "C", True)
    pdf.cell(40, 10, "Total (R$)", 1, 1, "C", True)
    
    total = 0
    pdf.set_font("Helvetica", "", 7)
    for it in itens:
        pdf.cell(20, 8, str(it['codigo']), 1)
        pdf.cell(90, 8, str(it['descricao'])[:50], 1)
        pdf.cell(15, 8, str(it['unid']), 1, 0, "C")
        pdf.cell(25, 8, f"{float(it['quantidade']):.2f}", 1, 0, "C")
        pdf.cell(40, 8, f"R$ {float(it['valor_total']):,.2f}", 1, 1, "R")
        total += float(it['valor_total'])
    
    pdf.ln(5)
    pdf.set_font("Helvetica", "B", 11)
    pdf.cell(150, 10, "TOTAL GERAL ATUALIZADO:", 0, 0, "R")
    pdf.cell(40, 10, f"R$ {total:,.2f}", 0, 1, "R")
    return bytes(pdf.output())

# --- SISTEMA DE ACESSO ---
# (Manter lógica do Supabase e TOKEN_TESTE aqui conforme versões anteriores)
if not st.session_state.autenticado:
    # ... (Login form)
    st.stop()

# --- MENU DE NAVEGAÇÃO ---
st.sidebar.title("🏗️ Menu Principal")
tela = st.sidebar.radio("Escolha a ferramenta:", ["Buscador Individual", "Atualizador de Planilha"])

dados_map = load_db('emop 0126.xlsm')

# --- TELA 1: BUSCADOR INDIVIDUAL (Lógica anterior) ---
if tela == "Buscador Individual":
    st.title("🔍 Buscador EMOP - Jan/2026")
    # ... (Seu código atual de busca e adição à cesta)

# --- TELA 2: ATUALIZADOR DE PLANILHA ---
elif tela == "Atualizador de Planilha":
    st.title("🔄 Atualizador Automático de Orçamentos")
    st.info("Suba um Excel com as colunas 'Código' e 'Quantidade' para atualizar para os preços de Jan/2026.")
    
    arquivo_up = st.file_uploader("Selecione sua planilha antiga (Excel)", type=["xlsx", "xls"])
    
    if arquivo_up and dados_map:
        df_usuario = pd.read_excel(arquivo_up)
        st.write("📋 **Planilha Carregada:**")
        st.dataframe(df_usuario.head())
        
        # Mapeamento de colunas (Usuário deve indicar quais são as colunas de código e quantidade)
        col_cod = st.selectbox("Selecione a coluna do Código:", df_usuario.columns)
        col_qtd = st.selectbox("Selecione a coluna da Quantidade:", df_usuario.columns)
        
        if st.button("🚀 Atualizar Preços para Janeiro/2026"):
            novos_itens = []
            erros = []
            
            for _, row in df_usuario.iterrows():
                cod = str(row[col_cod]).strip()
                qtd = float(row[col_qtd])
                
                if cod in dados_map:
                    info = dados_map[cod]
                    novos_itens.append({
                        "codigo": cod,
                        "descricao": info['d'],
                        "unid": info['u'],
                        "quantidade": qtd,
                        "valor_total": qtd * info['p']
                    })
                else:
                    erros.append(cod)
            
            if novos_itens:
                st.success(f"Sucesso! {len(novos_itens)} itens atualizados.")
                df_final = pd.DataFrame(novos_itens)
                st.dataframe(df_final.style.format({'valor_total': 'R$ {:,.2f}'}))
                
                pdf_bytes = gerar_pdf(novos_itens, titulo="ORÇAMENTO ATUALIZADO")
                st.download_button("📥 Baixar PDF Atualizado", pdf_bytes, "orcamento_atualizado_emop.pdf")
                
                if erros:
                    st.warning(f"Os códigos seguintes não foram encontrados na EMOP 01/2026: {', '.join(erros)}")
            else:
                st.error("Nenhum código da sua planilha foi encontrado na base EMOP atual.")
