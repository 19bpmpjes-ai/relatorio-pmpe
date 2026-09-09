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
    Identifica de forma flexível as colunas principais e renomeia.
    """
    novas_colunas = {}
    
    for col in df.columns:
        c_upper = str(col).upper().strip()
        c_limpo = re.sub(r'[^A-Z0-9]', '', c_upper)
        
        if any(k in c_limpo for k in ["GRAD", "POSTO", "PATENTE", "POSTOGRAD"]) and "GRADUAÇÃO" not in novas_colunas.values():
            novas_colunas[col] = "GRADUAÇÃO"
        elif any(k in c_limpo for k in ["MATR", "MATI", "MAT", "MATRICULA", "MATRIC"]) and "MATRÍCULA" not in novas_colunas.values():
            novas_colunas[col] = "MATRÍCULA"
        elif ("NOME" in c_limpo or "NOM" in c_limpo or "POLICIAL" in c_limpo) and "NOME COMPLETO" not in novas_colunas.values():
            novas_colunas[col] = "NOME COMPLETO"
        elif any(k in c_limpo for k in ["TEL", "FONE", "CEL", "CELULAR", "CONTATO", "TELEF"]) and "TELEFONE" not in novas_colunas.values():
            novas_colunas[col] = "TELEFONE"
        elif any(k in c_limpo for k in ["MOT", "MOTORISTA", "FUNCAO", "FUNCA", "MODALID", "CARGO", "CNH"]) and "MOTORISTA / FUNÇÃO" not in novas_colunas.values():
            novas_colunas[col] = "MOTORISTA / FUNÇÃO"
        elif any(k in c_limpo for k in ["COTA", "COTAS", "QUANT", "QTSERVI", "QTSERV", "QTD", "SOLICITADA"]) and "QUANT. COTAS" not in novas_colunas.values():
            novas_colunas[col] = "QUANT. COTAS"
        elif any(k in c_limpo for k in ["DISP", "TURNO", "DIAS", "HORA", "HORARIO", "DISPONIBILIDADE"]) and "DISPONIBILIDADE / TURNO" not in novas_colunas.values():
            novas_colunas[col] = "DISPONIBILIDADE / TURNO"
        elif any(k in c_limpo for k in ["OPC", "OME", "DESTINO", "UNIDADE", "LOTACAO", "PREENCHER", "BATALHAO"]) and "OME / OPÇÕES" not in novas_colunas.values():
            novas_colunas[col] = "OME / OPÇÕES"
            
    df = df.rename(columns=novas_colunas)
    return df

def extrair_omes_da_linha(row):
    """
    Varre TODAS as células da linha (ignorando dados pessoais/origem)
    para extrair Batalhões, Companhias e Opções com precisão cirúrgica.
    """
    texto_linha = []
    
    colunas_pessoais = ["ARQUIVO ORIGEM", "GRADUAÇÃO", "MATRÍCULA", "NOME COMPLETO", "TELEFONE"]
    
    for col, val in row.items():
        if col not in colunas_pessoais and pd.notna(val):
            texto_linha.append(str(val).upper())
            
    texto_original = " ".join(texto_linha).strip()
    
    # Se a linha for apenas sujeira de cabeçalho (*** ou MAT. NOME GUERRA)
    if not texto_original or texto_original in ["NAN", "NONE"] or "***" in texto_original or "NOME GUERRA" in texto_original:
        return []

    omes_encontradas = set()

    # 1. Unidades Especializadas
    if any(k in texto_original for k in ["TJPE", "TJ-PE", "JOANA BEZERRA", "TRIBUNAL DE JUSTIÇA"]):
        omes_encontradas.add("TJPE")
    if "TCE" in texto_original or "TRIBUNAL DE CONTAS" in texto_original:
        omes_encontradas.add("TCE")
    if any(k in texto_original for k in ["MARIA DA PENHA", "PPMP"]):
        omes_encontradas.add("MARIA DA PENHA")
    if any(k in texto_original for k in ["DASDH", "PATRULHA ESCOLAR", "PATRULHA ESCOLA", "ESCOLAR"]):
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
    if "BEPI" in texto_original:
        omes_encontradas.add("BEPI")
    if "BPGD" in texto_original:
        omes_encontradas.add("BPGd")
    if "BPMA" in texto_original:
        omes_encontradas.add("BPMA")
    if "BPTUR" in texto_original:
        omes_encontradas.add("BPTur")

    # 2. Padrões de BPM / BIESP / CIPM / CPM (Ex: 3º BPM, 12º BPM, 10º BPM, 1 CPM)
    bpm_matches = re.findall(r'(\d+)\s*[º°ª]?\s*BPM', texto_original)
    for num in bpm_matches:
        omes_encontradas.add(f"{num}º BPM")

    biesp_matches = re.findall(r'(\d+)\s*[º°ª]?\s*BIESP', texto_original)
    for num in biesp_matches:
        omes_encontradas.add(f"{num}º BIEsp")

    cipm_matches = re.findall(r'(\d+)\s*[º°ª]?\s*CIPM', texto_original)
    for num in cipm_matches:
        omes_encontradas.add(f"{num}ª CIPM")

    cpm_matches = re.findall(r'(\d+)\s*[º°ª]?\s*CPM', texto_original)
    for num in cpm_matches:
        omes_encontradas.add(f"{num}ª CPM")

    # 3. Padrão de múltiplos números separados por barra (Ex: "6/12/13/18")
    barras_matches = re.findall(r'\b(\d{1,2}(?:/\d{1,2})+)\b', texto_original)
    for grupo in barras_matches:
        numeros = grupo.split('/')
        for n in numeros:
            if n.isdigit() and 1 <= int(n) <= 30:
                omes_encontradas.add(f"{int(n)}º BPM")

    return list(omes_encontradas) if omes_encontradas else ["SEM OME"]

if arquivos_zip:
    tabelas_encontradas = []
    
    with st.spinner("Varrendo todas as colunas e organizando policiais por OME..."):
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
                lista_omes = extrair_omes_da_linha(row)
                
                # Ignora linhas de cabeçalho repetido dentro do HTML
                if not lista_omes:
                    continue
                
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
        
        st.success("Sucesso! Todos os Batalhões (3º BPM, 10º BPM, 12º BPM, 1 CPM, etc.) foram extraídos e alocados nas suas abas de destino.")
        
        st.download_button(
            label="📥 Baixar Planilha Consolidada e Totalmente Corrigida",
            data=buffer.getvalue(),
            file_name="Relatorio_Policiais_Por_OME_Final.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
    else:
        st.error("Nenhuma tabela nos padrões reconhecidos foi encontrada nos arquivos ZIP enviados.")
