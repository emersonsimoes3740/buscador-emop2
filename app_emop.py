import streamlit as st
from supabase import create_client, Client

# 1. Configuração Segura das Credenciais (Secrets)
try:
    url = st.secrets["SUPABASE_URL"]
    key = st.secrets["SUPABASE_KEY"]
    supabase: Client = create_client(url, key)
except Exception as e:
    st.error("Erro ao carregar credenciais. Verifique os Secrets no painel do Streamlit.")
    st.stop()

# 2. Função de Validação de Acesso
def validar_acesso_exclusivo(token_digitado):
    if not token_digitado:
        return False
    try:
        # Consulta na tabela 'licencas' do seu Supabase
        res = supabase.table("licencas").select("*").eq("token", token_digitado).execute()
        return len(res.data) > 0
    except Exception as e:
        st.error(f"Erro na conexão com o banco de dados: {e}")
        return False

# 3. Interface do Aplicativo
st.set_page_config(page_title="Buscador EMOP", layout="wide")
st.title("🔍 Buscador de Preços - EMOP")

# Sistema de Login por Token
if "autenticado" not in st.session_state:
    st.session_state.autenticado = False

if not st.session_state.autenticado:
    st.subheader("Acesso Restrito")
    token_input = st.text_input("Insira seu token de acesso:", type="password")
    if st.button("Acessar Sistema"):
        if validar_acesso_exclusivo(token_input):
            st.session_state.autenticado = True
            st.success("Acesso liberado!")
            st.rerun()
        else:
            st.error("Token inválido ou expirado.")
else:
    # --- ÁREA LOGADA DO APP ---
    st.sidebar.success("Usuário Autenticado")
    if st.sidebar.button("Encerrar Sessão"):
        st.session_state.autenticado = False
        st.rerun()

    st.markdown("### Pesquisa na Base de Dados")
    termo_busca = st.text_input("Digite o nome do material ou código EMOP:")
    
    if st.button("Realizar Busca"):
        if termo_busca:
            try:
                # Busca na tabela de itens (ajuste 'itens_emop' se o nome for outro)
                response = supabase.table("itens_emop").select("*").ilike("descricao", f"%{termo_busca}%").execute()
                dados = response.data

                if dados:
                    st.write(f"Foram encontrados **{len(dados)}** resultados para sua busca.")
                    st.dataframe(dados, use_container_width=True)
                else:
                    st.warning("Nenhum item encontrado com esse termo. Tente palavras-chave diferentes.")
            
            except Exception as e:
                st.error(f"Erro ao realizar busca no banco: {e}")
        else:
            st.info("Por favor, digite um termo para buscar.")
