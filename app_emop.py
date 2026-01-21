import pandas as pd
import streamlit as st
from supabase import create_client
from fpdf import FPDF
import os
import time

# 1. CONEXÃO E CONFIGURAÇÃO (SUPABASE)
url = st.secrets["SUPABASE_URL"]
key = st.secrets["SUPABASE_KEY"]
supabase = create_client(url, key)

st.set_page_config(page_title="Gestor EMOP - Eng. Emerson Simões", layout="wide")

# Inicializa a cesta de itens se não existir
if "cesta_itens" not in st.session_state:
    st.session_state.cesta_itens = []

# --- FUNÇÃO DE CARGA DE DADOS (Corrigindo o NameError) ---
@st.cache_data
def load_db(path):
    if not os.path.exists(path):
        return None
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
    except Exception as e:
        return None

# --- FUNÇÃO GERADORA DE PDF ---
def gerar_pdf(itens):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", "B", 16)
    pdf.cell(190, 10, "CELULA ENGENHARIA - RELATORIO EMOP", 0, 1, "C")
    pdf.set_font("Arial", "", 10)
    pdf.cell(190, 10, f"Data: {time.strftime('%d/%m/%Y')} | Ref: EMOP 01/2026", 0, 1, "C")
    pdf.ln(10)
    
    # Cabeçalho da Tabela
    pdf.set_fill_color(200, 200, 200)
    pdf.cell(30, 10, "Codigo", 1, 0, "C", True)
    pdf.cell(100, 10, "Descricao", 1, 0, "C", True)
    pdf.cell(20, 10, "Unid", 1, 0, "C", True)
    pdf.cell(40, 10, "Total (R$)", 1, 1, "C", True)
    
    total_geral = 0
    pdf.set_font("Arial", "", 8)
    for it in itens:
        pdf.cell(30, 10, str(it['codigo']), 1)
        pdf.cell(100, 10, str(it['descricao'])[:55], 1)
        pdf.cell(20, 10, str(it['unid']), 1, 0, "C")
        pdf.cell(40, 10, f"{it['valor_total']:,.2f}", 1, 1, "R")
        total_geral += it['valor_total']
    
    pdf.ln(5)
    pdf.set_font("Arial", "B", 12)
    pdf.cell(150, 10, "VALOR TOTAL DO ORCAMENTO:", 0, 0, "R")
    pdf.cell(40, 10, f"R$ {total_geral:,.2f}", 0, 1, "R")
    
    return pdf.output(dest="S")

# --- LÓGICA DE ACESSO ---
if "autenticado" not in st.session_state:
    st.session_state.autenticado = False

if not st.session_state.autenticado:
    st.title("🏗️ Portal Célula Engenharia")
    token = st.text_input("Insira seu Token ou Cupom de Teste:", type="password")
    TOKEN_TESTE = "TESTE-GRATIS-30MIN"
    
    if st.button("Acessar"):
        if token == TOKEN_TESTE:
            if "inicio_teste" not in st.session_state: st.session_state.inicio_teste = time.time()
            st.session_state.autenticado, st.session_state.tipo_acesso = True, "gratis"
            st.rerun()
        else:
            res = supabase.table("licencas").select("*").eq("token", token).execute()
            if res.data and not res.data[0]["em_uso"]:
                supabase.table("licencas").update({"em_uso": True}).eq("token", token).execute()
                st.session_state.autenticado, st.session_state.tipo_acesso, st.session_state.token_ativo = True, "pago", token
                st.rerun()
            else: st.error("Token inválido ou em uso.")
    st.stop()

# Logout e Trava de Tempo
if st.session_state.get("tipo_acesso") == "gratis":
    restante = 30 - (time.time() - st.session_state.inicio_teste) / 60
    if restante <= 0:
        st.error("Tempo esgotado!"); st.session_state.autenticado = False; st.rerun()
    st.sidebar.warning(f"⏱️ {int(restante)} min restantes")

if st.sidebar.button("Sair"):
    if st.session_state.get("tipo_acesso") == "pago":
        supabase.table("licencas").update({"em_uso": False}).eq("token", st.session_state.token_ativo).execute()
    st.session_state.autenticado = False; st.rerun()

# --- BUSCADOR E INTERFACE ---
st.title("🔍 Buscador EMOP - Jan/2026")
dados = load_db('emop 0126.xlsm')

if dados:
    lista = [f"{i['c']} | {i['d']}" for i in dados]
    sel = st.selectbox("Selecione o serviço:", options=[""] + lista)
    
    if sel:
        it = next(i for i in dados if i['c'] == sel.split(" | ")[0])
        st.subheader(f"📍 {it['c']} - {it['d']}")
        
        c1, c2 = st.columns(2)
        with c1: q_obra = st.number_input(f"Quantidade ({it['u']}):", min_value=0.01, value=1.0)
        with c2: st.metric("VALOR TOTAL", f"R$ {q_obra * it['p']:,.2f}")
        
        if st.button("➕ Adicionar ao Relatório"):
            st.session_state.cesta_itens.append({
                "codigo": it['c'], "descricao": it['d'], "unid": it['u'], "valor_total": q_obra * it['p']
            })
            st.toast("Item adicionado!")

# --- CESTA E EXPORTAÇÃO ---
if st.session_state.cesta_itens:
    st.divider()
    st.write("### 📋 Itens Selecionados")
    st.dataframe(pd.DataFrame(st.session_state.cesta_itens), use_container_width=True)
    
    if st.download_button(
        label="📥 Baixar Orçamento em PDF",
        data=gerar_pdf(st.session_state.cesta_itens),
        file_name="orcamento_celula_engenharia.pdf",
        mime="application/pdf"
    ): st.success("PDF Gerado!")
    
    if st.button("🗑️ Limpar Tudo"):
        st.session_state.cesta_itens = []; st.rerun()
