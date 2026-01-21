import pandas as pd
import streamlit as st
from supabase import create_client
from fpdf import FPDF
import os
import time

# 1. CONEXÃO E CONFIGURAÇÃO (SUPABASE)
# Certifique-se de que as chaves estão nos 'Secrets' do Streamlit Cloud
url = st.secrets["SUPABASE_URL"]
key = st.secrets["SUPABASE_KEY"]
supabase = create_client(url, key)

st.set_page_config(page_title="Gestor EMOP - Eng. Emerson Simões", layout="wide")

# Inicializa a cesta de itens se não existir
if "cesta_itens" not in st.session_state:
    st.session_state.cesta_itens = []

# --- FUNÇÃO DE CARGA DE DADOS (Base EMOP Jan/2026) ---
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
            # Identifica Serviço (Item Principal)
            if pd.notna(r['C']) and pd.isna(r['Q']):
                pai = {'c': str(r['C']), 'd': str(r['D']), 'u': str(r['U']),
                       'p': float(r['P']) if pd.notna(r['P']) else 0.0, 'comp': []}
                db.append(pai)
            # Identifica Insumos (Composições)
            elif pd.notna(r['Q']) and pai:
                pai['comp'].append({'c': str(r['C']), 'd': str(r['D']), 'u': str(r['U']),
                                    'q': float(r['Q']), 'p': float(r['P']) if pd.notna(r['P']) else 0.0})
        return db
    except Exception:
        return None

# --- FUNÇÃO GERADORA DE PDF (Correção de Bytes para Streamlit) ---
def gerar_pdf(itens):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Helvetica", "B", 16)
    pdf.cell(190, 10, "CELULA ENGENHARIA - RELATORIO EMOP", 0, 1, "C")
    pdf.set_font("Helvetica", "", 10)
    pdf.cell(190, 10, f"Data: {time.strftime('%d/%m/%Y')} | Ref: EMOP 01/2026", 0, 1, "C")
    pdf.ln(10)
    
    # Cabeçalho da Tabela
    pdf.set_fill_color(220, 220, 220)
    pdf.set_font("Helvetica", "B", 10)
    pdf.cell(30, 10, "Codigo", 1, 0, "C", True)
    pdf.cell(100, 10, "Descricao", 1, 0, "C", True)
    pdf.cell(20, 10, "Unid", 1, 0, "C", True)
    pdf.cell(40, 10, "Total (R$)", 1, 1, "C", True)
    
    total_geral = 0
    pdf.set_font("Helvetica", "", 8)
    for it in itens:
        # Limita descrição para não quebrar a tabela
        desc = str(it['descricao'])[:55]
        pdf.cell(30, 10, str(it['codigo']), 1)
        pdf.cell(100, 10, desc, 1)
        pdf.cell(20, 10, str(it['unid']), 1, 0, "C")
        pdf.cell(40, 10, f"{it['valor_total']:,.2f}", 1, 1, "R")
        total_geral += it['valor_total']
    
    pdf.ln(5)
    pdf.set_font("Helvetica", "B", 12)
    pdf.cell(150, 10, "VALOR TOTAL DO ORCAMENTO:", 0, 0, "R")
    pdf.cell(40, 10, f"R$ {total_geral:,.2f}", 0, 1, "R")
    
    # Retorna o PDF como bytes puros para o download_button
    return bytes(pdf.output())

# --- LÓGICA DE LOGIN E SEGURANÇA ---
if "autenticado" not in st.session_state:
    st.session_state.autenticado = False

if not st.session_state.autenticado:
    st.title("🏗️ Portal Célula Engenharia")
    st.write("Acesse com seu Token ou use o cupom de teste.")
    token = st.text_input("Token de Acesso:", type="password")
    TOKEN_TESTE = "TESTE-GRATIS-30MIN" #
    
    if st.button("Entrar"):
        if token == TOKEN_TESTE:
            if "inicio_teste" not in st.session_state: 
                st.session_state.inicio_teste = time.time()
            st.session_state.autenticado, st.session_state.tipo_acesso = True, "gratis"
            st.rerun()
        else:
            # Validação via Supabase
            res = supabase.table("licencas").select("*").eq("token", token).execute()
            if res.data and not res.data[0]["em_uso"]:
                supabase.table("licencas").update({"em_uso": True}).eq("token", token).execute()
                st.session_state.autenticado, st.session_state.tipo_acesso, st.session_state.token_ativo = True, "pago", token
                st.rerun()
            else: 
                st.error("Token inválido ou já em uso em outro dispositivo.")
    st.stop()

