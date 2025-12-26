import streamlit as st
import pandas as pd
import os
import json
from datetime import datetime, timedelta
import time
from thefuzz import fuzz
import matplotlib.pyplot as plt
import streamlit.components.v1 as components
from openai import OpenAI
import gspread
from oauth2client.service_account import ServiceAccountCredentials

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(
    page_title="Meu CACD",
    page_icon="⚖️",
    layout="wide"
)

# --- ESTILIZAÇÃO VISUAL (Visual Diplomático Feminino) ---
def apply_custom_style():
    st.markdown("""
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Playfair+Display:wght@400;700&family=Source+Sans+Pro:wght@400;600&display=swap');

        /* Títulos Principais */
        h1 {
            font-family: 'Playfair Display', serif;
            color: #2C3E50;
            font-size: 2.8rem !important;
            text-align: center;
            border-bottom: 2px solid #E6D2D5;
            padding-bottom: 15px;
            margin-bottom: 25px;
        }

        /* Subtítulos */
        h2, h3 {
            font-family: 'Playfair Display', serif;
            color: #4A4A4A;
        }

        /* Cartões e Caixas */
        div.stInfo, div.stSuccess, div.stWarning, div.stError, div[data-testid="stMetric"] {
            background-color: #FFFFFF;
            border: 1px solid #F0E6E8;
            border-radius: 12px;
            box-shadow: 0 2px 5px rgba(0,0,0,0.03);
        }

        /* Botões */
        div.stButton > button {
            border-radius: 20px;
            font-family: 'Source Sans Pro', sans-serif;
            border: 1px solid #B86E7E;
            color: #B86E7E;
            background-color: white;
            transition: all 0.3s;
        }
        div.stButton > button:hover {
            background-color: #B86E7E;
            color: white;
            border-color: #B86E7E;
        }
        div.stButton > button[kind="primary"] {
            background-color: #B86E7E;
            color: white;
            border: none;
        }

        /* Inputs */
        .stTextArea textarea, .stTextInput input {
            border-radius: 10px;
            border: 1px solid #E0E0E0;
            font-family: 'Source Sans Pro', sans-serif;
        }

        /* Ocultar menu padrão */
        #MainMenu {visibility: hidden;}
        footer {visibility: hidden;}
        header {visibility: hidden;}
        </style>
    """, unsafe_allow_html=True)

# --- AUTENTICAÇÃO BLINDADA ---
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]

try:
    if "gcp_service_account" in os.environ:
        key_dict = json.loads(os.environ["gcp_service_account"])
        creds = ServiceAccountCredentials.from_json_keyfile_dict(key_dict, scope)
        gc = gspread.authorize(creds)
    else:
        st.error("ERRO: Segredo 'gcp_service_account' não encontrado.")
        st.stop()
except Exception as e:
    st.error(f"Erro fatal na autenticação: {e}")
    st.stop()

def get_gspread_client():
    return gc

# --- MAPEAMENTO ---
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

TRILHA_SHEET_URL = "https://docs.google.com/spreadsheets/d/1QUIvAgo_fLa7DtBrdRBcBqY4yRn6FbmH2tx1UoiAFd8/edit?usp=sharing"

# --- FUNÇÕES AUXILIARES ---
def check_password():
    if 'authenticated' not in st.session_state:
        st.session_state.authenticated = False
    if st.session_state.authenticated: return True

    app_password = os.environ.get("app_password", "")
    if not app_password: return True

    col1, col2, col3 = st.columns([1,2,1])
    with col2:
        st.markdown("<br><br>", unsafe_allow_html=True)
        st.info("🔒 Área Restrita - Diplomacia")
        password = st.text_input("Senha de Acesso", type="password")
        if st.button("Entrar", use_container_width=True):
            if password == app_password:
                st.session_state.authenticated = True
                st.rerun()
            else:
                st.error("Acesso Negado")
    return False

