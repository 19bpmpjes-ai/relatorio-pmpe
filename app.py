import os
import zipfile
import io
import pandas as pd
import streamlit as st
import re

st.set_page_config(page_title="Processador de Relatórios PMPE", layout="wide")

st.title("📊 Processador de Relatórios SEI por OME")
st.write("Envie um ou **vários arquivos .zip** para consolidar e organizar os policiais na ordem padronizada de colunas.")

arquivos_zip = st.file_uploader("Arraste e solte os arquivos .ZIP aqui", type=["zip"], accept_multiple_files=True)

def desduplicar_colunas(df):
    """Garante que não existam nomes de colunas duplicados na mesma tabela."""
    cols = pd.Series(df.columns)
    for dup in cols[cols.duplicated()].unique():
        cols[cols == dup] = [f"{dup}_{i}" if i != 0 else str(dup) for i in range(sum(cols == dup))]
    df.columns = cols
    return df

def padronizar_e_organizar_colunas(df):
    """
    Identifica de forma estrita as abreviações e variações,
    mapeando tudo para a ordem exata das 9 colunas principais.
    """
    novas_colunas = {}
    
    for col in df.columns:
        c_upper = str(col).upper().strip()
        c_limpo = re.sub(r'[^A-Z0-9]', '', c_upper) # Remove pontos, hífens, espaços
        
        # Coluna 2: Graduação
        if any(k in c_limpo for k in ["GRAD", "POSTO", "PATENTE", "POSTOGRAD"]) and "GRADUAÇÃO" not in novas_colunas.values():
            novas_colunas[col] = "GRADUAÇÃO"
        # Coluna 3: Matrícula
        elif any(k in c_limpo for k in ["MATR", "MATI", "MAT", "MATRICULA", "MATRIC"]) and "MATRÍCULA" not in novas_colunas.values():
            novas_colunas[col] = "MATRÍCULA"
        # Coluna 4: Nome
        elif ("NOME" in c_limpo or "NOM" in c_limpo or "POLICIAL" in c_limpo) and "NOME COMPLETO" not in novas_colunas.values():
            novas_colunas[col] = "NOME COMPLETO"
        # Coluna 5: Telefone
        elif any(k in c_limpo for k in ["TEL", "FONE", "CEL", "CELULAR", "CONTATO", "TELEF"]) and "TELEFONE" not in novas_colunas.values():
            novas_colunas[col] = "TELEFONE"
        # Coluna 6: Motorista / Função
        elif any(k in c_limpo for k in ["MOT", "MOTORISTA", "FUNCAO", "FUNCA", "MODALID", "CARGO", "CNH"]) and "MOTORISTA / FUNÇÃO" not in novas_colunas.values():
            novas_colunas[col] = "MOTORISTA / FUNÇÃO"
        # Coluna 7: Quant. Cotas
        elif any(k in c_limpo for k in ["COTA", "COTAS", "QUANT", "QTSERVI", "QTSERV", "QTD", "SOLICITADA"]) and "QUANT. COTAS" not in novas_colunas.values():
            novas_colunas[col] = "QUANT. COTAS"
        # Coluna 8: Disponibilidade / Turno
        elif any(k in c_limpo for k in ["DISP", "TURNO", "DIAS", "HORA", "HORARIO", "DISPONIBILIDADE"]) and "DISPONIBILIDADE / TURNO" not in novas_colunas.values():
            novas_colunas[col] = "DISPONIBILIDADE / TURNO"
        # Coluna 9: OME / Opções
        elif any(k in c_limpo for k in ["OPC", "OME", "DESTINO", "UNIDADE", "LOTACAO", "PREENCHER", "BATALHAO"]) and "OME / OPÇÕES" not in novas_colunas.values():
            novas_colunas[col] = "OME / OPÇÕES"
            
    df = df.rename(columns=novas_colunas)
    return df

