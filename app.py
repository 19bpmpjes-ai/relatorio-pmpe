import os
import zipfile
import io
import pandas as pd
import streamlit as st
import re

st.set_page_config(page_title="Processador de Relatórios PMPE", layout="wide")

st.title("📊 Processador de Relatórios SEI por OME")
st.write("Envie um ou **vários arquivos .zip** contendo os documentos HTML para gerar a planilha consolidada e organizada em abas por OME.")

# Alterado para aceitar múltiplos arquivos ZIP simultaneamente
arquivos_zip = st.file_uploader("Arraste e solte os arquivos .ZIP aqui", type=["zip"], accept_multiple_files=True)

if arquivos_zip:
    tabelas_encontradas = []
    
    with st.spinner("Processando e organizando todos os arquivos HTML dos ZIPs..."):
        # Percorre cada arquivo ZIP enviado
        for arquivo_zip in arquivos_zip:
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
                                    
                                    tem_grad = any(k in texto_completo for k in ["GRADUAÇÃO", "GRADUACAO", "GRAD.", "GRAD "]) or "GRAD" in texto_completo
                                    tem_matr = any(k in texto_completo for k in ["MATRÍCULA", "MATRICULA", "MAT.", "MAT "]) or "MAT" in texto_completo
                                    tem_nome = "NOME COMPLETO" in texto_completo or "NOME" in texto_completo
                                    
                                    if (tem_grad and tem_matr) or (tem_matr and tem_nome) or (tem_grad and tem_nome):
                                        
                                        # Promoção da primeira linha para cabeçalho caso necessário
                                        PRIMEIRA_LINHA = " ".join([str(val).upper() for val in df.iloc[0].values]) if len(df) > 0 else ""
                                        if any(k in PRIMEIRA_LINHA for k in ["GRAD", "MAT", "NOME"]):
                                            df.columns = df.iloc[0]
                                            df = df[1:].reset_index(drop=True)
                                        
                                        # Remover colunas duplicadas
                                        df = df.loc[:, ~df.columns.duplicated()].copy()
                                        df.columns = [str(c).strip() if pd.notna(c) else f"Coluna_{i}" for i, c in enumerate(df.columns)]
                                        
                                        # Adicionar identificação do arquivo e do ZIP de origem
                                        df.insert(0, 'Arquivo_Origem', os.path.basename(nome_arquivo))
                                        df.insert(0, 'ZIP_Origem', arquivo_zip.name)
                                        tabelas_encontradas.append(df)
                                        break
                            except Exception:
                                continue

    if tabelas_encontradas:
        df_final = pd.concat(tabelas_encontradas, ignore_index=True)
        df_final.dropna(how='all', inplace=True)
        
        # Identificar coluna de OME
        coluna_ome = None
        for col in df_final.columns:
            col_upper = str(col).upper()
            if any(k in col_upper for k in ["OME DESTINO", "OME DE DESTINO", "DESTINO", "OME"]):
                coluna_ome = col
                break
        
        buffer = io.BytesIO()
        with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
            # 1. Aba geral com TODOS
            df_final.to_excel(writer, index=False, sheet_name='TODOS')
            
            # 2. Abas separadas por OME
            if coluna_ome:
                grupos = df_final.groupby(coluna_ome)
                
                for nome_ome, df_grupo in grupos:
                    nome_aba = re.sub(r'[\\/*?:\[\]]', '', str(nome_ome)).strip().upper()
                    if not nome_aba or nome_aba == 'NAN':
                        nome_aba = "SEM OME"
                    
                    nome_aba = nome_aba[:31]
                    
                    sheet_names_existentes = writer.sheets.keys()
                    count = 1
                    nome_aba_final = nome_aba
                    while nome_aba_final in sheet_names_existentes:
                        nome_aba_final = f"{nome_aba[:28]}_{count}"
                        count += 1
                    
                    df_grupo.to_excel(writer, index=False, sheet_name=nome_aba_final)
        
        st.success(f"Sucesso! {len(tabelas_encontradas)} tabelas processadas a partir de {len(arquivos_zip)} arquivo(s) ZIP.")
        
        st.download_button(
            label="📥 Baixar Planilha Excel Consolidada (Todas OMEs)",
            data=buffer.getvalue(),
            file_name="Relatorio_Geral_Policiais_Por_OME.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
    else:
        st.error("Nenhuma tabela nos padrões reconhecidos foi encontrada nos arquivos ZIP enviados.")
