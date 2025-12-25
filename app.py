import streamlit as st
import pandas as pd
from datetime import datetime
from thefuzz import fuzz
from google_sheets_auth import get_gspread_client

st.set_page_config(
    page_title="Active Recall Study Tool",
    page_icon="📚",
    layout="centered"
)

SHEETS_MAPPING = {
    "Direito": "https://docs.google.com/spreadsheets/d/1qb9d3qNAJBfcluxTHNsdRDdE1pZW7LS0EyzHlobRVDk/edit?usp=drive_link",
    "Geografia": "https://docs.google.com/spreadsheets/d/1U8js8DcnpMwANwIoBCSlPgH0BPEx2nQwRSBVssflCDs/edit?usp=drive_link",
    "História Mundial": "https://docs.google.com/spreadsheets/d/1XNhhnjlCp7xB3eCkwHyiG8_hPrmT4AXk-r_8YSsAYWg/edit?usp=sharing",
    "História do Brasil": "https://docs.google.com/spreadsheets/d/16LMjWZnez89To_0jNFWf_V9TcsKhUqTcxQP8VF1FL_8/edit?usp=sharing",
    "Política Internacional": "https://docs.google.com/spreadsheets/d/1uiXehNXzYwJ0BM8pLThfhcH7f7Cr4d7BhSQ3KO4mQEU/edit?usp=drive_link",
    "Economia": "https://docs.google.com/spreadsheets/d/1r3J0KnmoEs-pOD-oKuhogKGvMw7N26E1QeFENswEc3Y/edit?usp=drive_link",
    "Francês": "https://docs.google.com/spreadsheets/d/1O8aEGmkoXtpN0wLc0Uypk6D741Udk1V3XXUw0Wa25is/edit?usp=drive_link",
    "Inglês": "https://docs.google.com/spreadsheets/d/12VQFmP_42aKJIN2he4HzPobl79_icS0yqy5G4AZD_P4/edit?usp=drive_link"
}

if 'question_index' not in st.session_state:
    st.session_state.question_index = 0
if 'show_result' not in st.session_state:
    st.session_state.show_result = False
if 'user_answer' not in st.session_state:
    st.session_state.user_answer = ""
if 'similarity_score' not in st.session_state:
    st.session_state.similarity_score = 0
if 'filtered_df' not in st.session_state:
    st.session_state.filtered_df = None
if 'worksheet' not in st.session_state:
    st.session_state.worksheet = None
if 'selected_disciplina' not in st.session_state:
    st.session_state.selected_disciplina = None
if 'selected_tema' not in st.session_state:
    st.session_state.selected_tema = None
if 'selected_assunto' not in st.session_state:
    st.session_state.selected_assunto = None
if 'original_df' not in st.session_state:
    st.session_state.original_df = None
if 'row_mapping' not in st.session_state:
    st.session_state.row_mapping = []


@st.cache_data(ttl=300)
def get_worksheet_titles(sheet_url):
    """Get all worksheet titles from a spreadsheet."""
    try:
        client = get_gspread_client()
        spreadsheet = client.open_by_url(sheet_url)
        return [ws.title for ws in spreadsheet.worksheets()]
    except Exception as e:
        st.error(f"Error loading worksheets: {str(e)}")
        return []


@st.cache_data(ttl=300)
def load_worksheet_data(sheet_url, worksheet_title):
    """Load data from a specific worksheet."""
    try:
        client = get_gspread_client()
        spreadsheet = client.open_by_url(sheet_url)
        worksheet = spreadsheet.worksheet(worksheet_title)
        data = worksheet.get_all_records()
        df = pd.DataFrame(data)
        return df
    except Exception as e:
        st.error(f"Error loading worksheet data: {str(e)}")
        return None


def get_worksheet_for_update(sheet_url, worksheet_title):
    """Get worksheet object for updating (not cached)."""
    try:
        client = get_gspread_client()
        spreadsheet = client.open_by_url(sheet_url)
        return spreadsheet.worksheet(worksheet_title)
    except Exception as e:
        st.error(f"Error accessing worksheet: {str(e)}")
        return None


def update_sheet(worksheet, original_row_index, resultado, data):
    """Update the Google Sheet with the result and date."""
    try:
        worksheet.update_cell(original_row_index + 2, 4, resultado)
        worksheet.update_cell(original_row_index + 2, 5, data)
        return True
    except Exception as e:
        st.error(f"Error updating sheet: {str(e)}")
        return False


def reset_quiz_state():
    """Reset quiz state when filters change."""
    st.session_state.question_index = 0
    st.session_state.show_result = False
    st.session_state.user_answer = ""
    st.session_state.similarity_score = 0


def next_question():
    """Move to the next question."""
    st.session_state.question_index += 1
    st.session_state.show_result = False
    st.session_state.user_answer = ""
    st.session_state.similarity_score = 0