def extrair_omes_da_linha(row):
    """
    Varre os valores reais da linha inteira independentemente do nome da coluna.
    Garante a captura de BPM, CIPM, BIESP e Especializadas.
    """
    valores_linha = [str(val).upper().strip() for val in row.values if pd.notna(val)]
    texto_original = " ".join(valores_linha)
    
    if not texto_original or set(valores_linha).issubset({"NAN", "NONE", "****", "***"}):
        return ["SEM OME"]

    omes_encontradas = set()

    # 1. Unidades Especializadas
    if any(k in texto_original for k in ["TJPE", "TJ-PE", "JOANA BEZERRA", "TRIBUNAL DE JUSTIÇA", "TRIBUNAL DE JUSTICA"]):
        omes_encontradas.add("TJPE")
    if "TRIBUNAL DE CONTAS" in texto_original or "TCE" in texto_original:
        omes_encontradas.add("TCE")
    if any(k in texto_original for k in ["MARIA DA PENHA", "PPMP", "PATRULHA MARIA DA PENHA"]):
        omes_encontradas.add("MARIA DA PENHA")
    if any(k in texto_original for k in ["DASDH", "PATRULHA ESCOLAR", "PATRULHA ESCOLA", "ESCOLAR", "BGPESC", "SEDE DA DASDH", "DIRETORIA DE ASSISTENCIA"]):
        omes_encontradas.add("DASDH - PATRULHA ESCOLAR")
    if "BOPE" in texto_original:
        omes_encontradas.add("BOPE")
    if "CHOQUE" in texto_original or "BPCHOQUE" in texto_original:
        omes_encontradas.add("BPChoque")
    if "RADIOPATRULHA" in texto_original or "BPRP" in texto_original:
        omes_encontradas.add("BPRP")
    if "RPMON" in texto_original or "MONTADA" in texto_original:
        omes_encontradas.add("RPMon")
    if "BPTRAN" in texto_original or "TRÂNSITO" in texto_original or "TRANSITO" in texto_original:
        omes_encontradas.add("1º BPTran")
    if "BPRV" in texto_original or "RODOVIÁRIA" in texto_original or "RODOVIARIA" in texto_original:
        omes_encontradas.add("BPRv")
    if "BEPI" in texto_original or "INTERIOR" in texto_original:
        omes_encontradas.add("BEPI")
    if "BPGD" in texto_original or "GUARDA" in texto_original:
        omes_encontradas.add("BPGd")
    if "BPMA" in texto_original or "MEIO AMBIENTE" in texto_original:
        omes_encontradas.add("BPMA")
    if "BPTUR" in texto_original or "TURÍSTICO" in texto_original or "TURISTICO" in texto_original:
        omes_encontradas.add("BPTur")

    # 2. Busca por Batalhões (Ex: 3º BPM, 3ºBPM, 12º BPM, 10º BPM)
    bpm_matches = re.findall(r'(\d+)\s*[^A-Z0-9]?\s*BPM', texto_original)
    for num in bpm_matches:
        omes_encontradas.add(f"{num}º BPM")

    # 3. Busca por BIESP (Ex: 1º BIESP)
    biesp_matches = re.findall(r'(\d+)\s*[^A-Z0-9]?\s*BIESP', texto_original)
    for num in biesp_matches:
        omes_encontradas.add(f"{num}º BIEsp")

    # 4. Busca por CIPM (Ex: 10ª CIPM)
    cipm_matches = re.findall(r'(\d+)\s*[^A-Z0-9]?\s*CIPM', texto_original)
    for num in cipm_matches:
        omes_encontradas.add(f"{num}ª CIPM")

    # 5. Múltiplas opções por barra (Ex: "6/12/13/18")
    if not omes_encontradas:
        barras_matches = re.findall(r'\b(\d{1,2}(?:\/\d{1,2})+)\b', texto_original)
        for grupo in barras_matches:
            numeros = grupo.split('/')
            for n in numeros:
                if n.isdigit() and 1 <= int(n) <= 30:
                    omes_encontradas.add(f"{int(n)}º BPM")

    # 6. Companhias e CPMs isoladas (Ex: "1 CPM")
    if not omes_encontradas:
        cpm_matches = re.findall(r'(\d+)\s*[^A-Z0-9]?\s*(?:CPM|CIA)', texto_original)
        for num in cpm_matches:
            omes_encontradas.add(f"{num}ª CPM")

    return list(omes_encontradas) if omes_encontradas else ["SEM OME"]

