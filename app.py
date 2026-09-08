import os
import zipfile
import io
import pandas as pd
import streamlit as st

st.set_page_config(page_title="Processador de Relatórios PMPE", layout="wide")

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
                                colunas_texto = " ".join([str(col).upper() for col in df.columns])
                                conteudo_texto = df.to_string().upper()
                                texto_completo = colunas_texto + " " + conteudo_texto
                                
                                # Termos de busca abrangentes (incluindo palavras sem ponto)
                                tem_grad = any(k in texto_completo for k in ["GRADUAÇÃO", "GRADUACAO", "GRAD.", "GRAD "]) or "GRAD" in texto_completo
                                tem_matr = any(k in texto_completo for k in ["MATRÍCULA", "MATRICULA", "MAT.", "MAT "]) or "MAT" in texto_completo
                                tem_nome = "NOME COMPLETO" in texto_completo or "NOME" in texto_completo
                                
                                if (tem_grad and tem_matr) or (tem_matr and tem_nome) or (tem_grad and tem_nome):
                                    
                                    # Tratar promoção de primeira linha para cabeçalho
                                    PRIMEIRA_LINHA = " ".join([str(val).upper() for val in df.iloc[0].values]) if len(df) > 0 else ""
                                    if any(k in PRIMEIRA_LINHA for k in ["GRAD", "MAT", "NOME"]):
                                        df.columns = df.iloc[0]
                                        df = df[1:].reset_index(drop=True)
                                    
                                    # Remover colunas duplicadas e organizar nomes
                                    df = df.loc[:, ~df.columns.duplicated()].copy()
                                    df.columns = [str(c).strip() if pd.notna(c) else f"Coluna_{i}" for i, c in enumerate(df.columns)]
                                    
                                    # Adicionar origem do arquivo
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
        
        st.success(f"Sucesso! {len(tabelas_encontradas)} tabelas/documentos processados.")
        
        st.download_button(
            label="📥 Baixar Planilha Excel Consolidada",
            data=buffer.getvalue(),
            file_name="Dados_Consolidados_Policiais.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
    else:
        st.error("Nenhuma tabela nos padrões reconhecidos (GRAD / MAT / NOME) foi encontrada no arquivo ZIP enviado.")
