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

st.title("Active Recall Study Tool")

if 'question_index' not in st.session_state:
    st.session_state.question_index = 0
if 'show_result' not in st.session_state:
    st.session_state.show_result = False
if 'user_answer' not in st.session_state:
    st.session_state.user_answer = ""
if 'similarity_score' not in st.session_state:
    st.session_state.similarity_score = 0
if 'df' not in st.session_state:
    st.session_state.df = None
if 'worksheet' not in st.session_state:
    st.session_state.worksheet = None
if 'sheet_url' not in st.session_state:
    st.session_state.sheet_url = ""


def load_spreadsheet(url):
    """Load data from Google Sheets."""
    try:
        client = get_gspread_client()
        spreadsheet = client.open_by_url(url)
        worksheet = spreadsheet.sheet1
        data = worksheet.get_all_records()
        df = pd.DataFrame(data)
        return df, worksheet
    except Exception as e:
        st.error(f"Error loading spreadsheet: {str(e)}")
        return None, None


def update_sheet(worksheet, row_index, resultado, data):
    """Update the Google Sheet with the result and date."""
    try:
        worksheet.update_cell(row_index + 2, 4, resultado)
        worksheet.update_cell(row_index + 2, 5, data)
        return True
    except Exception as e:
        st.error(f"Error updating sheet: {str(e)}")
        return False


def next_question():
    """Move to the next question."""
    st.session_state.question_index += 1
    st.session_state.show_result = False
    st.session_state.user_answer = ""
    st.session_state.similarity_score = 0


def submit_answer():
    """Submit answer and calculate similarity."""
    st.session_state.show_result = True


def record_result(resultado):
    """Record the result and move to the next question."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    if update_sheet(st.session_state.worksheet, st.session_state.question_index, resultado, timestamp):
        st.session_state.df.at[st.session_state.question_index, 'Resultado'] = resultado
        st.session_state.df.at[st.session_state.question_index, 'Data'] = timestamp
        next_question()


with st.sidebar:
    st.header("Configuration")
    sheet_url = st.text_input(
        "Google Sheet URL",
        value=st.session_state.sheet_url,
        placeholder="https://docs.google.com/spreadsheets/d/...",
        help="Paste the full URL of your Google Sheet with study questions"
    )
    
    if st.button("Load Sheet", type="primary"):
        if sheet_url:
            st.session_state.sheet_url = sheet_url
            with st.spinner("Loading spreadsheet..."):
                df, worksheet = load_spreadsheet(sheet_url)
                if df is not None and worksheet is not None:
                    required_columns = ['Assunto', 'Pergunta', 'Resposta', 'Resultado', 'Data']
                    missing_columns = [col for col in required_columns if col not in df.columns]
                    
                    if missing_columns:
                        st.error(f"Missing columns: {', '.join(missing_columns)}")
                    else:
                        st.session_state.df = df
                        st.session_state.worksheet = worksheet
                        st.session_state.question_index = 0
                        st.session_state.show_result = False
                        st.success(f"Loaded {len(df)} questions!")
        else:
            st.warning("Please enter a Google Sheet URL")
    
    if st.session_state.df is not None:
        st.divider()
        st.subheader("Progress")
        total = len(st.session_state.df)
        current = st.session_state.question_index + 1
        st.progress(min(current / total, 1.0))
        st.caption(f"Question {min(current, total)} of {total}")

if st.session_state.df is None:
    st.info("Please enter your Google Sheet URL in the sidebar and click 'Load Sheet' to begin.")
    st.markdown("""
    ### Expected Sheet Structure
    Your Google Sheet should have the following columns:
    1. **Assunto** - Subject/Topic
    2. **Pergunta** - Question
    3. **Resposta** - Reference Answer
    4. **Resultado** - Result (will be updated by the app)
    5. **Data** - Date (will be updated by the app)
    """)
else:
    df = st.session_state.df
    
    if st.session_state.question_index >= len(df):
        st.success("You've completed all questions!")
        st.balloons()
        
        if st.button("Start Over"):
            st.session_state.question_index = 0
            st.session_state.show_result = False
            st.session_state.user_answer = ""
            st.rerun()
    else:
        current_row = df.iloc[st.session_state.question_index]
        
        st.subheader(f"Subject: {current_row['Assunto']}")
        
        st.markdown("### Question")
        st.markdown(f"> {current_row['Pergunta']}")
        
        st.markdown("### Your Answer")
        user_answer = st.text_area(
            "Type your answer here:",
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
                        submit_answer()
                        st.rerun()
                    else:
                        st.warning("Please type an answer before submitting.")
            with col2:
                if st.button("Skip Question", use_container_width=True):
                    next_question()
                    st.rerun()
        else:
            reference_answer = str(current_row['Resposta'])
            similarity = fuzz.token_sort_ratio(user_answer.lower(), reference_answer.lower())
            st.session_state.similarity_score = similarity
            
            st.markdown("---")
            st.markdown("### Evaluation")
            
            if similarity >= 80:
                st.success(f"Similarity Score: {similarity}%")
            elif similarity >= 50:
                st.warning(f"Similarity Score: {similarity}%")
            else:
                st.error(f"Similarity Score: {similarity}%")
            
            st.markdown("### Reference Answer")
            st.info(reference_answer)
            
            st.markdown("### How did you do?")
            col1, col2, col3 = st.columns(3)
            
            with col1:
                if st.button("Acertei", type="primary", use_container_width=True, help="I got it right"):
                    record_result("Acertei")
                    st.rerun()
            
            with col2:
                if st.button("Posso melhorar", use_container_width=True, help="I can improve - partial answer"):
                    record_result("Posso melhorar")
                    st.rerun()
            
            with col3:
                if st.button("Errei", use_container_width=True, help="I got it wrong"):
                    record_result("Errei")
                    st.rerun()
