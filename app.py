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
from functools import wraps

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
    except:
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
    defaults = {
        'question_index': 0,
        'show_result': False,
        'user_answer': "",
        'similarity_score': 0,
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
            font-size: 3rem !important;
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
            font-size: 16px;
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
            except:
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

        
def get_next_mission(df):
    """Find first row where Status is not 'sim'."""
    if df is None or df.empty:
        return None, None

    # Procura coluna de Status de forma flexível
    status_col = None
    for col in df.columns:
        if 'status' in col.lower():
            status_col = col
            break

    # Se não achar pelo nome, tenta a coluna D (índice 3)
    if status_col is None and len(df.columns) >= 4:
        status_col = df.columns[3]

    if status_col:
        for idx, row in df.iterrows():
            status_val = str(row.get(status_col, '')).lower().strip()
            if status_val != 'sim':
                return idx, row
    return None, None

def complete_mission(worksheet, row_idx):
    """Mark mission as complete."""
    try:
        # Atualiza Status (Col 4/D) e Data (Col 5/E)
        # row_idx + 2 porque a planilha começa em 1 e tem cabeçalho
        worksheet.update_cell(row_idx + 2, 4, "sim")
        worksheet.update_cell(row_idx + 2, 5, datetime.now().strftime("%Y-%m-%d"))
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

def next_question():
    """Move to the next question."""
    st.session_state.question_index += 1
    st.session_state.show_result = False
    st.session_state.user_answer = ""
    st.session_state.similarity_score = 0
    st.session_state.voice_text = ""

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

def get_ai_response(question):
    """Get response from OpenAI."""
    try:
        client = OpenAI(
            api_key=os.environ.get("openai_api_key"),
        )
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "Você é um assistente de estudos especializado no CACD. Responda de forma clara, concisa e jurídica."},
                {"role": "user", "content": question}
            ],
            max_tokens=500
        )
        return response.choices[0].message.content
    except Exception as e:
        return f"Erro ao consultar IA: {str(e)}"

def render_sidebar():
    with st.sidebar:
        st.markdown("### 🏛️ Painel de Controle")

        # --- CRONÔMETRO BLINDADO (OFFLINE) ---
        with st.expander("⏱️ Cronômetro", expanded=True):
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
            components.iframe("https://open.spotify.com/embed/show/6k3Udb6eX6o7f0r7yG9sX3?utm_source=generator", height=152)

        with st.expander("🧠 Consultor IA"):
            q = st.text_area("Dúvida Rápida", height=100, placeholder="Pergunte ao tutor...")
            if st.button("Consultar", use_container_width=True):
                if q:
                    with st.spinner("Analisando..."):
                        st.markdown(get_ai_response(q))

def render_trilha_dashboard():
    """Render the Trilha dashboard showing next mission."""
    st.subheader("Trilha - Próxima Missão")

    df, worksheet = get_trilha_data()

    if df is None or df.empty:
        st.info("Nenhuma trilha configurada ou planilha 'Trilha' não encontrada.")
        return

    idx, mission = get_next_mission(df)

    if mission is None:
        st.success("Todas as missões foram concluídas!")
        return

    desc_col = df.columns[1] if len(df.columns) > 1 else df.columns[0]
    disc_col = df.columns[2] if len(df.columns) > 2 else desc_col

    description = mission.get(desc_col, "Sem descrição")
    disciplina = mission.get(disc_col, "")

    col1, col2 = st.columns([4, 1])
    with col1:
        st.info(f"**{description}** ({disciplina})")
    with col2:
        if st.button("✅ Concluir", key="complete_mission", use_container_width=True):
            if complete_mission(worksheet, idx):
                st.success("Missão concluída!")
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

    if study_mode == "Perguntas":
        render_quiz_mode()
    else:
        render_essay_mode()

def render_quiz_mode():
    """Render the quiz mode interface."""
    df = st.session_state.filtered_df

    if st.session_state.question_index >= len(df):
        st.success("Você completou todas as questões!")
        st.balloons()

        if st.button("Recomeçar"):
            reset_quiz_state()
            st.rerun()
        return

    nav_col1, nav_col2 = st.columns([1, 3])
    with nav_col1:
        total = len(df)
        jump_to = st.number_input(
            "Ir para questão nº",
            min_value=1,
            max_value=total,
            value=st.session_state.question_index + 1,
            key="jump_to_question_input"
        )
        if jump_to != st.session_state.question_index + 1:
            st.session_state.question_index = jump_to - 1
            st.session_state.show_result = False
            st.session_state.user_answer = ""
            st.rerun()

    current_row = df.iloc[st.session_state.question_index]

    last_result = str(current_row.get('Resultado', '')).strip()
    last_date = str(current_row.get('Data', '')).strip()
    
    if last_date or last_result:
        meta_parts = []
        if last_date:
            meta_parts.append(f"Última revisão: {last_date[:10]}")
        if last_result:
            meta_parts.append(f"Último resultado: {last_result}")
        st.caption(" | ".join(meta_parts))

    st.markdown(f"**Assunto:** {current_row['Assunto']}")
    
    if '_source_sheet' in current_row:
        st.caption(f"Tema: {current_row['_source_sheet']}")
    
    st.markdown("### Pergunta")
    st.markdown(f"> {current_row['Pergunta']}")

    st.markdown("### Sua Resposta")

    input_method = st.radio("Método de entrada", ["Texto", "Voz"], horizontal=True, key="input_method")

    if input_method == "Voz":
        try:
            from audiorecorder import audiorecorder
            import speech_recognition as sr
            import tempfile

            audio = audiorecorder("Gravar", "Parar")

            if len(audio) > 0:
                with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp_file:
                    audio.export(tmp_file.name, format="wav")
                    tmp_path = tmp_file.name

                st.audio(tmp_path, format="audio/wav")

                if st.button("Transcrever"):
                    with st.spinner("Transcrevendo..."):
                        try:
                            recognizer = sr.Recognizer()
                            with sr.AudioFile(tmp_path) as source:
                                audio_data = recognizer.record(source)
                            text = recognizer.recognize_google(audio_data, language="pt-BR")
                            st.session_state.voice_text = text
                            st.session_state.user_answer = text
                            st.rerun()
                        except Exception as e:
                            st.error(f"Erro na transcrição: {str(e)}")
        except Exception as e:
            st.warning("Gravação de voz não disponível.")

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
            if st.button("Acertei", type="primary", use_container_width=True):
                record_result("Acertei")
                st.rerun()

        with col2:
            if st.button("Posso melhorar", use_container_width=True):
                record_result("Posso melhorar")
                st.rerun()

        with col3:
            if st.button("Errei", use_container_width=True):
                record_result("Errei")
                st.rerun()

def render_essay_mode():
    """Render the essay/dissertativo mode interface."""
    df = st.session_state.filtered_df

    st.markdown("### Modo Dissertativo")
    st.markdown("Escreva uma redação sobre o assunto selecionado. O sistema verificará a cobertura dos conceitos.")

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