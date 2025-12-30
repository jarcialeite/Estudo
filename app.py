import streamlit as st
import pandas as pd
import os
import json
from datetime import datetime, timedelta
from thefuzz import fuzz
import matplotlib.pyplot as plt
import streamlit.components.v1 as components
from openai import OpenAI
import gspread
from oauth2client.service_account import ServiceAccountCredentials

import time
import html
from functools import wraps

# --- COLAR LOGO APÓS OS IMPORTS E ANTES DO RESTO DO CÓDIGO ---

def evaluate_answer_ai(question, user_answer, reference_answer):
    """Envia a resposta para a IA avaliar como banca do CACD."""
    try:
        # Tenta pegar a chave do ambiente ou dos segredos
        api_key = os.environ.get("openai_api_key")
        if not api_key and "openai_api_key" in st.secrets:
            api_key = st.secrets["openai_api_key"]

        if not api_key:
            return 0, "Erro: Chave da API OpenAI não configurada."

        client = OpenAI(api_key=api_key)

        prompt = f"""
        Atue como um medidor de desempenho nas perguntas a seguir.

        PERGUNTA: {question}
        GABARITO: {reference_answer}
        RESPOSTA: {user_answer}

        Tarefa:
        1. Compare a resposta com o gabarito.
        2. Avalie se a resposta condiz com o gabarito.
        3. Dê uma nota de 0 a 100 baseada na aderência.
        4. Gere um feedback curto (1-2 frases) sobre como o candidato se saiu.
        5. Indique objetivamente semelhanças e diferenças de significado em tópicos curtos.

        Formato de saída:
        NOTA: [apenas o número]
        RESULTADO: [feedback curto]
        SEMELHANÇAS: [tópicos curtos]
        DIFERENÇAS: [tópicos curtos]
        """

        response = client.responses.create(
            model="gpt-5-mini",
            input=prompt,
            max_output_tokens=300
        )

        content = response.output_text
        
        score = 0
        feedback = "Sem feedback."

        lines = content.split('\n')
        for line in lines:
            if "NOTA:" in line:
                try:
                    score = int(line.replace("NOTA:", "").strip())
                except (ValueError, TypeError): 
                    score = 0
            if "RESULTADO:" in line:
                feedback = line.replace("RESULTADO:", "").strip()
            if "FEEDBACK:" in line:
                feedback = line.replace("FEEDBACK:", "").strip()

        score = max(0, min(100, score))
        return score, feedback

    except Exception as e:
        return 0, f"Erro ao conectar com a IA: {str(e)}"


# --- SILENCIADOR DE ERROS DE COTA ---
def retry_on_quota(func):
    """Tenta executar a função novamente se der erro de cota do Google."""
    @wraps(func)
    def wrapper(*args, **kwargs):
        for _ in range(3): # Tenta 3 vezes antes de desistir
            try:
                return func(*args, **kwargs)
            except Exception as e:
                erro = str(e).lower()
                if "quota" in erro or "429" in erro:
                    time.sleep(2) # Espera respirar
                    continue
                else:
                    raise e
        return func(*args, **kwargs)
    return wrapper

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(
    page_title="Meu estudo",
    page_icon="📚",
    layout="wide"
)

# --- CONEXÃO UNIVERSAL BLINDADA (Replit & Streamlit Cloud) ---
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]

def get_credentials():
    # 1. TENTA PRIMEIRO O REPLIT (Variáveis de Ambiente)
    # Isso evita o erro de "secrets.toml not found"
    if "gcp_service_account" in os.environ:
        return json.loads(os.environ["gcp_service_account"])

    # 2. SE FALHAR, TENTA O STREAMLIT CLOUD
    try:
        if "gcp_service_account" in st.secrets:
            return json.loads(st.secrets["gcp_service_account"])
    except (ValueError):
        pass # Se der erro aqui, é porque não estamos na nuvem, apenas ignora

    return None

try:
    key_dict = get_credentials()
    if key_dict:
        creds = ServiceAccountCredentials.from_json_keyfile_dict(key_dict, scope)
        gc = gspread.authorize(creds)
    else:
        # Se não achou em lugar nenhum, mostra erro amigável
        st.error("⚠️ Configuração de Segurança não encontrada.")
        st.info("No Replit: Adicione 'gcp_service_account' em Secrets (Cadeado).")
        st.info("No Streamlit Cloud: Adicione em Settings > Secrets.")
        st.stop()
except Exception as e:
    st.error(f"Erro fatal na autenticação: {e}")
    st.stop()

# Função auxiliar para garantir que o cliente esteja sempre disponível
def get_gspread_client():
    return gc
# Mapeamento das Disciplinas
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

# URL CORRETA DA TRILHA
TRILHA_SHEET_URL = "https://docs.google.com/spreadsheets/d/1QUIvAgo_fLa7DtBrdRBcBqY4yRn6FbmH2tx1UoiAFd8/edit?usp=sharing"

def check_password():
    """Check if password is correct."""
    if 'authenticated' not in st.session_state:
        st.session_state.authenticated = False

    if st.session_state.authenticated:
        return True

    # Tenta pegar a senha do ambiente
    app_password = os.environ.get("app_password", "")

    # Se não houver senha configurada, libera o acesso (debug)
    if not app_password:
        return True

    password = st.text_input("Digite a senha para acessar:", type="password")
    if st.button("Entrar"):
        if password == app_password:
            st.session_state.authenticated = True
            st.rerun()
        else:
            st.error("Senha incorreta!")
    return False

