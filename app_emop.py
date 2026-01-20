import streamlit as st
import pandas as pd

# 1. CONFIGURAÇÃO DE SEGURANÇA (TOKENS)
# Adicione ou remova tokens aqui para gerenciar seus clientes
TOKENS_VALIDOS = ["ENG-EMERSON-2026", "CLIENTE-OBRA-01", "ACESS-VIP-EMOP"]

def verificar_acesso():
    if "autenticado" not in st.session_state:
        st.session_state.autenticado = False

    if not st.session_state.autenticado:
        st.title("🔐 Acesso Restrito - Buscador EMOP")
        st.write("Para comercializar este app, este token é sua chave de licença única.")
        
        token_input = st.text_input("Digite seu Token de Acesso:", type="password")
        
        if st.button("Liberar Sistema"):
            if token_input in TOKENS_VALIDOS:
                st.session_state.autenticado = True
                st.success("Acesso autorizado!")
                st.rerun()
            else:
                st.error("Token inválido ou expirado. Fale com o administrador.")
        return False
    return True

# 2. EXECUÇÃO DO APLICATIVO
if verificar_acesso():
    st.set_page_config(page_title="Buscador EMOP Pro", layout="wide")
    st.title("🏗️ Buscador de Composições EMOP")
    
    # Carregamento da Planilha (usando o nome exato do arquivo que você subiu)
    @st.cache_data
    def carregar_dados():
        try:
            # Lendo o arquivo .xlsm que você subiu no GitHub
            df = pd.read_excel("emop 0126.xlsm", engine="openpyxl")
            return df
        except Exception as e:
            st.error(f"Erro ao carregar a base de dados: {e}")
            return None

    df_emop = carregar_dados()

    if df_emop is not None:
        st.write(f"Base de dados carregada com sucesso! ({len(df_emop)} itens)")
        
        # Interface de Busca
        busca = st.text_input("Digite o código ou descrição do item:")
        
        if busca:
            # Lógica simples de filtro (ajuste as colunas conforme sua planilha)
            resultados = df_emop[df_emop.astype(str).apply(lambda x: busca.lower() in x.str.lower().any(), axis=1)]
            st.dataframe(resultados)
