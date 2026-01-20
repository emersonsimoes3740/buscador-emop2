import pandas as pd
import streamlit as st

# 1. CONFIGURAÇÃO INICIAL E SEGURANÇA
st.set_page_config(page_title="EMOP 2026 - Eng. Emerson Simões", layout="wide")

def validar_token(token_usuario):
    try:
        # Tenta ler a lista de 10 mil tokens que você deve subir como 'tokens_validos.txt'
        with open("tokens_validos.txt", "r") as f:
            tokens = [linha.strip() for linha in f.readlines()]
            return token_usuario in tokens
    except FileNotFoundError:
        # Token mestre para acesso inicial
        return token_usuario == "ENG-EMERSON-2026"

if "autenticado" not in st.session_state:
    st.session_state.autenticado = False

if not st.session_state.autenticado:
    st.title("🔐 Acesso Restrito - Gestor EMOP")
    st.write("Insira sua licença de uso para acessar a base de dados.")
    
    token_input = st.text_input("Digite seu Token de Acesso:", type="password")
    
    if st.button("Validar Licença"):
        if validar_token(token_input):
            st.session_state.autenticado = True
            st.success("Acesso autorizado!")
            st.rerun()
        else:
            st.error("Token inválido ou expirado. Fale com o administrador.")
    st.stop() 

# 2. LÓGICA DO SISTEMA (Processamento da Planilha EMOP Jan/2026)
@st.cache_data
def load_db(path):
    try:
        df = pd.read_excel(path)
        # Padronizando as colunas da EMOP conforme sua estrutura
        df.columns = ['C','D','U','Q','P','PC','T']
        db, pai = [], None
        for _, r in df.iterrows():
            # Identifica Item Principal (Serviço)
            if pd.isna(r['Q']) and pd.notna(r['C']):
                # Estrutura quebrada em linhas para evitar SyntaxError
                pai = {
                    'c': str(r['C']),
                    'd': str(r['D']),
                    'u': str(r['U']),
                    'p': float(r['P']) if pd.notna(r['P']) else 0.0,
                    'comp': []
                }
                db.append(pai)
            # Identifica Insumo (Composição)
            elif pd.notna(r['Q']) and pai:
                pai['comp'].append({
                    'c': str(r['C']),
                    'd': str(r['D']),
                    'u': str(r['U']),
                    'q': float(r['Q']),
                    'p': float(r['P']) if pd.notna(r['P']) else 0.0
                })
        return db
    except Exception as e:
        st.error(f"Erro ao carregar Excel: {e}")
        return []

st.title("🏗️ Gestor de Obras EMOP - Jan/2026")
st.markdown("**Desenvolvido por Eng. Emerson Simões**")

# Carrega o arquivo excel que está no seu repositório privado
dados = load_db('emop 0126.xlsm')

if dados:
    lista = [f"{i['c']} | {i['d']}" for i in dados]
    sel = st.selectbox("Selecione ou digite o Item para analisar:", options=[""] + lista)

    if sel:
        it = next(i for i in dados if i['c'] == sel.split(" | ")[0])
        st.divider()
        st.subheader(f"📍 {it['c']} - {it['d']}")
        
        c1, c2, c3 = st.columns(3)
        with c1:
            q_o = st.number_input(f"Quantidade da Obra ({it['u']}):", min_value=0.01, value=100.0)
        with c2:
            jor = st.number_input("Jornada de Trabalho (h/dia):", min_value=1.0, value=8.0)
        with c3:
            v_t = q_o * it['p']
            # Exibição do valor total formatado
            st.metric("VALOR TOTAL ITEM", f"R$ {v_t:,.2f}")

        if it['comp']:
            df_c = pd.DataFrame(it['comp'])
            df_c['MO'] = df_c['u'].str.upper().apply(lambda x: 'H' in str(x))
            mo = df_c[df_c['MO'] == True]
            
            pzs, d_calc = [], {}
            
            if not mo.empty:
                st.write("### 👷 Cronograma de Execução")
                cols = st.columns(len(mo))
                for i, (idx, r) in enumerate(mo.iterrows()):
                    with cols[i]:
                        n = st.number_input(f"Nº de {r['d'][:20]}:", min_value=1, value=1, key=f"k{idx}")
                        d = (r['q'] * q_o) / (jor * n)
                        pzs.append(d)
                        d_calc[idx] = d
                        st.write(f"⏱️ **{d:.2f} dias**")
                
                if pzs:
                    st.info(f"📅 **PRAZO TOTAL ESTIMADO:** {max(pzs):.2f} dias úteis.")

            st.write("### 📋 Composição e Insumos")
            df_c['Q_Tot'] = df_c['q'] * q_o
            df_c['C_Tot'] = df_c['Q_Tot'] * df_c['p']
            df_c['Dias'] = df_c.index.map(lambda x: d_calc.get(x, 0.0))
            
            df_ver = df_c.rename(columns={'c':'Cód.','d':'Descrição','u':'Unid.','q':'Coef.','p':'Preço Unit.'})
            
            st.dataframe(df_ver[['Cód.','Descrição','Unid.','Coef.','Q_Tot','Preço Unit.','C_Tot','Dias']].style.format({
                'Coef.':'{:.4f}', 'Q_Tot':'{:.2f}', 'Preço Unit.':'R$ {:.2f}', 
                'C_Tot':'R$ {:.2f}', 'Dias':'{:.2f}'
            }), use_container_width=True, hide_index=True)
        else:
            st.warning("Composição detalhada não encontrada para este item.")

st.markdown("---")
st.markdown("<p style='text-align: center; color: gray;'>Sistema desenvolvido por Eng. Emerson Simões - Referência EMOP Jan/2026</p>", unsafe_allow_html=True)
