import os
import zipfile
import io
import pandas as pd
import streamlit as st

st.set_page_config(page_title="Processador de Relatórios PMPE", layout="centered")

st.title("📊 Processador de Relatórios SEI")
st.write("Envie o arquivo **.zip** contendo os documentos HTML para gerar a planilha consolidada.")

arquivo_zip = st.file_uploader("Arraste e solte o arquivo .ZIP aqui", type=["zip"])

if arquivo_zip is not None:
    tabelas_encontradas = []
    
    with st.spinner("Processando arquivos HTML..."):
        with zipfile.ZipFile(arquivo_zip, 'r') as z:
            for nome_arquivo in z.namelist():
                if nome_arquivo.endswith('.html') or nome_arquivo.endswith('.htm'):
                    with z.open(nome_arquivo) as f:
                        try:
                            dfs = pd.read_html(f)
                            for df in dfs:
                                colunas_texto = [str(col).upper() for col in df.columns]
                                conteudo_texto = df.to_string().upper()
                                
                                if any("GRADUAÇÃO" in col or "GRADUACAO" in col for col in colunas_texto) or "MATRÍCULA" in conteudo_texto:
                                    if "GRADUAÇÃO" not in str(df.columns[0]).upper() and "GRADUACAO" not in str(df.columns[0]).upper():
                                        df.columns = df.iloc[0]
                                        df = df[1:].reset_index(drop=True)
                                    
                                    df.insert(0, 'Arquivo_Origem', os.path.basename(nome_arquivo))
                                    tabelas_encontradas.append(df)
                                    break
                        except Exception:
                            continue

    if tabelas_encontradas:
        df_final = pd.concat(tabelas_encontradas, ignore_index=True)
        df_final.dropna(how='all', inplace=True)
        
        buffer = io.BytesIO()
        with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
            df_final.to_excel(writer, index=False, sheet_name='Cadastros')
        
        st.success(f"Sucesso! {len(tabelas_encontradas)} policiais processados.")
        
        st.download_button(
            label="📥 Baixar Planilha Excel Consolidada",
            data=buffer.getvalue(),
            file_name="Dados_Consolidados_Policiais.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
    else:
        st.error("Nenhuma tabela no padrão de 'GRADUAÇÃO / MATRÍCULA' foi encontrada no arquivo ZIP enviado.")