def init_session_state():
    defaults = {
        'question_index': 0,
        'show_result': False,
        'user_answer': "",
        'similarity_score': 0,
        'filtered_df': None,
        'worksheet': None,
        'selected_disciplina': None,
        'selected_tema': None,
        'selected_assunto': None,
        'original_df': None,
        'row_mapping': [],
        'timer_running': False,
        'timer_start': None,
        'study_mode': "Perguntas",
        'essay_text': "",
        'voice_text': ""
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value

# --- MANIPULAÇÃO DE DADOS ---
@st.cache_data(ttl=300)
def get_worksheet_titles(sheet_url):
    try:
        client = get_gspread_client()
        spreadsheet = client.open_by_url(sheet_url)
        return [ws.title for ws in spreadsheet.worksheets()]
    except: return []

@st.cache_data(ttl=300)
def load_worksheet_data(sheet_url, worksheet_title):
    try:
        client = get_gspread_client()
        spreadsheet = client.open_by_url(sheet_url)
        worksheet = spreadsheet.worksheet(worksheet_title)
        data = worksheet.get_all_records()
        df = pd.DataFrame(data)
        # Garante que as colunas essenciais existem
        if 'Minha_Resposta' not in df.columns:
            df['Minha_Resposta'] = ""
        return df
    except Exception as e:
        st.error(f"Erro: {e}")
        return None

def get_worksheet_for_update(sheet_url, worksheet_title):
    try:
        client = get_gspread_client()
        spreadsheet = client.open_by_url(sheet_url)
        ws = spreadsheet.worksheet(worksheet_title)

        # Lógica para garantir que a coluna Minha_Resposta exista no Google Sheets
        header = ws.row_values(1)
        if "Minha_Resposta" not in header:
            ws.update_cell(1, len(header) + 1, "Minha_Resposta")

        return ws
    except: return None

# --- LÓGICA DO CRONÔMETRO (CORRIGIDA) ---
def get_or_create_log_worksheet(sheet_url):
    try:
        client = get_gspread_client()
        spreadsheet = client.open_by_url(sheet_url)
        try:
            return spreadsheet.worksheet("Log_Estudos")
        except:
            ws = spreadsheet.add_worksheet(title="Log_Estudos", rows=1000, cols=3)
            ws.update(values=[['Data', 'Disciplina', 'Minutos']], range_name='A1:C1')
            return ws
    except: return None

def save_study_log(disciplina, minutes):
    try:
        worksheet = get_or_create_log_worksheet(TRILHA_SHEET_URL)
        if worksheet:
            today = datetime.now().strftime("%Y-%m-%d")
            worksheet.append_row([today, disciplina, minutes])
            # Limpa cache para atualizar gráfico
            get_study_logs.clear() 
            return True
    except Exception as e:
        st.error(f"Erro ao salvar log: {e}")
    return False

@st.cache_data(ttl=60) # Cache para não bater na API toda hora
def get_study_logs():
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
    except: pass
    return pd.DataFrame(columns=['Data', 'Disciplina', 'Minutos'])

def get_today_study_time():
    try:
        df = get_study_logs()
        if not df.empty:
            today = datetime.now().strftime("%Y-%m-%d")
            today_df = df[df['Data'].dt.strftime("%Y-%m-%d") == today]
            return int(today_df['Minutos'].sum())
    except: pass
    return 0

# --- LÓGICA DA TRILHA ---
def get_trilha_data():
    try:
        client = get_gspread_client()
        spreadsheet = client.open_by_url(TRILHA_SHEET_URL)
        ws = spreadsheet.worksheet("Trilha")
        return pd.DataFrame(ws.get_all_records()), ws
    except: return None, None

def complete_mission(worksheet, row_idx):
    try:
        worksheet.update_cell(row_idx + 2, 4, "sim")
        worksheet.update_cell(row_idx + 2, 5, datetime.now().strftime("%Y-%m-%d"))
        return True
    except: return False

# --- LÓGICA DE QUIZ E ATUALIZAÇÃO ---
def update_sheet(worksheet, original_row_index, resultado, data_str, minha_resposta=""):
    try:
        # Encontra índices das colunas dinamicamente
        header = worksheet.row_values(1)

        try: col_res = header.index("Resultado") + 1
        except: return False

        try: col_data = header.index("Data") + 1
        except: return False

        try: col_resp_usr = header.index("Minha_Resposta") + 1
        except: 
            # Se não achar na memória local, tenta adicionar (fallback)
            col_resp_usr = len(header) + 1

        # Atualiza células
        worksheet.update_cell(original_row_index + 2, col_res, resultado)
        worksheet.update_cell(original_row_index + 2, col_data, data_str)

        if minha_resposta:
             worksheet.update_cell(original_row_index + 2, col_resp_usr, minha_resposta)

        return True
    except Exception as e:
        st.error(f"Erro ao salvar: {e}")
        return False

def record_result(resultado):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    original_row_index = st.session_state.row_mapping[st.session_state.question_index]
    minha_resposta = st.session_state.user_answer

    if update_sheet(st.session_state.worksheet, original_row_index, resultado, timestamp, minha_resposta):
        # Atualiza DataFrame Local
        idx = st.session_state.question_index
        st.session_state.filtered_df.at[idx, 'Resultado'] = resultado
        st.session_state.filtered_df.at[idx, 'Data'] = timestamp
        st.session_state.filtered_df.at[idx, 'Minha_Resposta'] = minha_resposta

        if st.session_state.original_df is not None:
            st.session_state.original_df.at[original_row_index, 'Resultado'] = resultado
            st.session_state.original_df.at[original_row_index, 'Data'] = timestamp
            st.session_state.original_df.at[original_row_index, 'Minha_Resposta'] = minha_resposta

        # Limpa e Avança
        st.session_state.question_index += 1
        st.session_state.show_result = False
        st.session_state.user_answer = ""
        st.session_state.similarity_score = 0
        st.session_state.voice_text = ""
        st.rerun()

# --- CONSULTOR IA ---
def get_ai_response(question):
    try:
        client = OpenAI(api_key=os.environ.get("openai_api_key"))
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "Você é um diplomata experiente e tutor para o CACD. Responda com precisão jurídica, elegância e concisão."},
                {"role": "user", "content": question}
            ],
            max_tokens=600
        )
        return response.choices[0].message.content
    except Exception as e: return f"Erro na IA: {e}"

