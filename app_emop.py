import streamlit as st
import pandas as pd

# Inicializa o estado de autenticação antes de qualquer outra coisa
if "autenticado" not in st.session_state:
    st.session_state.autenticado = False

def verificar_acesso():
    if not st.session_state.autenticado:
        st.title("🔐 Acesso Restrito")
        token_input = st.text_input("Digite seu Token de Acesso:", type="password")
        if st.button("Liberar Sistema"):
            # O token deve estar exatamente como abaixo
            if token_input == "ENG-EMERSON-2026":
                st.session_state.autenticado = True
                st.rerun()
            else:
                st.error("Token inválido.")
        return False
    return True

# Apenas se passar na verificação o restante do código executa
if verificar_acesso():
    st.title("🏗️ Buscador de Composições EMOP")
    # Restante do seu código aqui...