if arquivos_zip:
    tabelas_encontradas = []
    
    with st.spinner("Unificando colunas e reorganizando policiais por OME..."):
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
                                        
                                        df.columns = [str(c).strip() if pd.notna(c) else f"Coluna_{i}" for i, c in enumerate(df.columns)]
                                        
                                        df = desduplicar_colunas(df)
                                        df = padronizar_e_organizar_colunas(df)
                                        
                                        df.insert(0, 'ARQUIVO ORIGEM', os.path.basename(nome_arquivo))
                                        tabelas_encontradas.append(df)
                                        break
                            except Exception:
                                continue

    if tabelas_encontradas:
        df_final = pd.concat(tabelas_encontradas, ignore_index=True, axis=0)
        df_final.dropna(how='all', inplace=True)

        df_final = padronizar_e_organizar_colunas(df_final)

        # LIMPEZA DA MATRÍCULA SEM USAR LAMBDA: Compatível com Python 3.14/Pandas
        if "MATRÍCULA" in df_final.columns:
            df_final["MATRÍCULA"] = df_final["MATRÍCULA"].astype(str).str.replace(r'[^0-9]', '', regex=True)

        ordem_estrita = [
            "ARQUIVO ORIGEM",            # Coluna 1
            "GRADUAÇÃO",                 # Coluna 2
            "MATRÍCULA",                 # Coluna 3
            "NOME COMPLETO",             # Coluna 4
            "TELEFONE",                  # Coluna 5
            "MOTORISTA / FUNÇÃO",        # Coluna 6
            "QUANT. COTAS",              # Coluna 7
            "DISPONIBILIDADE / TURNO",   # Coluna 8
            "OME / OPÇÕES"               # Coluna 9
        ]
        
        colunas_existentes = [c for c in ordem_estrita if c in df_final.columns]
        outras_colunas = [c for c in df_final.columns if c not in ordem_estrita]
        
        df_final = df_final[colunas_existentes + outras_colunas]

        buffer = io.BytesIO()
        with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
            
            mecanismo_abas = {}
            
            for idx, row in df_final.iterrows():
                grad_val = str(row.get("GRADUAÇÃO", "")).upper()
                nome_val = str(row.get("NOME COMPLETO", "")).upper()
                if "GRAD" in grad_val or "NOME" in nome_val or grad_val == "***":
                    continue

                lista_omes = extrair_omes_da_linha(row)
                
                for ome in lista_omes:
                    chave_ome = str(ome).strip().upper()
                    if chave_ome not in mecanismo_abas:
                        mecanismo_abas[chave_ome] = []
                    mecanismo_abas[chave_ome].append(row)
            
            for nome_ome, lista_rows in mecanismo_abas.items():
                df_aba = pd.DataFrame(lista_rows)
                nome_aba = nome_ome[:31]
                if not nome_aba:
                    nome_aba = "SEM OME"
                
                df_aba.to_excel(writer, index=False, sheet_name=nome_aba)
        
        st.success("Sucesso! Matrículas limpas (apenas números) e policiais organizados por OME.")
        
        st.download_button(
            label="📥 Baixar Planilha Consolidada Corrigida",
            data=buffer.getvalue(),
            file_name="Relatorio_Policiais_Por_OME_Corrigido.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
    else:
        st.error("Nenhuma tabela nos padrões reconhecidos foi encontrada nos arquivos ZIP enviados.")