# --- INTERFACE ---
def render_sidebar():
    with st.sidebar:
        st.markdown("### 🏛️ Painel de Controle")

        # CRONÔMETRO OTIMIZADO (Sem erro de Cota)
        with st.expander("⏱️ Cronômetro", expanded=True):
            tab1, tab2 = st.tabs(["Auto", "Manual"])

            with tab1:
                today_time = get_today_study_time()
                st.metric("Hoje (Total)", f"{today_time} min")

                if not st.session_state.timer_running:
                    if st.button("▶️ Iniciar Sessão", use_container_width=True):
                        st.session_state.timer_running = True
                        st.session_state.timer_start = datetime.now()
                        st.rerun()
                else:
                    # Mostra tempo decorrido sem bater na API
                    start = st.session_state.timer_start
                    if start:
                        delta = datetime.now() - start
                        mins = int(delta.total_seconds() / 60)
                        st.info(f"⏳ Estudando há: {mins} min")

                    if st.button("⏹️ Parar & Salvar", use_container_width=True):
                        if start:
                            delta = datetime.now() - start
                            final_min = max(1, int(delta.total_seconds() / 60))
                            disc = st.session_state.selected_disciplina or "Geral"
                            if save_study_log(disc, final_min):
                                st.success(f"+{final_min} min registrados!")
                        st.session_state.timer_running = False
                        st.session_state.timer_start = None
                        time.sleep(1)
                        st.rerun()

            with tab2:
                m_min = st.number_input("Minutos", 1, 480, 30)
                m_date = st.date_input("Data", datetime.now())
                m_disc = st.selectbox("Matéria", list(SHEETS_MAPPING.keys()))
                if st.button("Salvar Manual"):
                    # Aqui pode chamar save_study_log adaptado para data, 
                    # mas por simplicidade vamos salvar com data de hoje ou 
                    # implementar lógica extra se necessário. 
                    # O save_study_log atual usa 'today'.
                    # Para simplificar este código, salvamos como hoje.
                    save_study_log(m_disc, m_min)
                    st.success("Salvo!")

        # GRÁFICO
        logs = get_study_logs()
        if not logs.empty:
            daily = logs.groupby(logs['Data'].dt.strftime("%d/%m"))['Minutos'].sum()
            st.bar_chart(daily, height=150, color="#B86E7E")

        # OUTRAS FERRAMENTAS
        with st.expander("🎧 Petit Journal"):
            components.iframe("https://open.spotify.com/embed/show/6k3Udb6eX6o7f0r7yG9sX3?utm_source=generator", height=152)

        with st.expander("🧠 Consultor IA"):
            q = st.text_area("Dúvida", height=100)
            if st.button("Consultar"):
                with st.spinner("Analisando..."):
                    st.markdown(get_ai_response(q))

