import pandas as pd
import streamlit as st

# Configuração da página
st.set_page_config(page_title="EMOP 2026 - Eng. Emerson Simões", layout="wide")

@st.cache_data
def load_db(path):
    try:
        df = pd.read_excel(path)
        # Padronizando as colunas da EMOP (A a G)
        df.columns = ['C','D','U','Q','P','PC','T']
        db, pai = [], None
        for _, r in df.iterrows():
            # Identifica Item Principal (Serviço)
            if pd.isna(r['Q']) and pd.notna(r['C']):
                pai = {'c':str(r['C']),'d':str(r['D']),'u':str(r['U']),'p':float(r['P']) if pd.notna(r['P']) else 0.0,'comp':[]}
                db.append(pai)
            # Identifica Insumo (Composição)
            elif pd.notna(r['Q']) and pai:
                pai['comp'].append({'c':str(r['C']),'d':str(r['D']),'u':str(r['U']),'q':float(r['Q']),'p':float(r['P']) if pd.notna(r['P']) else 0.0})
        return db
    except Exception as e:
        st.error(f"Erro ao carregar Excel: {e}")
        return []

# Título Principal
st.title("🏗️ Gestor de Obras EMOP - Jan/2026")
st.markdown("**Desenvolvido por Eng. Emerson Simões**")

dados = load_db('emop 0126.xlsm')

if dados:
    lista = [f"{i['c']} | {i['d']}" for i in dados]
    sel = st.selectbox("Selecione ou digite o Item para analisar:", options=[""] + lista)

    if sel:
        # Busca o item selecionado
        it = next(i for i in dados if i['c'] == sel.split(" | ")[0])
        st.divider()
        st.subheader(f"📍 {it['c']} - {it['d']}")
        
        # Painel de Inputs
        c1, c2, c3 = st.columns(3)
        with c1:
            q_o = st.number_input(f"Quantidade da Obra ({it['u']}):", min_value=0.01, value=100.0)
        with c2:
            jor = st.number_input("Jornada de Trabalho (h/dia):", min_value=1.0, value=8.0)
        with c3:
            v_t = q_o * it['p']
            st.metric("VALOR TOTAL ITEM", f"R$ {v_t:,.2f}")

        if it['comp']:
            df_c = pd.DataFrame(it['comp'])
            # Filtra Mão de Obra (unidades que contém 'H')
            df_c['MO'] = df_c['u'].str.upper().apply(lambda x: 'H' in str(x))
            mo = df_c[df_c['MO'] == True]
            
            pzs, d_calc = [], {}
            
            # Seção de Cronograma
            if not mo.empty:
                st.write("### 👷 Cronograma de Execução")
                cols = st.columns(len(mo))
                for i, (idx, r) in enumerate(mo.iterrows()):
                    with cols[i]:
                        # Mostra apenas os primeiros 20 caracteres da descrição do profissional
                        n = st.number_input(f"Nº de {r['d'][:20]}:", min_value=1, value=1, key=f"k{idx}")
                        d = (r['q'] * q_o) / (jor * n)
                        pzs.append(d)
                        d_calc[idx] = d
                        st.write(f"⏱️ **{d:.2f} dias**")
                
                if pzs:
                    st.info(f"📅 **PRAZO TOTAL ESTIMADO:** {max(pzs):.2f} dias úteis.")

            # Seção de Tabela de Insumos
            st.write("### 📋 Composição e Insumos")
            df_c['Q_Tot'] = df_c['q'] * q_o
            df_c['C_Tot'] = df_c['Q_Tot'] * df_c['p']
            df_c['Dias'] = df_c.index.map(lambda x: d_calc.get(x, 0.0))
            
            # Renomeando para exibição
            df_ver = df_c.rename(columns={'c':'Cód.','d':'Descrição','u':'Unid.','q':'Coef.','p':'Preço Unit.'})
            
            st.dataframe(df_ver[['Cód.','Descrição','Unid.','Coef.','Q_Tot','Preço Unit.','C_Tot','Dias']].style.format({
                'Coef.':'{:.4f}', 'Q_Tot':'{:.2f}', 'Preço Unit.':'R$ {:.2f}', 
                'C_Tot':'R$ {:.2f}', 'Dias':'{:.2f}'
            }), use_container_width=True, hide_index=True)

        else:
            st.warning("Composição detalhada não encontrada para este item.")

st.markdown("---")
st.markdown("<p style='text-align: center; color: gray;'>Sistema desenvolvido por Eng. Emerson Simões - Referência EMOP Jan/2026</p>", unsafe_allow_html=True)