# --- CONTROLE DE SESSÃO ---
if st.session_state.get("tipo_acesso") == "gratis":
    restante = 30 - (time.time() - st.session_state.inicio_teste) / 60
    if restante <= 0:
        st.error("Tempo de teste expirado!"); st.session_state.autenticado = False; st.rerun()
    st.sidebar.warning(f"⏱️ {int(restante)} min restantes")

if st.sidebar.button("Encerrar Sessão (Sair)"):
    if st.session_state.get("tipo_acesso") == "pago":
        supabase.table("licencas").update({"em_uso": False}).eq("token", st.session_state.token_ativo).execute()
    st.session_state.autenticado = False; st.rerun()

# --- INTERFACE DO BUSCADOR ---
st.title("🔍 Buscador EMOP - Jan/2026")
dados = load_db('emop 0126.xlsm') # Certifique-se que o arquivo está no GitHub

if dados:
    lista_opcoes = [f"{i['c']} | {i['d']}" for i in dados]
    selecao = st.selectbox("Pesquise por código ou descrição:", options=[""] + lista_opcoes)
    
    if selecao:
        cod_limpo = selecao.split(" | ")[0]
        item = next(i for i in dados if i['c'] == cod_limpo)
        st.subheader(f"📍 {item['c']} - {item['d']}")
        
        c1, c2, c3 = st.columns(3)
        with c1: q_obra = st.number_input(f"Quantidade ({item['u']}):", min_value=0.01, value=1.0)
        with c2: jornada = st.number_input("Jornada (h/dia):", min_value=1.0, value=8.0)
        with c3: st.metric("VALOR TOTAL ITEM", f"R$ {q_obra * item['p']:,.2f}")
        
        # CALCULADORA DE MÃO DE OBRA (Cronograma)
        if item['comp']:
            df_comp = pd.DataFrame(item['comp'])
            mo = df_comp[(df_comp['u'].str.upper() == 'H') & (df_comp['d'].str.upper().str.contains('MAO-DE-OBRA', na=False))].copy()
            if not mo.empty:
                st.write("### 👷 Cronograma de Execução")
                prazos = []
                cols = st.columns(len(mo))
                for idx, (i, r) in enumerate(mo.iterrows()):
                    with cols[idx]:
                        nome = " ".join(str(r['d']).upper().replace('MAO-DE-OBRA DE ', '').split()[:2])
                        n_homens = st.number_input(f"Nº de {nome}:", min_value=1, value=1, key=f"n_{i}")
                        prazo = (r['q'] * q_obra) / (jornada * n_homens)
                        prazos.append(prazo); st.write(f"⏱️ **{prazo:.2f} dias**")
                if prazos: st.info(f"📅 **PRAZO ESTIMADO:** {max(prazos):.2f} dias úteis.")

        # BOTÃO PARA CESTA
        if st.button("➕ Adicionar ao Relatório PDF"):
            st.session_state.cesta_itens.append({
                "codigo": item['c'], "descricao": item['d'], "unid": item['u'], "valor_total": q_obra * item['p']
            })
            st.toast("Item adicionado à lista!")

# --- CESTA DE ITENS E EXPORTAÇÃO PDF ---
if st.session_state.cesta_itens:
    st.divider()
    st.write("### 📋 Itens do seu Orçamento")
    st.dataframe(pd.DataFrame(st.session_state.cesta_itens), use_container_width=True)
    
    try:
        # Gera os bytes antes do botão para evitar erro de StreamlitAPIException
        pdf_bytes = gerar_pdf(st.session_state.cesta_itens)
        
        col_pdf, col_limpar = st.columns(2)
        with col_pdf:
            st.download_button(
                label="📥 Baixar Orçamento em PDF",
                data=pdf_bytes,
                file_name="orcamento_celula_engenharia.pdf",
                mime="application/pdf",
                key="btn_pdf"
            )
        with col_limpar:
            if st.button("🗑️ Limpar Lista de Itens"):
                st.session_state.cesta_itens = []; st.rerun()
    except Exception as e:
        st.error(f"Erro ao gerar PDF: {e}")

st.sidebar.markdown("---")
st.sidebar.write(f"Conectado como: {st.session_state.get('token_ativo', 'Visitante')}")