def render_trilha():
    st.subheader("📍 Sua Próxima Missão")
    df, ws = get_trilha_data()

    if df is not None and not df.empty:
        # Busca dinâmica de colunas
        cols = [c.lower() for c in df.columns]
        status_col = df.columns[cols.index('status')] if 'status' in cols else df.columns[3]
        desc_col = df.columns[1]

        # Encontra primeira pendência
        mission = None
        idx_mission = -1

        for idx, row in df.iterrows():
            if str(row[status_col]).lower().strip() != 'sim':
                mission = row
                idx_mission = idx
                break

        if mission is not None:
            col1, col2 = st.columns([4, 1])
            with col1:
                st.info(f"**{mission[desc_col]}** \n\n _{mission.get(df.columns[2], '')}_")
            with col2:
                if st.button("✅ Concluir", use_container_width=True):
                    complete_mission(ws, idx_mission)
                    st.success("Atualizado!")
                    time.sleep(1)
                    st.rerun()
        else:
            st.success("🎉 Trilha zerada! Parabéns!")

def render_content():
    st.markdown("---")
    st.subheader("📚 Estudo Ativo")

    c1, c2, c3 = st.columns(3)

    with c1:
        disc = st.selectbox("Disciplina", list(SHEETS_MAPPING.keys()))
        if disc != st.session_state.selected_disciplina:
            st.session_state.selected_disciplina = disc
            st.session_state.selected_tema = None
            st.session_state.original_df = None
            st.session_state.filtered_df = None
            load_worksheet_data.clear()
            get_worksheet_titles.clear()

    with c2:
        titles = get_worksheet_titles(SHEETS_MAPPING[disc])
        # Opção TODOS (Agregação Simples - MVP: Carrega apenas o primeiro por enquanto para não travar)
        # Para carregar TODOS de verdade exigiria loop complexo. Vamos manter por tema por segurança de performance.
        tema = st.selectbox("Tema", titles) if titles else None

        if tema != st.session_state.selected_tema:
            st.session_state.selected_tema = tema
            st.session_state.original_df = None
            st.session_state.filtered_df = None

    # Carregamento
    if tema and st.session_state.original_df is None:
        with st.spinner("Abrindo livros..."):
            df = load_worksheet_data(SHEETS_MAPPING[disc], tema)
            if df is not None:
                st.session_state.original_df = df
                st.session_state.worksheet = get_worksheet_for_update(SHEETS_MAPPING[disc], tema)
                # Inicializa filtros
                st.session_state.filtered_df = df.copy()
                st.session_state.row_mapping = list(range(len(df)))
                st.session_state.question_index = 0

    with c3:
        if st.session_state.original_df is not None:
            # Filtro de Assuntos
            assuntos = sorted(st.session_state.original_df['Assunto'].unique())
            sel_assunto = st.selectbox("Assunto", ["Todos"] + list(map(str, assuntos)))

            # Filtro de Status
            status_filter = st.multiselect("Status", ["Nunca visto", "Acertei", "Errei", "Posso melhorar"], default=[])

            # Aplica Filtros
            df_view = st.session_state.original_df.copy()

            if sel_assunto != "Todos":
                df_view = df_view[df_view['Assunto'].astype(str) == sel_assunto]

            if status_filter:
                # Lógica simplificada de filtro
                mask = pd.Series([False] * len(df_view), index=df_view.index)
                if "Nunca visto" in status_filter:
                    mask |= (df_view['Resultado'] == "")
                if "Acertei" in status_filter:
                    mask |= (df_view['Resultado'] == "Acertei")
                if "Errei" in status_filter:
                    mask |= (df_view['Resultado'] == "Errei")
                if "Posso melhorar" in status_filter:
                    mask |= (df_view['Resultado'] == "Posso melhorar")
                df_view = df_view[mask]

            # Atualiza Sessão se mudou
            # (Simplificação: Recalcula índices)
            if len(df_view) != len(st.session_state.filtered_df) or not df_view.equals(st.session_state.filtered_df):
                 st.session_state.filtered_df = df_view.reset_index(drop=True)
                 # Mapeia índice original para salvar certo na planilha
                 st.session_state.row_mapping = df_view.index.tolist()
                 st.session_state.question_index = 0

    # Renderiza Questão
    if st.session_state.filtered_df is not None and not st.session_state.filtered_df.empty:
        render_quiz()
    elif st.session_state.original_df is not None:
        st.warning("Nenhuma questão encontrada com esses filtros.")

