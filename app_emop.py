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
st.title("Buscador de Preços - EMOP")

# Sistema de Login por Token
if "autenticado" not in st.session_state:
    st.session_state.autenticado = False

if not st.session_state.autenticado:
    token_input = st.text_input("Insira seu token de acesso:", type="password")
    if st.button("Acessar"):
        if validar_acesso_exclusivo(token_input):
            st.session_state.autenticado = True
            st.success("Acesso liberado!")
            st.rerun()
        else:
            st.error("Token inválido ou expirado.")
else:
    # --- ÁREA LOGADA DO APP ---
    st.sidebar.success("Conectado")
    if st.sidebar.button("Sair"):
        st.session_state.autenticado = False
        st.rerun()

    termo_busca = st.text_input("O que você deseja buscar na base EMOP?")
    
    if st.button("Buscar"):
        # Exemplo de lógica de busca (ajuste conforme sua tabela de dados)
        try:
            # Aqui simulamos a busca na sua tabela de itens EMOP
            # Substitua 'itens_emop' pelo nome real da sua tabela de dados
            response = supabase.table("itens_emop").select("*").ilike("descricao", f"%{termo_busca}%").execute()
            dados = response.data

            # CORREÇÃO DA LINHA 89 (Indentação corrigida)
            if dados:
                st.write(f"Encontrados {len(dados)} resultados:")
                st.dataframe(dados)
            else:
                st.warning("Nenhum item encontrado com esse termo.")
        
        except Exception as e:
            st.error(f"Erro ao realizar busca: {e}")

---

### O que foi corrigido:
* **Linha 89:** O bloco `if dados:` agora possui comandos recuados (o `st.write` e o `st.dataframe`), eliminando o `IndentationError`.
* **Conexão httpx:** O código
