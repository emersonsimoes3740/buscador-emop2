import pandas as pd
import streamlit as st
from supabase import create_client
from fpdf import FPDF
import os
import time

# 1. CONEXÃO E SEGURANÇA
url = st.secrets["SUPABASE_URL"]
key = st.secrets["SUPABASE_KEY"]
supabase = create_client(url, key)

st.set_page_config(page_title="Gestor EMOP - Eng. Emerson Simões", layout="wide")

# Inicializa a cesta de itens se não existir
if "cesta_itens" not in st.session_state:
    st.session_state.cesta_itens = []

# --- SISTEMA DE ACESSO (Omitido aqui por brevidade, manter o anterior) ---

# 2. FUNÇÃO PARA GERAR PDF
def gerar_pdf(itens):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", "B", 16)
    pdf.cell(190, 10, "CÉLULA ENGENHARIA - RELATÓRIO EMOP", 0, 1, "C")
    pdf.set_font("Arial", "", 10)
    pdf.cell(190, 10, f"Data: {time.strftime('%d/%m/%Y')} | Ref: EMOP 01/2026", 0, 1, "C")
    pdf.ln(10)
    
    # Cabeçalho da Tabela
    pdf.set_fill_color(200, 200, 200)
    pdf.cell(30, 10, "Código", 1, 0, "C", True)
    pdf.cell(100, 10, "Descrição", 1, 0, "C", True)
    pdf.cell(20, 10, "Unid", 1, 0, "C", True)
    pdf.cell(40, 10, "Total (R$)", 1, 1, "C", True)
    
    total_geral = 0
    for it in itens:
        pdf.cell(30, 10, it['codigo'], 1)
        pdf.cell(100, 10, it['descricao'][:50], 1)
        pdf.cell(20, 10, it['unid'], 1, 0, "C")
        pdf.cell(40, 10, f"{it['valor_total']:,.2f}", 1, 1, "R")
        total_geral += it['valor_total']
    
    pdf.ln(5)
    pdf.set_font("Arial", "B", 12)
    pdf.cell(150, 10, "VALOR TOTAL DO ORÇAMENTO:", 0, 0, "R")
    pdf.cell(40, 10, f"R$ {total_geral:,.2f}", 0, 1, "R")
    
    return pdf.output(dest="S").encode("latin-1")

# --- BUSCADOR ---
# (Manter função load_db e carregamento de dados aqui)

st.title("🔍 Buscador EMOP - Jan/2026")
dados = load_db('emop 0126.xlsm')

if dados:
    lista = [f"{i['c']} | {i['d']}" for i in dados]
    sel = st.selectbox("Selecione o serviço:", options=[""] + lista)
    
    if sel:
        it = next(i for i in dados if i['c'] == sel.split(" | ")[0])
        st.subheader(f"📍 {it['c']} - {it['d']}")
        
        q_obra = st.number_input(f"Quantidade ({it['u']}):", min_value=0.01, value=1.0)
        v_total = q_obra * it['p']
        
        # BOTÃO PARA ADICIONAR À CESTA
        if st.button("➕ Adicionar ao Relatório"):
            novo_item = {
                "codigo": it['c'],
                "descricao": it['d'],
                "unid": it['u'],
                "valor_total": v_total
            }
            st.session_state.cesta_itens.append(novo_item)
            st.success("Item adicionado à sua lista!")

# --- SEÇÃO DO RELATÓRIO (MOSTRA O QUE FOI PESQUISADO) ---
if st.session_state.cesta_itens:
    st.divider()
    st.header("📋 Seu Orçamento Atual")
    df_cesta = pd.DataFrame(st.session_state.cesta_itens)
    st.table(df_cesta)
    
    col_pdf, col_limpar = st.columns(2)
    
    with col_pdf:
        pdf_data = gerar_pdf(st.session_state.cesta_itens)
        st.download_button(
            label="📥 Baixar Orçamento em PDF",
            data=pdf_data,
            file_name="orcamento_celula_engenharia.pdf",
            mime="application/pdf"
        )
        
    with col_limpar:
        if st.button("🗑️ Limpar Lista"):
            st.session_state.cesta_itens = []
            st.rerun()
