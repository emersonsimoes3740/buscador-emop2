import pandas as pd
import streamlit as st
from supabase import create_client
import os

# 1. CONEXÃO SEGURA COM SUPABASE (Proteção contra uso simultâneo)
# Certifique-se de que as chaves estão configuradas nos 'Secrets' do Streamlit Cloud
url = st.secrets["SUPABASE_URL"]
key = st.secrets["SUPABASE_KEY"]
supabase = create_client(url, key)

# Configuração da página padrão Engenharia
st.set_page_config(page_title="Gestor EMOP - Eng. Emerson Simões", layout="wide")

# --- SISTEMA DE ACESSO EXCLUSIVO ---
if "autenticado" not in st.session_state:
    st.session_state.autenticado = False

if not st.session_state.autenticado:
    st.title("🏗️ Portal de Engenharia - Eng. Emerson Simões")
    st.write("Acesse a base de dados EMOP 01/2026 com sua licença exclusiva.")
    
    token = st.text_input("Insira seu Token de Licença:", type="password")
    
    if st.button("Acessar Sistema"):
        # Consulta o banco de dados Supabase
        res = supabase.table("licencas").select("*").eq("token", token).execute()
        if res.data:
            dados_token = res.data[0]
            if not dados_token["ativa"]:
                st.error("Esta licença foi desativada pelo administrador.")
            elif dados_token["em_uso"]:
                st.warning("⚠️ Este token já está em uso noutro dispositivo. Encerre a outra sessão.")
            else:
                # Bloqueia o token no banco para uso exclusivo
                supabase.table("licencas").update({"em_uso": True}).eq("token", token).execute()
                st.session_state.autenticado = True
                st.session_state.token_ativo = token
                st.rerun()
        else:
            st.error("Token não encontrado ou inválido.")
    st.stop()

# Botão de Logout para liberar o token no banco de dados
if st.sidebar.button("Encerrar Sessão (Sair)"):
    supabase.table("licencas").update({"em_uso": False}).eq("token", st.session_state.token_ativo).execute()
    st.session_state.autenticado = False
    st.rerun()

# 2. PROCESSAMENTO DA PLANILHA EMOP
@st.cache_data
def load_db(path):
    if not os.path.exists(path):
        return f"Erro: Arquivo {path} não encontrado no repositório."
    try:
        df = pd.read_excel(path)
        # Padronização de colunas conforme estrutura EMOP: Cod, Desc, Unid, Qtd, Preço...
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
            # Identifica Insumos (Composição)
            elif pd.notna(r['Q']) and pai:
                pai['comp'].append({'c': str(r['C']), 'd': str(r['D']), 'u': str(r['U']),
                                    'q': float(r['Q']), 'p': float(r['P']) if pd.notna(r['P']) else 0.0})
        return db
    except Exception as e:
        return f"Erro ao processar: {e}"

st.title("🔍 Buscador EMOP - Janeiro/2026")
# Carrega a planilha que você subiu para o GitHub
dados = load_db('emop 0126.xlsm')

if isinstance(dados, list) and dados:
    lista_servicos = [f"{i['c']} | {i['d']}" for i in dados]
    selecao = st.selectbox("Selecione ou digite o código/descrição do item:", options=[""] + lista_servicos)

    if selecao:
        codigo_sel = selecao.split(" | ")[0]
        item = next(i for i in dados if i['c'] == codigo_sel)
        
        st.divider()
        st.subheader(f"📍 {item['c']} - {item['d']}")
        
        # Painel de Cálculo
        c1, c2, c3 = st.columns(3)
        with c1:
            q_obra = st.number_input(f"Quantidade da Obra ({item['u']}):", min_value=0.01, value=1.0)
        with c2:
            jor = st.number_input("Jornada (h/dia):", min_value=1.0, value=8.0)
        with c3:
            st.metric("VALOR TOTAL ITEM", f"R$ {q_obra * item['p']:,.2f}")

        # 3. CALCULADORA DE CRONOGRAMA (MÃO DE OBRA LIMPA)
        if item['comp']:
            df_comp = pd.DataFrame(item['comp'])
            # Filtra apenas o que é Mão de Obra (Unidade H e descrição contém 'MAO-DE-OBRA')
            mo = df_comp[
                (df_comp['u'].str.upper() == 'H') & 
                (df_comp['d'].str.upper().str.contains('MAO-DE-OBRA', na=False))
            ].copy()
            
            if not mo.empty:
                st.write("### 👷 Cronograma de Execução")
                prazos_dias = []
                cols_mo = st.columns(len(mo))
                
                for idx_mo, (index, row) in enumerate(mo.iterrows()):
                    with cols_mo[idx_mo]:
                        # Limpa o nome para mostrar apenas a profissão (ex: PEDREIRO)
                        desc_limpa = str(row['d']).upper().replace('MAO-DE-OBRA DE ', '').strip()
                        nome_prof = " ".join(desc_limpa.split()[:2])
                        
                        num_homens = st.number_input(f"Nº de {nome_prof}:", min_value=1, value=1, key=f"mo_{index}")
                        
                        # Cálculo: (Coeficiente * Qtd Obra) / (Jornada * Nº Homens)
                        prazo_ind = (row['q'] * q_obra) / (jor * num_homens)
                        prazos_dias.append(prazo_ind)
                        st.write(f"⏱️ **{prazo_ind:.2f} dias**")
                
                if prazos_dias:
                    st.info(f"📅 **PRAZO ESTIMADO DO SERVIÇO:** {max(prazos_dias):.2f} dias úteis.")
            else:
                st.warning("Este serviço não possui itens de mão-de-obra direta para cálculo de cronograma.")

            # 4. TABELA DE COMPOSIÇÃO DETALHADA
            st.write("### 📋 Detalhamento de Insumos")
            df_comp['Total'] = df_comp['q'] * q_obra * df_comp['p']
            st.dataframe(
                df_comp.style.format({'q': '{:.4f}', 'p': 'R$ {:.2f}', 'Total': 'R$ {:.2f}'}), 
                use_container_width=True
            )

st.sidebar.markdown("---")
st.sidebar.write(f"Conectado com o token: {st.session_state.token_ativo}")
