import os
import zipfile
import io
import pandas as pd
import streamlit as st
import re

st.set_page_config(page_title="Processador de Relatórios PMPE", layout="wide")

st.title("📊 Processador de Relatórios SEI por OME")
st.write("Envie um ou **vários arquivos .zip** contendo os documentos HTML para gerar a planilha consolidada.")

arquivos_zip = st.file_uploader("Arraste e solte os arquivos .ZIP aqui", type=["zip"], accept_multiple_files=True)

def padronizar_ome(texto_ome):
    """
    Padroniza variações de nomes de OMEs para um formato único.
    Ex: '10', '10 BPM', '10ºBPM' -> '10º BPM'
    """
    if pd.isna(texto_ome):
        return "SEM OME"
        
    texto = str(texto_ome).upper().strip()
    
    if not texto or texto == "NAN":
        return "SEM OME"
        
    # Mapeamentos específicos e especializadas / programas
    if any(k in texto for k in ["DASDH", "PATRULHA DO BAIRRO", "DIRETORIA DE ASSISTENCIA"]):
        return "DASDH / PATRULHA DO BAIRRO"
    if "BOPE" in texto:
        return "BOPE"
    if "CHOQUE" in texto or "BPCHOQUE" in texto:
        return "BPChoque"
    if "RADIOPATRULHA" in texto or "BPRP" in texto:
        return "BPRP"
    if "RPMON" in texto or "MONTADA" in texto:
        return "RPMon"
    if "BPTRAN" in texto or "TRÂNSITO" in texto or "TRANSITO" in texto:
        return "1º BPTran"
    if "BPRV" in texto or "RODOVIÁRIA" in texto or "RODOVIARIA" in texto:
        return "BPRv"
    if "BEPI" in texto or "INTERIOR" in texto:
        return "BEPI"
    if "BPGD" in texto or "GUARDA" in texto:
        return "BPGd"
    if "BPMA" in texto or "MEIO AMBIENTE" in texto:
        return "BPMA"
    if "BPTUR" in texto or "TURÍSTICO" in texto or "TURISTICO" in texto:
        return "BPTur"
        
    # BIEsp (Batalhões Integrados Especializados)
    biesp_match = re.search(r'(\d+)\s*º?\s*BIESP', texto)
    if biesp_match:
        num = biesp_match.group(1)
        return f"{num}º BIEsp"
        
    # CIPM (Companhias Independentes)
    cipm_match = re.search(r'(\d+)\s*ª?\s*CIPM', texto)
    if cipm_match:
        num = cipm_match.group(1)
        return f"{num}ª CIPM"

    # BPM (Batalhões de Polícia Militar)
    bpm_match = re.search(r'(\d+)\s*º?\s*BPM', texto)
    if bpm_match:
        num = bpm_match.group(1)
        return f"{num}º BPM"
        
    # Se for apenas um número isolado de 1 a 29 (Ex: "10" ou "10º")
    num_match = re.match(r'^(\d{1,2})\s*º?$', texto)
    if num_match:
        num = int(num_match.group(1))
        if 1 <= num <= 29:
            return f"{num}º BPM"

    # Limpeza genérica caso não caia em nenhuma regra específica
    nome_limpo = re.sub(r'[\\/*?:\[\]]', '', texto).strip()
    return nome_limpo[:31]

if arquivos_zip:
    tabelas_encontradas = []
    
    with st.spinner("Processando e organizando arquivos..."):
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
                                        
                                        PRIMEIRA_LINHA = " ".join([str(val).upper() for val in df.iloc[0].values]) if len(df) > 0 else ""
                                        if any(k in PRIMEIRA_LINHA for k in ["GRAD", "MAT", "NOME"]):
                                            df.columns = df.iloc[0]
                                            df = df[1:].reset_index(drop=True)
                                        
                                        df = df.loc[:, ~df.columns.duplicated()].copy()
                                        df.columns = [str(c).strip() if pd.notna(c) else f"Coluna_{i}" for i, c in enumerate(df.columns)]
                                        
                                        df.insert(0, 'Arquivo_Origem', os.path.basename(nome_arquivo))
                                        df.insert(0, 'ZIP_Origem', arquivo_zip.name)
                                        tabelas_encontradas.append(df)
                                        break
                            except Exception:
                                continue

    if tabelas_encontradas:
        df_final = pd.concat(tabelas_encontradas, ignore_index=True)
        df_final.dropna(how='all', inplace=True)
        
        # Identificar a coluna da OME
        coluna_ome = None
        for col in df_final.columns:
            col_upper = str(col).upper()
            if ("OME" in col_upper or "DESTINO" in col_upper) and "NOME" not in col_upper:
                coluna_ome = col
                break
                
        if not coluna_ome:
            for col in df_final.columns:
                col_upper = str(col).upper()
                if any(k in col_upper for k in ["UNIDADE", "LOTAÇÃO", "LOTACAO", "OPÇÃO", "OPCAO"]) and "NOME" not in col_upper:
                    coluna_ome = col
                    break

        buffer = io.BytesIO()
        with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
            # Aba Geral
            df_final.to_excel(writer, index=False, sheet_name='TODOS')
            
            # Separar por OME Padronizada
            if coluna_ome:
                # Criar uma coluna auxiliar temporária com a OME padronizada
                df_final['OME_Padronizada'] = df_final[coluna_ome].apply(padronizar_ome)
                
                grupos = df_final.groupby('OME_Padronizada')
                
                for nome_ome_padrao, df_grupo in grupos:
                    # Remover coluna auxiliar antes de salvar na aba da OME
                    df_aba = df_grupo.drop(columns=['OME_Padronizada'])
                    
                    nome_aba = nome_ome_padrao[:31]
                    
                    sheet_names_existentes = writer.sheets.keys()
                    count = 1
                    nome_aba_final = nome_aba
                    while nome_aba_final in sheet_names_existentes:
                        nome_aba_final = f"{nome_aba[:28]}_{count}"
                        count += 1
                    
                    df_aba.to_excel(writer, index=False, sheet_name=nome_aba_final)
        
        st.success("Sucesso! Relatórios unificados e OMEs padronizadas em abas exclusivas.")
        
        st.download_button(
            label="📥 Baixar Planilha Consolidada por OMEs",
            data=buffer.getvalue(),
            file_name="Relatorio_Policiais_Por_OME.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
    else:
        st.error("Nenhuma tabela nos padrões reconhecidos foi encontrada nos arquivos ZIP enviados.")