def init_session_state():
    """Initialize all session state variables."""
    if "sidebar_open" not in st.session_state:
        st.session_state.sidebar_open = True


    defaults = {
        'question_index': 0,
        'show_result': False,
        'user_answer': "",
        'similarity_score': 0,
        'ai_feedback': "",
        'answer_input': "",
        'filtered_df': None,
        'worksheet': None,
        'worksheets_map': {},
        'selected_disciplina': None,
        'selected_tema': None,
        'selected_assunto': None,
        'original_df': None,
        'row_mapping': [],
        'source_sheet_mapping': [],
        'timer_running': False,
        'timer_start': None,
        'study_mode': "Perguntas",
        'essay_text': "",
        'voice_text': "",
        'last_audio_hash': None,
        'status_filter': [],
        'recency_filter': "Todas",
        'jump_to_question': 1
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value

def apply_custom_style():
        
    st.markdown("""
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Playfair+Display:ital,wght@0,400;0,700;1,400&display=swap');

        h1 {
            font-family: 'Playfair Display', serif;
            color: #2C3E50;
            font-size: 2.4rem !important;
            font-weight: 700;
            text-align: center;
            border-bottom: 2px solid #E6D2D5;
            padding-bottom: 20px;
            margin-bottom: 30px;
        }
        
        h2, h3 {
            font-family: 'Playfair Display', serif;
            color: #4A4A4A;
            font-weight: 400;
        }

        .question-card {
            background: #FFF9FB;
            border: 1px solid #F0E6E8;
            border-radius: 18px;
            padding: 20px 24px;
            box-shadow: 0 6px 14px rgba(0,0,0,0.04);
            margin-bottom: 18px;
        }

        .question-meta {
            font-family: 'Source Sans Pro', sans-serif;
            color: #7A6F73;
            font-size: 0.9rem;
            margin-bottom: 10px;
        }

        .question-text {
            font-family: 'Playfair Display', serif;
            color: #2F2F2F;
            font-size: 1.35rem;
            line-height: 1.6;
        }

        div[data-testid="stMetric"], div.stInfo, div.stSuccess, div.stWarning, div.stError {
            background-color: #FFFFFF;
            border: 1px solid #F0E6E8;
            border-radius: 15px;
            box-shadow: 0 4px 6px rgba(0,0,0,0.02);
            padding: 15px;
        }

        div.stButton > button {
            background-color: #FFFFFF;
            color: #B86E7E;
            border: 1px solid #B86E7E;
            border-radius: 25px;
            font-family: 'Source Sans Pro', sans-serif;
            font-weight: 600;
            transition: all 0.3s ease;
        }
        
        div.stButton > button:hover {
            background-color: #B86E7E;
            color: #FFFFFF;
            border-color: #B86E7E;
            box-shadow: 0 4px 10px rgba(184, 110, 126, 0.3);
            transform: translateY(-2px);
        }
        
        div.stButton > button[kind="primary"] {
            background-color: #B86E7E;
            color: white;
            box-shadow: 0 4px 10px rgba(184, 110, 126, 0.2);
        }

        .stTextArea textarea {
            background-color: #FFFFFF;
            border: 1px solid #E0E0E0;
            border-radius: 10px;
            font-family: 'Georgia', serif;
            font-size: 15px;
        }

        .stProgress > div > div > div > div {
            background-color: #B86E7E;
        }
        
        #MainMenu {visibility: hidden;}
        footer {visibility: hidden;}
        header {visibility: hidden;}
        </style>
    """, unsafe_allow_html=True)

@st.cache_data(ttl=300)
def get_worksheet_titles(sheet_url):
    """Get all worksheet titles from a spreadsheet."""
    try:
        client = get_gspread_client()
        spreadsheet = client.open_by_url(sheet_url)
        return [ws.title for ws in spreadsheet.worksheets()]
    except Exception as e:
        st.error(f"Erro ao carregar abas: {str(e)}")
        return []

@st.cache_data(ttl=300) # Guarda na memória por 5 minutos (conteúdo muda pouco)
@retry_on_quota
def load_worksheet_data(sheet_url, worksheet_title):
    """Carrega dados da disciplina com cache agressivo."""
    try:
        client = get_gspread_client()
        spreadsheet = client.open_by_url(sheet_url)
        worksheet = spreadsheet.worksheet(worksheet_title)
        data = worksheet.get_all_records()
        df = pd.DataFrame(data)
        # Garante coluna de resposta pessoal
        if 'Minha_Resposta' not in df.columns:
            df['Minha_Resposta'] = ""
        return df
    except Exception:
        return None

def get_worksheet_for_update(sheet_url, worksheet_title):
    """Get worksheet object for updating (not cached)."""
    try:
        client = get_gspread_client()
        spreadsheet = client.open_by_url(sheet_url)
        return spreadsheet.worksheet(worksheet_title)
    except Exception as e:
        st.error(f"Erro ao acessar planilha: {str(e)}")
        return None

def ensure_minha_resposta_column(worksheet):
    """Ensure 'Minha_Resposta' column exists after 'Data' column."""
    try:
        headers = worksheet.row_values(1)
        if 'Minha_Resposta' not in headers:
            if 'Data' in headers:
                data_idx = headers.index('Data')
                new_col_idx = data_idx + 2
            else:
                new_col_idx = len(headers) + 1
            worksheet.update_cell(1, new_col_idx, 'Minha_Resposta')
            return new_col_idx
        else:
            return headers.index('Minha_Resposta') + 1
    except Exception as e:
        st.error(f"Erro ao criar coluna Minha_Resposta: {str(e)}")
        return None

def get_column_index(worksheet, column_name):
    """Get 1-based column index by header name."""
    try:
        headers = worksheet.row_values(1)
        if column_name in headers:
            return headers.index(column_name) + 1
        return None
    except:
        return None

def load_all_worksheets_data(sheet_url):
    """Load data from ALL worksheets and concatenate with source tracking."""
    try:
        client = get_gspread_client()
        spreadsheet = client.open_by_url(sheet_url)
        all_dfs = []
        worksheets_map = {}
        
        for ws in spreadsheet.worksheets():
            try:
                data = ws.get_all_records()
                if data:
                    df = pd.DataFrame(data)
                    required_cols = ['Assunto', 'Pergunta', 'Resposta', 'Resultado', 'Data']
                    if all(col in df.columns for col in required_cols):
                        df['_source_sheet'] = ws.title
                        df['_original_row_idx'] = list(range(len(df)))
                        all_dfs.append(df)
                        worksheets_map[ws.title] = ws
            except (ValueError):
                continue
        
        if all_dfs:
            combined_df = pd.concat(all_dfs, ignore_index=True)
            return combined_df, worksheets_map
        return None, {}
    except Exception as e:
        st.error(f"Erro ao carregar todas as abas: {str(e)}")
        return None, {}

def apply_status_filter(df, status_filter):
    """Apply status filter to dataframe."""
    if not status_filter:
        return df
    
    masks = []
    for status in status_filter:
        if status == "Nunca respondidas":
            masks.append(df['Resultado'].isna() | (df['Resultado'].astype(str).str.strip() == ''))
        else:
            masks.append(df['Resultado'].astype(str) == status)
    
    if masks:
        combined_mask = masks[0]
        for m in masks[1:]:
            combined_mask = combined_mask | m
        return df[combined_mask]
    return df

def apply_recency_filter(df, recency_filter):
    """Apply recency filter based on 'Data' column."""
    if recency_filter == "Todas":
        return df
    
    now = datetime.now()
    df_copy = df.copy()
    
    df_copy['_parsed_date'] = pd.to_datetime(df_copy['Data'], format='%Y-%m-%d %H:%M:%S', errors='coerce')
    
    if recency_filter == "Hoje":
        start_date = now.replace(hour=0, minute=0, second=0, microsecond=0)
        mask = df_copy['_parsed_date'] >= start_date
    elif recency_filter == "Esta Semana":
        start_date = now - timedelta(days=7)
        mask = df_copy['_parsed_date'] >= start_date
    elif recency_filter == "Este Mês":
        start_date = now - timedelta(days=30)
        mask = df_copy['_parsed_date'] >= start_date
    elif recency_filter == "Há mais de 2 meses":
        cutoff_date = now - timedelta(days=60)
        mask = (df_copy['_parsed_date'] < cutoff_date) | df_copy['_parsed_date'].isna()
    else:
        mask = pd.Series([True] * len(df_copy))
    
    result = df_copy[mask].drop(columns=['_parsed_date'], errors='ignore')
    return result

def get_theme_last_review_date(df):
    """Get the most recent review date from the dataframe."""
    try:
        dates = pd.to_datetime(df['Data'], format='%Y-%m-%d %H:%M:%S', errors='coerce')
        valid_dates = dates.dropna()
        if len(valid_dates) > 0:
            return valid_dates.max().strftime("%Y-%m-%d")
    except:
        pass
    return None

def get_or_create_log_worksheet(sheet_url):
    """Get or create Log_Estudos worksheet."""
    try:
        client = get_gspread_client()
        spreadsheet = client.open_by_url(sheet_url)
        try:
            worksheet = spreadsheet.worksheet("Log_Estudos")
        except:
            worksheet = spreadsheet.add_worksheet(title="Log_Estudos", rows=1000, cols=3)
            worksheet.update(values=[['Data', 'Disciplina', 'Minutos']], range_name='A1:C1')
        return worksheet
    except Exception as e:
        st.error(f"Erro ao acessar Log_Estudos: {str(e)}")
        return None

@retry_on_quota
def save_study_log(disciplina, minutes):
    """Salva apenas quando necessário, com proteção de cota."""
    try:
        client = get_gspread_client()
        spreadsheet = client.open_by_url(TRILHA_SHEET_URL)
        try:
            ws = spreadsheet.worksheet("Log_Estudos")
        except:
            ws = spreadsheet.add_worksheet(title="Log_Estudos", rows=1000, cols=3)
            ws.update(values=[['Data', 'Disciplina', 'Minutos']], range_name='A1:C1')

        today = datetime.now().strftime("%Y-%m-%d")
        ws.append_row([today, disciplina, minutes])

        # Limpa o cache para o gráfico atualizar
        get_study_logs.clear() 
        return True
    except Exception as e:
        st.error(f"Erro ao salvar: {e}")
        return False

def get_study_logs():
    """Get study logs for the last 7 days."""
    try:
        worksheet = get_or_create_log_worksheet(TRILHA_SHEET_URL)
        if worksheet:
            data = worksheet.get_all_records()
            if data:
                df = pd.DataFrame(data)
                df['Data'] = pd.to_datetime(df['Data'], errors='coerce')
                seven_days_ago = datetime.now() - timedelta(days=7)
                df = df[df['Data'] >= seven_days_ago]
                return df
    except:
        pass
    return pd.DataFrame(columns=['Data', 'Disciplina', 'Minutos'])

def get_today_study_time():
    """Get total study time for today."""
    try:
        df = get_study_logs()
        if not df.empty:
            today = datetime.now().strftime("%Y-%m-%d")
            today_df = df[df['Data'].dt.strftime("%Y-%m-%d") == today]
            return int(today_df['Minutos'].sum())
    except:
        pass
    return 0

@st.cache_data(ttl=60) # Guarda na memória por 60 segundos
@retry_on_quota
def get_trilha_data():
    """Busca dados da trilha com cache e proteção contra falhas."""
    try:
        client = get_gspread_client()
        spreadsheet = client.open_by_url(TRILHA_SHEET_URL)
        # Tenta pegar a aba, se não achar retorna None sem travar
        try:
            worksheet = spreadsheet.worksheet("Trilha")
            data = worksheet.get_all_records()
            return pd.DataFrame(data), worksheet
        except:
            return None, None
    except Exception:
        return None, None

        
def ensure_tempo_column(worksheet):
    """Ensure 'Tempo' column exists after 'Data' column in Trilha worksheet."""
    try:
        headers = worksheet.row_values(1)
        if 'Tempo' not in headers:
            if 'Data' in headers:
                data_idx = headers.index('Data')
                new_col_idx = data_idx + 2
            else:
                new_col_idx = len(headers) + 1
            worksheet.update_cell(1, new_col_idx, 'Tempo')
            return new_col_idx
        else:
            return headers.index('Tempo') + 1
    except Exception as e:
        st.error(f"Erro ao criar coluna Tempo: {str(e)}")
        return None

def get_next_missions(df, count=5):
    """Find next N rows where Status is not 'sim'."""
    if df is None or df.empty:
        return []

    status_col = None
    for col in df.columns:
        if 'status' in col.lower():
            status_col = col
            break

    if status_col is None and len(df.columns) >= 4:
        status_col = df.columns[3]

    pending_missions = []
    if status_col:
        for idx, row in df.iterrows():
            status_val = str(row.get(status_col, '')).lower().strip()
            if status_val != 'sim':
                pending_missions.append((idx, row))
                if len(pending_missions) >= count:
                    break
    return pending_missions

def get_next_mission(df):
    """Find first row where Status is not 'sim'."""
    missions = get_next_missions(df, 1)
    if missions:
        return missions[0]
    return None, None

def create_new_mission(worksheet, description, disciplina):
    """Create a new mission in the Trilha worksheet."""
    try:
        all_values = worksheet.get_all_values()
        if len(all_values) <= 1:
            new_id = 1
        else:
            ids = []
            for row in all_values[1:]:
                try:
                    ids.append(int(row[0]))
                except:
                    pass
            new_id = max(ids) + 1 if ids else 1
        
        new_row = [new_id, description, disciplina, "não", "", ""]
        worksheet.append_row(new_row)
        return new_id
    except Exception as e:
        st.error(f"Erro ao criar missão: {str(e)}")
        return None

def complete_mission(worksheet, row_idx, tempo_minutes=None):
    """Mark mission as complete with optional tempo."""
    try:
        worksheet.update_cell(row_idx + 2, 4, "sim")
        worksheet.update_cell(row_idx + 2, 5, datetime.now().strftime("%Y-%m-%d"))
        
        if tempo_minutes is not None:
            tempo_col = ensure_tempo_column(worksheet)
            if tempo_col:
                worksheet.update_cell(row_idx + 2, tempo_col, tempo_minutes)
        
        return True
    except Exception as e:
        st.error(f"Erro ao salvar conclusão: {e}")
        return False

def update_sheet(worksheet, original_row_index, resultado, data, minha_resposta=None):
    """Update the Google Sheet with the result, date, and user answer."""
    try:
        resultado_col = get_column_index(worksheet, 'Resultado')
        data_col = get_column_index(worksheet, 'Data')
        
        if resultado_col:
            worksheet.update_cell(original_row_index + 2, resultado_col, resultado)
        else:
            worksheet.update_cell(original_row_index + 2, 4, resultado)
        
        if data_col:
            worksheet.update_cell(original_row_index + 2, data_col, data)
        else:
            worksheet.update_cell(original_row_index + 2, 5, data)
        
        if minha_resposta is not None:
            minha_col = ensure_minha_resposta_column(worksheet)
            if minha_col:
                worksheet.update_cell(original_row_index + 2, minha_col, minha_resposta)
        
        return True
    except Exception as e:
        st.error(f"Erro ao atualizar planilha: {str(e)}")
        return False

def reset_quiz_state():
    """Reset quiz state when filters change."""
    st.session_state.question_index = 0
    st.session_state.show_result = False
    st.session_state.user_answer = ""
    st.session_state.similarity_score = 0
    st.session_state.voice_text = ""
    st.session_state.ai_feedback = ""
    st.session_state.answer_input = ""
    st.session_state.last_audio_hash = None

def next_question():
    """Move to the next question."""
    st.session_state.question_index += 1
    st.session_state.show_result = False
    st.session_state.user_answer = ""
    st.session_state.similarity_score = 0
    st.session_state.voice_text = ""
    st.session_state.ai_feedback = ""
    st.session_state.answer_input = ""
    st.session_state.last_audio_hash = None

def format_last_resolution(value):
    """Format last resolution date for display."""
    if value is None or str(value).strip() == "":
        return "Nunca"
    parsed = pd.to_datetime(value, errors='coerce')
    if pd.notna(parsed):
        return parsed.strftime("%d/%m/%Y %H:%M")
    return str(value)

def record_result(resultado):
    """Record the result and move to the next question."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    user_answer = st.session_state.user_answer
    current_row = st.session_state.filtered_df.iloc[st.session_state.question_index]
    
    worksheet_to_use = st.session_state.worksheet
    original_row_index = st.session_state.row_mapping[st.session_state.question_index] if st.session_state.question_index < len(st.session_state.row_mapping) else 0
    
    if st.session_state.selected_tema == "Todos" and st.session_state.worksheets_map:
        source_sheet_name = current_row.get('_source_sheet', '')
        original_row_index = int(current_row.get('_original_row_idx', 0))
        worksheet_to_use = st.session_state.worksheets_map.get(source_sheet_name)

    if worksheet_to_use and update_sheet(worksheet_to_use, original_row_index, resultado, timestamp, user_answer):
        st.session_state.filtered_df.at[st.session_state.question_index, 'Resultado'] = resultado
        st.session_state.filtered_df.at[st.session_state.question_index, 'Data'] = timestamp
        if 'Minha_Resposta' not in st.session_state.filtered_df.columns:
            st.session_state.filtered_df['Minha_Resposta'] = ''
        st.session_state.filtered_df.at[st.session_state.question_index, 'Minha_Resposta'] = user_answer
        next_question()
        st.rerun()

def get_ai_response(question):
    """Get response from OpenAI using Responses API (GPT-5-mini)."""
    try:
        client = OpenAI(
            api_key=os.environ.get(
                "AI_INTEGRATIONS_OPENAI_API_KEY",
                os.environ.get("openai_api_key")
            ),
            base_url=os.environ.get(
                "AI_INTEGRATIONS_OPENAI_BASE_URL",
                "https://api.openai.com/v1"
            ),
        )

        response = client.responses.create(
            model="gpt-5-mini",
            input=[
                {
                    "role": "system",
                    "content": [
                        {
                            "type": "input_text",
                            "text": (
                                "Você é um assistente de estudos especializado no CACD. "
                                "Responda objetivamente."
                            )
                        }
                    ]
                },
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "input_text",
                            "text": question
                        }
                    ]
                }
            ],
            max_output_tokens=500
        )

        return response.output_text

    except Exception as e:
        return f"Erro ao consultar IA: {str(e)}"


def render_sidebar():
    
        # --- CRONÔMETRO BLINDADO (OFFLINE) ---
        with st.expander("⏱️ Tempo de estudo", expanded=True):
            tab1, tab2 = st.tabs(["Auto", "Manual"])

            with tab1:
                # Mostra o total já cacheado (rápido, não bate no Google)
                today_time = get_today_study_time()
                st.metric("Tempo Total Hoje", f"{today_time} min")

                # --- CORREÇÃO DO ERRO COL2 ---
                # Criamos as colunas ANTES de tentar usá-las
                col1, col2 = st.columns(2)

                # Lógica 100% Offline enquanto conta
                with col1:
                    if not st.session_state.timer_running:
                        if st.button("▶️ Iniciar", use_container_width=True):
                            st.session_state.timer_running = True
                            st.session_state.timer_start = datetime.now()
                            st.rerun()
                    else:
                         # Botão visualmente desabilitado ou informativo
                         st.markdown(f"<div style='text-align:center; padding: 10px; color: #B86E7E; font-weight: bold;'>Em curso...</div>", unsafe_allow_html=True)

                with col2:
                    if st.session_state.timer_running:
                        # Cálculo apenas visual (não toca no Google API)
                        start = st.session_state.timer_start
                        mins_decorridos = 0
                        if start:
                            delta = datetime.now() - start
                            mins_decorridos = int(delta.total_seconds() / 60)

                        # Botão de Parar (Só chama o Google AQUI)
                        if st.button("⏹️ Parar", use_container_width=True):
                            if start:
                                delta = datetime.now() - start
                                final_min = max(1, int(delta.total_seconds() / 60))
                                disc = st.session_state.selected_disciplina or "Geral"

                                with st.spinner("Salvando..."):
                                    # Chama a função blindada de salvar
                                    save_study_log(disc, final_min)

                                st.success(f"+{final_min} min!")

                            st.session_state.timer_running = False
                            st.session_state.timer_start = None
                            time.sleep(1)
                            st.rerun()

                # Feedback visual do tempo (fora das colunas para destaque)
                if st.session_state.timer_running and st.session_state.timer_start:
                    delta = datetime.now() - st.session_state.timer_start
                    mins = int(delta.total_seconds() / 60)
                    st.info(f"⏳ Tempo da sessão atual: {mins} min")

            with tab2:
                m_min = st.number_input("Minutos", 1, 480, 30)
                m_date = st.date_input("Data", datetime.now())
                m_disc = st.selectbox("Matéria", list(SHEETS_MAPPING.keys()))
                if st.button("Salvar Manual", use_container_width=True):
                    with st.spinner("Salvando..."):
                        save_study_log(m_disc, m_min)
                    st.success("Salvo!")

        # --- GRÁFICO ---
        try:
            logs = get_study_logs()
            if not logs.empty:
                daily = logs.groupby(logs['Data'].dt.strftime("%d/%m"))['Minutos'].sum()
                st.bar_chart(daily, height=150, color="#B86E7E")
        except:
            pass # Se der erro no gráfico, não quebra o app

        # --- OUTRAS FERRAMENTAS ---
        with st.expander("🎧 Petit Journal"):
            components.iframe(
                "https://open.spotify.com/embed/show/75MOMlaBaE9Smo2Vp87CO2",
                height=152
            )

            st.markdown(
                "[▶️ Ouvir no Spotify (com login)](https://open.spotify.com/show/75MOMlaBaE9Smo2Vp87CO2)",
                unsafe_allow_html=True
            )


        with st.expander("🧠 Consultor IA"):
            q = st.text_area("Dúvida Rápida", height=100, placeholder="Pergunte ao tutor...")
            if st.button("Consultar", use_container_width=True):
                if q:
                    with st.spinner("Analisando..."):
                        st.markdown(get_ai_response(q))


def render_trilha_dashboard():
    """Render the Trilha dashboard with mission selection and timer."""
    st.subheader("Trilha de estudo")

    if 'trilha_timer_running' not in st.session_state:
        st.session_state.trilha_timer_running = False
    if 'trilha_timer_start' not in st.session_state:
        st.session_state.trilha_timer_start = None
    if 'trilha_elapsed_minutes' not in st.session_state:
        st.session_state.trilha_elapsed_minutes = 0
    if 'active_mission_idx' not in st.session_state:
        st.session_state.active_mission_idx = None
    if 'force_select_mission' not in st.session_state:
        st.session_state.force_select_mission = None
    if 'show_create_mission' not in st.session_state:
        st.session_state.show_create_mission = False

    df, worksheet = get_trilha_data()

    if df is None or df.empty:
        st.info("Nenhuma trilha configurada ou planilha 'Trilha' não encontrada.")
        return

    pending_missions = get_next_missions(df, 5)
    
    if st.session_state.force_select_mission:
        id_col = df.columns[0]
        found_in_list = any(
            row.get(id_col) == st.session_state.force_select_mission 
            for _, row in pending_missions
        )
        if not found_in_list:
            for idx, row in df.iterrows():
                if row.get(id_col) == st.session_state.force_select_mission:
                    pending_missions.append((idx, row))
                    break

    if not pending_missions:
        st.success("Todas as missões foram concluídas!")
        if st.button("➕ Criar Nova Missão", use_container_width=True):
            st.session_state.show_create_mission = True
        if st.session_state.show_create_mission:
            with st.form("create_mission_form_empty"):
                new_desc = st.text_input("Descrição da Tarefa")
                new_disc = st.selectbox("Disciplina", list(SHEETS_MAPPING.keys()))
                if st.form_submit_button("Criar Missão", type="primary"):
                    if new_desc.strip():
                        new_id = create_new_mission(worksheet, new_desc, new_disc)
                        if new_id:
                            st.success(f"Missão #{new_id} criada!")
                            st.session_state.show_create_mission = False
                            st.session_state.force_select_mission = new_id
                            if 'mission_selector' in st.session_state:
                                del st.session_state['mission_selector']
                            get_trilha_data.clear()
                            st.rerun()
                    else:
                        st.warning("Preencha a descrição.")
        return

    desc_col = df.columns[1] if len(df.columns) > 1 else df.columns[0]
    disc_col = df.columns[2] if len(df.columns) > 2 else desc_col
    id_col = df.columns[0]

    mission_options = []
    mission_indices = []
    default_idx = 0
    
    for i, (idx, row) in enumerate(pending_missions):
        desc = row.get(desc_col, "Sem descrição")
        disc = row.get(disc_col, "")
        mission_id = row.get(id_col, idx+1)
        mission_options.append(f"{mission_id}. {desc} ({disc})")
        mission_indices.append((idx, row, mission_id))
        
        if st.session_state.force_select_mission and mission_id == st.session_state.force_select_mission:
            default_idx = i
            st.session_state.force_select_mission = None

    col1, col2 = st.columns([3, 1])
    
    with col1:
        selected_mission = st.selectbox(
            "Escolha sua Missão Ativa",
            options=mission_options,
            index=default_idx,
            key="mission_selector"
        )
        
        selected_list_idx = mission_options.index(selected_mission)
        active_idx, active_row, active_id = mission_indices[selected_list_idx]
        st.session_state.active_mission_idx = active_idx
        
        active_desc = active_row.get(desc_col, "")
        active_disc = active_row.get(disc_col, "")

    with col2:
        if st.button("➕ Nova Missão", use_container_width=True):
            st.session_state.show_create_mission = not st.session_state.show_create_mission

    if st.session_state.show_create_mission:
        with st.expander("Criar Nova Missão", expanded=True):
            with st.form("create_mission_form"):
                new_desc = st.text_input("Descrição da Tarefa")
                new_disc = st.selectbox("Disciplina", list(SHEETS_MAPPING.keys()))
                submitted = st.form_submit_button("Criar Missão", type="primary")
                if submitted:
                    if new_desc.strip():
                        new_id = create_new_mission(worksheet, new_desc, new_disc)
                        if new_id:
                            st.success(f"Missão #{new_id} criada!")
                            st.session_state.show_create_mission = False
                            st.session_state.force_select_mission = new_id
                            if 'mission_selector' in st.session_state:
                                del st.session_state['mission_selector']
                            get_trilha_data.clear()
                            st.rerun()
                    else:
                        st.warning("Preencha a descrição.")

    st.markdown(f"**Missão Ativa:** {active_desc}")
    
    timer_col1, timer_col2, timer_col3 = st.columns([1, 1, 1])
    
    with timer_col1:
        if not st.session_state.trilha_timer_running:
            total_mins = st.session_state.trilha_elapsed_minutes
            if total_mins > 0:
                st.info(f"⏸️ {total_mins} min acumulados")
            if st.button("▶️ Iniciar Foco", use_container_width=True, type="primary"):
                st.session_state.trilha_timer_running = True
                st.session_state.trilha_timer_start = datetime.now()
                st.rerun()
        else:
            elapsed = datetime.now() - st.session_state.trilha_timer_start
            session_mins = int(elapsed.total_seconds() / 60)
            total_mins = st.session_state.trilha_elapsed_minutes + session_mins
            st.info(f"⏳ {total_mins} min")
    
    with timer_col2:
        if st.session_state.trilha_timer_running:
            if st.button("⏹️ Pausar Timer", use_container_width=True):
                elapsed = datetime.now() - st.session_state.trilha_timer_start
                session_mins = max(0, int(elapsed.total_seconds() / 60))
                st.session_state.trilha_elapsed_minutes += session_mins
                st.session_state.trilha_timer_running = False
                st.session_state.trilha_timer_start = None
                st.rerun()
    
    with timer_col3:
        if st.button("✅ Concluir Missão", use_container_width=True):
            tempo_min = st.session_state.trilha_elapsed_minutes
            if st.session_state.trilha_timer_running and st.session_state.trilha_timer_start:
                elapsed = datetime.now() - st.session_state.trilha_timer_start
                tempo_min += max(0, int(elapsed.total_seconds() / 60))
            
            tempo_min = max(1, tempo_min) if tempo_min > 0 else None
            
            if complete_mission(worksheet, active_idx, tempo_min):
                if tempo_min:
                    save_study_log(active_disc, tempo_min)
                st.success(f"Missão concluída!" + (f" (+{tempo_min} min)" if tempo_min else ""))
                st.session_state.trilha_timer_running = False
                st.session_state.trilha_timer_start = None
                st.session_state.trilha_elapsed_minutes = 0
                st.session_state.active_mission_idx = None
                get_trilha_data.clear()
                st.rerun()
            else:
                st.error("Erro ao concluir missão")

def render_study_content():
    """Render the main study content area."""
    st.subheader("Material de Estudo")

    col1, col2, col3 = st.columns(3)

    with col1:
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
            st.session_state.worksheets_map = {}
            reset_quiz_state()
            load_worksheet_data.clear()
            get_worksheet_titles.clear()

    sheet_url = SHEETS_MAPPING[selected_disciplina]
    worksheet_titles = get_worksheet_titles(sheet_url)

    with col2:
        if worksheet_titles:
            tema_options = ["Todos"] + worksheet_titles
            selected_tema = st.selectbox(
                "Selecione o tema",
                options=tema_options,
                index=0,
                key="tema_select"
            )

            if selected_tema != st.session_state.selected_tema:
                st.session_state.selected_tema = selected_tema
                st.session_state.selected_assunto = None
                st.session_state.original_df = None
                st.session_state.filtered_df = None
                st.session_state.worksheets_map = {}
                st.session_state.source_sheet_mapping = []
                reset_quiz_state()
                load_worksheet_data.clear()

    if st.session_state.selected_tema and st.session_state.original_df is None:
        with st.spinner("Carregando dados..."):
            if st.session_state.selected_tema == "Todos":
                df, worksheets_map = load_all_worksheets_data(sheet_url)
                if df is not None:
                    st.session_state.original_df = df.copy()
                    st.session_state.worksheets_map = worksheets_map
                    st.session_state.worksheet = None
            else:
                df = load_worksheet_data(sheet_url, st.session_state.selected_tema)
                if df is not None:
                    required_columns = ['Assunto', 'Pergunta', 'Resposta', 'Resultado', 'Data']
                    missing_columns = [col for col in required_columns if col not in df.columns]

                    if missing_columns:
                        st.error(f"Colunas faltando: {', '.join(missing_columns)}")
                    else:
                        st.session_state.original_df = df.copy()
                        st.session_state.worksheet = get_worksheet_for_update(sheet_url, st.session_state.selected_tema)

    if st.session_state.original_df is not None:
        last_review = get_theme_last_review_date(st.session_state.original_df)
        if last_review:
            st.caption(f"Visto pela última vez em: {last_review}")

    with st.expander("Filtros Avançados"):
        filter_col1, filter_col2 = st.columns(2)
        with filter_col1:
            status_options = ["Nunca respondidas", "Acertei", "Errei", "Posso melhorar"]
            status_filter = st.multiselect("Filtrar por Status", options=status_options, key="status_filter_select")
        with filter_col2:
            recency_options = ["Todas", "Hoje", "Esta Semana", "Este Mês", "Há mais de 2 meses"]
            recency_filter = st.selectbox("Filtrar por Recência", options=recency_options, key="recency_filter_select")

        if status_filter != st.session_state.status_filter or recency_filter != st.session_state.recency_filter:
            st.session_state.status_filter = status_filter
            st.session_state.recency_filter = recency_filter
            st.session_state.selected_assunto = None
            reset_quiz_state()

    with col3:
        if st.session_state.original_df is not None:
            working_df = st.session_state.original_df.copy()

            if st.session_state.status_filter:
                working_df = apply_status_filter(working_df, st.session_state.status_filter)
            if st.session_state.recency_filter != "Todas":
                working_df = apply_recency_filter(working_df, st.session_state.recency_filter)

            unique_assuntos = sorted(working_df['Assunto'].dropna().unique().tolist())
            assunto_options = ["Tudo"] + [str(a) for a in unique_assuntos]

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
                    filtered = working_df.copy()
                    original_indices = working_df.index.tolist()
                else:
                    mask = working_df['Assunto'].astype(str) == selected_assunto
                    filtered = working_df[mask].copy()
                    original_indices = working_df[mask].index.tolist()

                filtered = filtered.reset_index(drop=True)
                st.session_state.filtered_df = filtered
                st.session_state.row_mapping = original_indices

                if '_source_sheet' in filtered.columns:
                    st.session_state.source_sheet_mapping = filtered['_source_sheet'].tolist()
                else:
                    st.session_state.source_sheet_mapping = []

    st.divider()

    mode_col1, mode_col2 = st.columns([1, 4])
    with mode_col1:
        study_mode = st.radio("Modo", ["Perguntas", "Dissertativo"], key="study_mode_radio")
        st.session_state.study_mode = study_mode

    if st.session_state.filtered_df is None or len(st.session_state.filtered_df) == 0:
        if st.session_state.original_df is None:
            st.info("Selecione uma disciplina e tema para começar.")
        else:
            st.warning("Nenhuma questão encontrada com os filtros selecionados.")
        return

    with mode_col2:
        total = len(st.session_state.filtered_df)
        current = st.session_state.question_index + 1
        st.progress(min(current / total, 1.0))
        st.caption(f"Questão {min(current, total)} de {total}")

    # AQUI ESTAVA O ERRO: Chamamos as funções, mas elas precisam estar definidas FORA daqui
    if study_mode == "Perguntas":
        render_quiz_mode()
    else:
        render_essay_mode()


# --- AGORA SIM: As funções estão coladas na margem esquerda (fora da anterior) ---

def render_quiz_mode():
    """Render the quiz mode interface."""
    df = st.session_state.filtered_df
    total = len(df)

    # 1. VERIFICAÇÃO DE CONCLUSÃO (Mudamos para o topo)
    # Se o índice passou do total, mostra a festa e para a execução AQUI.
    if st.session_state.question_index >= total:
        st.success(f"Você completou todas as {total} questões desta seleção!")
        st.balloons()

        if st.button("Recomeçar"):
            reset_quiz_state()
            st.rerun()
        return

    # 2. BARRA DE NAVEGAÇÃO (Só desenha se não acabou)
    col_nav1, col_nav2 = st.columns([1, 4])
    with col_nav1:
        # Proteção extra: min(...) garante que nunca tente mostrar valor maior que o total
        safe_current = min(st.session_state.question_index + 1, total)

        idx_visual = st.number_input(
            "Ir para Questão", 
            min_value=1, 
            max_value=total, 
            value=safe_current
        )

        # Lógica de pular para questão específica
        idx = idx_visual - 1
        if idx != st.session_state.question_index:
            st.session_state.question_index = idx
            st.session_state.show_result = False
            st.session_state.user_answer = ""
            st.session_state.similarity_score = 0
            st.session_state.ai_feedback = ""
            st.session_state.answer_input = ""
            st.session_state.last_audio_hash = None
            st.rerun()

    current_row = df.iloc[st.session_state.question_index]

    # Metadados
    status_anterior = current_row.get('Resultado', 'Novo') or "Novo"
    last_resolution = format_last_resolution(current_row.get('Data', ''))
    question_text = html.escape(str(current_row['Pergunta']))
    assunto_text = html.escape(str(current_row['Assunto']))

    st.markdown(
        f"""
        <div class="question-card">
            <div class="question-meta">
                Assunto: {assunto_text} · Status anterior: {html.escape(str(status_anterior))} · Última resolução: {html.escape(last_resolution)}
            </div>
            <div class="question-text">{question_text}</div>
        </div>
        """,
        unsafe_allow_html=True
    )

    st.markdown("### Sua Resposta")

    input_method = st.radio("Método de entrada", ["Texto", "Voz"], horizontal=True, key="input_method", label_visibility="collapsed")

    if input_method == "Voz":
        try:
            from audiorecorder import audiorecorder
            import speech_recognition as sr
            import tempfile

            audio = audiorecorder("🎤 Gravar", "⏹️ Parar")

            if len(audio) > 0:
                audio_hash = hash(audio.raw_data)
                with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp_file:
                    audio.export(tmp_file.name, format="wav")
                    tmp_path = tmp_file.name

                st.audio(tmp_path, format="audio/wav")

                if st.session_state.last_audio_hash != audio_hash:
                    with st.spinner("Transcrevendo automaticamente..."):
                        try:
                            recognizer = sr.Recognizer()
                            with sr.AudioFile(tmp_path) as source:
                                audio_data = recognizer.record(source)
                            text = recognizer.recognize_google(audio_data, language="pt-BR")
                            st.session_state.last_audio_hash = audio_hash
                            st.session_state.voice_text = text
                            st.session_state.user_answer = text
                            st.session_state.answer_input = text
                            st.rerun()
                        except Exception as e:
                            st.error(f"Erro na transcrição: {str(e)}")
        except Exception as e:
            st.warning("Gravação de voz não disponível.")

    user_answer = st.text_area(
        "Digite sua resposta aqui:",
        value=st.session_state.answer_input,
        height=150,
        key="answer_input",
        label_visibility="collapsed"
    )
    st.session_state.user_answer = user_answer

    # --- LÓGICA DE BOTÕES E CORREÇÃO ---
    if not st.session_state.show_result:
        col1, col2 = st.columns([1, 1])
        with col1:
            if st.button("Verificar Resposta", type="primary", use_container_width=True):
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
        # CORREÇÃO VIA IA
        if st.session_state.similarity_score == 0: 
            with st.spinner("⚖️ A Banca Examinadora está analisando sua resposta..."):
                nota, feedback = evaluate_answer_ai(
                    current_row['Pergunta'], 
                    user_answer, 
                    str(current_row['Resposta'])
                )
                st.session_state.similarity_score = nota
                st.session_state.ai_feedback = feedback
        else:
            nota = st.session_state.similarity_score
            feedback = getattr(st.session_state, 'ai_feedback', '')

        st.markdown("---")
        st.markdown(f"### Conformidade com o gabarito: **{nota}/100**")

        if nota >= 80:
            st.success(f"**Excelente!** {feedback}")
            st.progress(nota / 100)
        elif nota >= 50:
            st.warning(f"**Bom.** {feedback}")
            st.progress(nota / 100)
        else:
            st.error(f"**Insuficiente.** {feedback}")
            st.progress(nota / 100)

        with st.expander("Ver Gabarito Oficial", expanded=False):
            st.info(f"**Referência:** {current_row['Resposta']}")

        st.markdown("### Registrar Desempenho")
        c1, c2, c3 = st.columns(3)

        if c1.button("✅ Acertei", use_container_width=True): 
            record_result("Acertei")
        if c2.button("⚠️ Posso melhorar", use_container_width=True): 
            record_result("Posso melhorar")
        if c3.button("❌ Errei", use_container_width=True): 
            record_result("Errei")

def render_essay_mode():
    """Render the essay/dissertativo mode interface."""
    df = st.session_state.filtered_df

    st.markdown("### Modo Dissertativo")
    st.markdown("Escreva uma redação cobrindo todos os tópicos listados abaixo. O sistema verificará sua cobertura.")

    with st.expander(f"📋 Tópicos a Abordar ({len(df)} questões)", expanded=True):
        for idx, row in df.iterrows():
            st.markdown(f"**{idx+1}.** {row['Assunto']}: {row['Pergunta'][:100]}...")

    st.markdown("---")

    essay = st.text_area(
        "Sua redação:",
        value=st.session_state.essay_text,
        height=300,
        key="essay_input"
    )
    st.session_state.essay_text = essay

    if st.button("Avaliar Cobertura", type="primary"):
        if essay.strip():
            covered = []
            not_covered = []

            for idx, row in df.iterrows():
                answer = str(row['Resposta'])
                similarity = fuzz.token_set_ratio(essay.lower(), answer.lower())

                if similarity >= 40:
                    covered.append((row['Assunto'], answer[:50] + "...", similarity))
                else:
                    not_covered.append((row['Assunto'], answer[:50] + "..."))

            st.markdown("---")
            st.markdown("### Resultado da Avaliação")

            coverage_pct = len(covered) / len(df) * 100 if len(df) > 0 else 0
            st.metric("Cobertura", f"{coverage_pct:.1f}%")

            if covered:
                with st.expander(f"Conceitos abordados ({len(covered)})", expanded=True):
                    for assunto, resp, sim in covered:
                        st.markdown(f"- **{assunto}**: {resp} ({sim}%)")

            if not_covered:
                with st.expander(f"Conceitos não abordados ({len(not_covered)})"):
                    for assunto, resp in not_covered:
                        st.markdown(f"- **{assunto}**: {resp}")
        else:
            st.warning("Escreva algo antes de avaliar.")


def main():
    """Main application entry point."""
    if not check_password():
        st.stop()

    init_session_state()

    apply_custom_style()

    render_sidebar()

    st.title("Meu estudo")

    render_trilha_dashboard()

    st.divider()

    render_study_content()

if __name__ == "__main__":
    main()