def record_result(resultado):
    """Record the result and move to the next question."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    original_row_index = st.session_state.row_mapping[st.session_state.question_index]
    
    if update_sheet(st.session_state.worksheet, original_row_index, resultado, timestamp):
        st.session_state.filtered_df.at[st.session_state.question_index, 'Resultado'] = resultado
        st.session_state.filtered_df.at[st.session_state.question_index, 'Data'] = timestamp
        if st.session_state.original_df is not None:
            st.session_state.original_df.at[original_row_index, 'Resultado'] = resultado
            st.session_state.original_df.at[original_row_index, 'Data'] = timestamp
        next_question()


st.title("Active Recall Study Tool")

with st.sidebar:
    st.header("Configuração")
    
    disciplinas = list(SHEETS_MAPPING.keys())
    selected_disciplina = st.selectbox(
        "Selecione a disciplina",
        options=disciplinas,
        index=0,
        key="disciplina_select"
    )
    
    if selected_disciplina != st.session_state.selected_disciplina:
        st.session_state.selected_disciplina = selected_disciplina
        st.session_state.selected_tema = None
        st.session_state.selected_assunto = None
        st.session_state.original_df = None
        st.session_state.filtered_df = None
        st.session_state.worksheet = None
        reset_quiz_state()
        load_worksheet_data.clear()
        get_worksheet_titles.clear()
    
    sheet_url = SHEETS_MAPPING[selected_disciplina]
    worksheet_titles = get_worksheet_titles(sheet_url)
    
    if worksheet_titles:
        selected_tema = st.selectbox(
            "Selecione o tema",
            options=worksheet_titles,
            index=0,
            key="tema_select"
        )
        
        if selected_tema != st.session_state.selected_tema:
            st.session_state.selected_tema = selected_tema
            st.session_state.selected_assunto = None
            st.session_state.original_df = None
            st.session_state.filtered_df = None
            reset_quiz_state()
            load_worksheet_data.clear()
        
        if st.session_state.original_df is None:
            with st.spinner("Carregando dados..."):
                df = load_worksheet_data(sheet_url, selected_tema)
                if df is not None:
                    required_columns = ['Assunto', 'Pergunta', 'Resposta', 'Resultado', 'Data']
                    missing_columns = [col for col in required_columns if col not in df.columns]
                    
                    if missing_columns:
                        st.error(f"Colunas faltando: {', '.join(missing_columns)}")
                    else:
                        st.session_state.original_df = df.copy()
                        st.session_state.worksheet = get_worksheet_for_update(sheet_url, selected_tema)
        
        if st.session_state.original_df is not None:
            unique_assuntos = sorted(st.session_state.original_df['Assunto'].dropna().unique().tolist())
            assunto_options = ["Tudo"] + unique_assuntos
            
            selected_assunto = st.selectbox(
                "Escolha o assunto",
                options=assunto_options,
                index=0,
                key="assunto_select"
            )
            
            if selected_assunto != st.session_state.selected_assunto:
                st.session_state.selected_assunto = selected_assunto
                reset_quiz_state()
                
                if selected_assunto == "Tudo":
                    st.session_state.filtered_df = st.session_state.original_df.reset_index(drop=True)
                    st.session_state.row_mapping = list(range(len(st.session_state.original_df)))
                else:
                    mask = st.session_state.original_df['Assunto'] == selected_assunto
                    original_indices = st.session_state.original_df[mask].index.tolist()
                    st.session_state.filtered_df = st.session_state.original_df[mask].reset_index(drop=True)
                    st.session_state.row_mapping = original_indices
            
            st.divider()
            st.subheader("Progresso")
            if st.session_state.filtered_df is not None and len(st.session_state.filtered_df) > 0:
                total = len(st.session_state.filtered_df)
                current = st.session_state.question_index + 1
                st.progress(min(current / total, 1.0))
                st.caption(f"Questão {min(current, total)} de {total}")

if st.session_state.filtered_df is None or len(st.session_state.filtered_df) == 0:
    if st.session_state.original_df is None:
        st.info("Selecione uma disciplina e tema na barra lateral para começar.")
    else:
        st.warning("Nenhuma questão encontrada com os filtros selecionados.")
else:
    df = st.session_state.filtered_df
    
    if st.session_state.question_index >= len(df):
        st.success("Você completou todas as questões!")
        st.balloons()
        
        if st.button("Recomeçar"):
            reset_quiz_state()
            st.rerun()
    else:
        current_row = df.iloc[st.session_state.question_index]
        
        st.subheader(f"Assunto: {current_row['Assunto']}")
        
        st.markdown("### Pergunta")
        st.markdown(f"> {current_row['Pergunta']}")
        
        st.markdown("### Sua Resposta")
        user_answer = st.text_area(
            "Digite sua resposta aqui:",
            value=st.session_state.user_answer,
            height=150,
            key="answer_input",
            label_visibility="collapsed"
        )
        st.session_state.user_answer = user_answer
        
        if not st.session_state.show_result:
            col1, col2 = st.columns([1, 1])
            with col1:
                if st.button("Enviar Resposta", type="primary", use_container_width=True):
                    if user_answer.strip():
                        st.session_state.show_result = True
                        st.rerun()
                    else:
                        st.warning("Por favor, digite uma resposta antes de enviar.")
            with col2:
                if st.button("Pular Questão", use_container_width=True):
                    next_question()
                    st.rerun()
        else:
            reference_answer = str(current_row['Resposta'])
            similarity = fuzz.token_sort_ratio(user_answer.lower(), reference_answer.lower())
            st.session_state.similarity_score = similarity
            
            st.markdown("---")
            st.markdown("### Avaliação")
            
            if similarity >= 80:
                st.success(f"Pontuação de Similaridade: {similarity}%")
            elif similarity >= 50:
                st.warning(f"Pontuação de Similaridade: {similarity}%")
            else:
                st.error(f"Pontuação de Similaridade: {similarity}%")
            
            st.markdown("### Resposta de Referência")
            st.info(reference_answer)
            
            st.markdown("### Como você se saiu?")
            col1, col2, col3 = st.columns(3)
            
            with col1:
                if st.button("Acertei", type="primary", use_container_width=True, help="Acertei a resposta"):
                    record_result("Acertei")
                    st.rerun()
            
            with col2:
                if st.button("Posso melhorar", use_container_width=True, help="Resposta parcial"):
                    record_result("Posso melhorar")
                    st.rerun()
            
            with col3:
                if st.button("Errei", use_container_width=True, help="Errei a resposta"):
                    record_result("Errei")
                    st.rerun()
