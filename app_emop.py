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

def gerar_pdf(itens):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Helvetica", "B", 16)
    pdf.cell(190, 10, "CELULA ENGENHARIA - RELATORIO EMOP", 0, 1, "C")
    pdf.set_font("Helvetica", "", 10)
    pdf.cell(190, 10, f"Data: {time.strftime('%d/%m/%Y')} | Ref: EMOP 01/2026", 0, 1, "C")
    pdf.ln(10)
    
    # Cabeçalho da Tabela - Ajustado para incluir Quantidade
    pdf.set_fill_color(220, 220, 220)
    pdf.set_font("Helvetica", "B", 9)
    pdf.cell(25, 10, "Codigo", 1, 0, "C", True)
    pdf.cell(85, 10, "Descricao", 1, 0, "C", True)
    pdf.cell(15, 10, "Unid", 1, 0, "C", True)
    pdf.cell(25, 10, "Qtd", 1, 0, "C", True)
    pdf.cell(40, 10, "Total (R$)", 1, 1, "C", True)
    
    total_geral = 0
    pdf.set_font("Helvetica", "", 8)
    for it in itens:
        pdf.cell(25, 10, str(it['codigo']), 1)
        pdf.cell(85, 10, str(it['descricao'])[:45], 1)
        pdf.cell(15, 10, str(it['unid']), 1, 0, "C")
        pdf.cell(25, 10, f"{it['quantidade']:.2f}", 1, 0, "C")
        pdf.cell(40, 10, f"{it['valor_total']:,.2f}", 1, 1, "R")
        total_geral += it['valor_total']
        
    pdf.ln(5)
    pdf.set_font("Helvetica", "B", 12)
    pdf.cell(150, 10, "VALOR TOTAL DO ORCAMENTO:", 0, 0, "R")
    pdf.cell(40, 10, f"R$ {total_geral:,.2f}", 0, 1, "R")
    return bytes(pdf.output())

# --- LOGIN E SEGURANÇA ---
if "autenticado" not in st.session_state:
    st.session_state.autenticado = False

if not st.session_state.autenticado:
    st.title("🏗️ Portal Célula Engenharia")
    token = st.text_input("Token ou Cupom de Teste:", type="password")
    if st.button("Entrar"):
        if token == "TESTE-GRATIS-30MIN":
            if "inicio_teste" not in st.session_state: st.session_state.inicio_teste = time.time()
            st.session_state.autenticado, st.session_state.tipo_acesso = True, "gratis"
            st.rerun()
        else:
            res = supabase.table("licencas").select("*").eq("token", token).execute()
            if res.data and not res.data[0]["em_uso"]:
                supabase.table("licencas").update({"em_uso": True}).eq("token", token).execute()
                st.session_state.update({"autenticado": True, "tipo_acesso": "pago", "token_ativo": token})
                st.rerun()
            else: st.error("Token inválido ou em uso.")
    st.stop()

# --- INTERFACE PRINCIPAL ---
st.title("🔍 Buscador EMOP - Jan/2026")
dados = load_db('emop 0126.xlsm')

if dados:
    lista_opcoes = [f"{i['c']} | {i['d']}" for i in dados]
    selecao = st.selectbox("Pesquise por código ou descrição:", options=[""] + lista_opcoes)
    
    if selecao:
        item = next(i for i in dados if i['c'] == selecao.split(" | ")[0])
        st.subheader(f"📍 {item['c']} - {item['d']}")
        
        c1, c2, c3 = st.columns(3)
        with c1: q_obra = st.number_input(f"Quantidade ({item['u']}):", min_value=0.01, value=1.0)
        with c2: jornada = st.number_input("Jornada (h/dia):", min_value=1.0, value=8.0)
        with c3: st.metric("VALOR TOTAL ITEM", f"R$ {q_obra * item['p']:,.2f}")
        
        if item['comp']:
            df_comp = pd.DataFrame(item['comp'])
            # 1. CALCULADORA DE CRONOGRAMA
            mo = df_comp[(df_comp['u'].str.upper() == 'H') & (df_comp['d'].str.upper().str.contains('MAO-DE-OBRA', na=False))].copy()
            if not mo.empty:
                st.write("### 👷 Cronograma de Execução")
                cols = st.columns(len(mo))
                for idx, (i, r) in enumerate(mo.iterrows()):
                    with cols[idx]:
                        nome = " ".join(str(r['d']).upper().replace('MAO-DE-OBRA DE ', '').split()[:2])
                        n_h = st.number_input(f"Nº de {nome}:", min_value=1, value=1, key=f"n_{i}")
                        st.write(f"⏱️ **{(r['q'] * q_obra) / (jornada * n_h):.2f} dias**")

            # 2. COMPOSIÇÃO DETALHADA
            st.write("### 📋 Composição e Insumos")
            df_comp['Total'] = df_comp['q'] * q_obra * df_comp['p']
            st.dataframe(df_comp.style.format({'q': '{:.4f}', 'p': 'R$ {:.2f}', 'Total': 'R$ {:.2f}'}), use_container_width=True)

        if st.button("➕ Adicionar ao Relatório PDF"):
            st.session_state.cesta_itens.append({
                "codigo": item['c'], 
                "descricao": item['d'], 
                "unid": item['u'], 
                "quantidade": q_obra,
                "valor_total": q_obra * item['p']
            })
            st.toast("Item adicionado com quantidade!")

# --- EXPORTAÇÃO PDF ---
if st.session_state.cesta_itens:
    st.divider()
    st.write("### 📋 Resumo do Orçamento")
    # Exibe a tabela com a coluna de quantidade para conferência
    df_resumo = pd.DataFrame(st.session_state.cesta_itens)
    st.dataframe(df_resumo[['codigo', 'descricao', 'unid', 'quantidade', 'valor_total']], 
                 use_container_width=True)
    
    if st.download_button("📥 Baixar Orçamento PDF Completo", 
                          data=gerar_pdf(st.session_state.cesta_itens), 
                          file_name="orcamento_celula_engenharia.pdf", 
                          mime="application/pdf"):
        st.success("PDF gerado com sucesso!")
        
    if st.button("🗑️ Limpar Lista"): 
        st.session_state.cesta_itens = []; st.rerun()

# Barra Lateral e Sair
if st.sidebar.button("Sair"):
    if st.session_state.get("tipo_acesso") == "pago":
        supabase.table("licencas").update({"em_uso": False}).eq("token", st.session_state.token_ativo).execute()
    st.session_state.autenticado = False; st.rerun()
