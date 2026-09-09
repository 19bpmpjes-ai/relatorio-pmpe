import os
import zipfile
import io
import pandas as pd
import streamlit as st
import re

st.set_page_config(page_title="Processador de Relatórios PMPE", layout="wide")

st.title("📊 Processador de Relatórios SEI por OME")
st.write("Envie um ou **vários arquivos .zip** para consolidar e distribuir os policiais nas abas das OMEs desejadas.")

arquivos_zip = st.file_uploader("Arraste e solte os arquivos .ZIP aqui", type=["zip"], accept_multiple_files=True)

def extrair_omes(texto_ome):
    """
    Analisa a célula de OME/OPÇÕES, divide caso haja mais de uma opção selecionada
    e retorna uma lista de OMEs padronizadas.
    """
    if pd.isna(texto_ome):
        return ["SEM OME"]
        
    texto_original = str(texto_ome).upper().strip()
    if not texto_original or texto_original in ["NAN", "NONE"]:
        return ["SEM OME"]

    # Quebra o texto se houver múltiplas OMEs por barras, hifens, vírgulas, quebras de linha ou 'E'
    linhas = re.split(r'[\n\r,;/]|\s+E\s+|\s*-\s*', texto_original)
    omes_encontradas = set()

    for linha in linhas:
        texto = linha.strip()
        if not texto:
            continue

        # TJPE / Joana Bezerra / Tribunal de Justiça
        if any(k in texto for k in ["TJPE", "TJ-PE", "JOANA BEZERRA", "TRIBUNAL DE JUSTIÇA", "TRIBUNAL DE JUSTICA"]):
            omes_encontradas.add("TJPE")
        # TCE / Tribunal de Contas
        elif "TRIBUNAL DE CONTAS" in texto or "TCE" in texto:
            omes_encontradas.add("TCE")
        # Maria da Penha
        elif any(k in texto for k in ["MARIA DA PENHA", "PPMP", "PATRULHA MARIA DA PENHA"]):
            omes_encontradas.add("MARIA DA PENHA")
        # DASDH / Patrulha do Bairro / Patrulha Escolar / BGPESC / Sede DASDH
        elif any(k in texto for k in ["DASDH", "PATRULHA DO BAIRRO", "PATRULHA ESCOLAR", "PATRULHA ESCOLA", "ESCOLAR", "BGPESC", "SEDE DA DASDH", "DIRETORIA DE ASSISTENCIA"]):
            omes_encontradas.add("DASDH - PATRULHA DO BAIRRO")
        elif "BOPE" in texto:
            omes_encontradas.add("BOPE")
        elif "CHOQUE" in texto or "BPCHOQUE" in texto:
            omes_encontradas.add("BPChoque")
        elif "RADIOPATRULHA" in texto or "BPRP" in texto:
            omes_encontradas.add("BPRP")
        elif "RPMON" in texto or "MONTADA" in texto:
            omes_encontradas.add("RPMon")
        elif "BPTRAN" in texto or "TRÂNSITO" in texto or "TRANSITO" in texto:
            omes_encontradas.add("1º BPTran")
        elif "BPRV" in texto or "RODOVIÁRIA" in texto or "RODOVIARIA" in texto:
            omes_encontradas.add("BPRv")
        elif "BEPI" in texto or "INTERIOR" in texto:
            omes_encontradas.add("BEPI")
        elif "BPGD" in texto or "GUARDA" in texto:
            omes_encontradas.add("BPGd")
        elif "BPMA" in texto or "MEIO AMBIENTE" in texto:
            omes_encontradas.add("BPMA")
        elif "BPTUR" in texto or "TURÍSTICO" in texto or "TURISTICO" in texto:
            omes_encontradas.add("BPTur")
        else:
            # Captura de BIEsp
            biesp_match = re.search(r'(\d+)\s*º?\s*BIESP', texto)
            if biesp_match:
                omes_encontradas.add(f"{biesp_match.group(1)}º BIEsp")
                continue

            # Captura de CIPM
            cipm_match = re.search(r'(\d+)\s*ª?\s*CIPM', texto)
            if cipm_match:
                omes_encontradas.add(f"{cipm_match.group(1)}ª CIPM")
                continue

            # Captura de BPM
            bpm_match = re.search(r'(\d+)\s*º?\s*BPM', texto)
            if bpm_match:
                omes_encontradas.add(f"{bpm_match.group(1)}º BPM")
                continue

            # Captura de número isolado de 1 a 29 (Ex: "1BPM" ou "19BPM")
            num_match = re.search(r'\b(\d{1,2})\s*º?\s*(BPM)?\b', texto)
            if num_match:
                num = int(num_match.group(1))
                if 1 <= num <= 29:
                    omes_encontradas.add(f"{num}º BPM")
                    continue

            # Limpeza genérica para outros casos
            nome_limpo = re.sub(r'[\\/*?:\[\]]', '', texto).strip()
            if nome_limpo and len(nome_limpo) > 2:
                omes_encontradas.add(nome_limpo[:31])

    return list(omes_encontradas) if omes_encontradas else ["SEM OME"]

if arquivos_zip:
    tabelas_encontradas = []
    
    with st.spinner("Processando e consolidando tabelas..."):
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
                                        
                                        # Adiciona apenas o Arquivo_Origem (sem ZIP_Origem)
                                        df.insert(0, 'Arquivo_Origem', os.path.basename(nome_arquivo))
                                        tabelas_encontradas.append(df)
                                        break
                            except Exception:
                                continue

    if tabelas_encontradas:
        df_final = pd.concat(tabelas_encontradas, ignore_index=True)
        df_final.dropna(how='all', inplace=True)
        
        # Identificação de todas as colunas que podem conter informações de OME/Opções
        colunas_opcao = []
        for col in df_final.columns:
            col_upper = str(col).upper()
            if any(k in col_upper for k in ["OPÇ", "OPC", "OME", "DESTINO", "UNIDADE", "LOTAÇÃO", "LOTACAO"]) and "NOME" not in col_upper:
                colunas_opcao.append(col)

        buffer = io.BytesIO()
        with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
            
            mecanismo_abas = {}
            
            for idx, row in df_final.iterrows():
                # Concatena o conteúdo de todas as colunas relativas a Opções/OME encontradas na linha
                texto_linha_opcoes = " ".join([str(row[c]) for c in colunas_opcao if pd.notna(row[c])])
                
                lista_omes = extrair_omes(texto_linha_opcoes)
                
                for ome in lista_omes:
                    chave_ome = str(ome).strip().upper()
                    if chave_ome not in mecanismo_abas:
                        mecanismo_abas[chave_ome] = []
                    mecanismo_abas[chave_ome].append(row)
            
            # Gerar abas sem duplicidades
            for nome_ome, lista_rows in mecanismo_abas.items():
                df_aba = pd.DataFrame(lista_rows)
                nome_aba = nome_ome[:31]
                if not nome_aba:
                    nome_aba = "SEM OME"
                
                df_aba.to_excel(writer, index=False, sheet_name=nome_aba)
        
        st.success("Sucesso! Planilha processada e policiais devidamente distribuídos em suas respectivas OMEs.")
        
        st.download_button(
            label="📥 Baixar Planilha Consolidada por OMEs",
            data=buffer.getvalue(),
            file_name="Relatorio_Policiais_Por_OME.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
    else:
        st.error("Nenhuma tabela nos padrões reconhecidos foi encontrada nos arquivos ZIP enviados.")