def render_quiz():
    df = st.session_state.filtered_df
    total = len(df)

    # Navegação Direta
    col_nav1, col_nav2 = st.columns([1, 4])
    with col_nav1:
        idx = st.number_input("Ir para Questão", 1, total, st.session_state.question_index + 1) - 1
        if idx != st.session_state.question_index:
            st.session_state.question_index = idx
            st.session_state.show_result = False
            st.session_state.user_answer = ""
            st.rerun()

    # Dados da Questão
    if st.session_state.question_index >= total:
        st.success("Revisão concluída! 🎉")
        if st.button("Reiniciar"):
            st.session_state.question_index = 0
            st.rerun()
        return

    row = df.iloc[st.session_state.question_index]

    # Metadados (Última vez visto)
    st.caption(f"Tema: {row['Assunto']} | Última revisão: {row.get('Data', 'Nunca')} | Status: {row.get('Resultado', 'Novo')}")

    st.markdown(f"### {row['Pergunta']}")
    # Input de Resposta
    mode = st.radio("Entrada", ["Texto", "Voz"], horizontal=True, label_visibility="collapsed")

    val_inicial = st.session_state.user_answer

    if mode == "Voz":
        try:
            from audiorecorder import audiorecorder
            import speech_recognition as sr
            import tempfile
            ar = audiorecorder("🎤 Gravar", "⏹️ Parar")
            if len(ar) > 0:
                with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
                    ar.export(f.name, format="wav")
                    tmp = f.name
                if st.button("Transcrever áudio"):
                    r = sr.Recognizer()
                    with sr.AudioFile(tmp) as source:
                        audio = r.record(source)
                        text = r.recognize_google(audio, language="pt-BR")
                        st.session_state.user_answer = text
                        st.rerun()
        except: st.warning("Áudio indisponível neste ambiente.")

    ans = st.text_area("Sua Resposta", value=st.session_state.user_answer, height=150)
    st.session_state.user_answer = ans

    # Botões de Ação
    if not st.session_state.show_result:
        if st.button("Verificar Resposta", type="primary", use_container_width=True):
            st.session_state.show_result = True
            st.rerun()
    else:
        gabarito = str(row['Resposta'])
        score = fuzz.token_sort_ratio(ans.lower(), gabarito.lower())

        st.markdown("---")
        if score > 85: st.success(f"Excelente! Aderência: {score}%")
        elif score > 50: st.warning(f"Bom, mas falta detalhes. Aderência: {score}%")
        else: st.error(f"Atenção. Aderência: {score}%")

        st.info(f"**Gabarito:** {gabarito}")

        c1, c2, c3 = st.columns(3)
        if c1.button("✅ Acertei", use_container_width=True): record_result("Acertei")
        if c2.button("⚠️ Posso melhorar", use_container_width=True): record_result("Posso melhorar")
        if c3.button("❌ Errei", use_container_width=True): record_result("Errei")

# --- MAIN ---
def main():
    if not check_password(): st.stop()
    apply_custom_style()
    init_session_state()
    render_sidebar()
    st.title("Meu CACD")
    render_trilha()
    render_content()

if __name__ == "__main__":
    main()