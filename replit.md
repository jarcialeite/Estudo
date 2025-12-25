# Study Station LMS

## Overview
A high-performance Streamlit-based Learning Management System (LMS) that integrates with Google Sheets for study tracking, active recall quizzes, and AI-powered study assistance.

## Features

### Sidebar Features
- **Study Timer & History**: Stopwatch and manual entry for tracking study time with 7-day bar chart visualization
- **Spotify Player**: Embedded Petit Journal podcast player
- **AI Consultant**: OpenAI-powered quick question answering using gpt-4o-mini

### Main Content
- **Trilha Dashboard**: Shows next uncompleted mission from the Trilha worksheet
- **Study Material**: Multi-level filtering (Discipline, Theme, Subject)
- **Quiz Mode (Perguntas)**: Active recall with fuzzy matching, voice input support, and three-tier evaluation
- **Essay Mode (Dissertativo)**: Coverage analysis against all answers for selected subject

## Available Disciplines
- Direito
- Geografia
- História Mundial
- História do Brasil
- Política Internacional
- Economia
- Francês
- Inglês

## Google Sheet Structure

### Content Worksheets
1. **Assunto** - Subject/Topic
2. **Pergunta** - Question
3. **Resposta** - Reference Answer
4. **Resultado** - Result (updated by app)
5. **Data** - Date (updated by app)

### Trilha Worksheet
Tracks study missions with Status column (set to "sim" when complete)

### Log_Estudos Worksheet
Auto-created to track study time with columns: Data, Disciplina, Minutos

## Project Structure
- `app.py` - Main Streamlit LMS application
- `google_sheets_auth.py` - Google Sheets authentication using Replit connector
- `.streamlit/config.toml` - Streamlit server configuration

## Running the Application
```bash
streamlit run app.py --server.port 5000
```

## Environment Variables (via Replit AI Integrations)
- `AI_INTEGRATIONS_OPENAI_API_KEY` - OpenAI API key (auto-configured)
- `AI_INTEGRATIONS_OPENAI_BASE_URL` - OpenAI base URL (auto-configured)

## Optional Secrets
- `app_password` - Optional password protection for the app

## Dependencies
- streamlit
- pandas
- gspread
- oauth2client
- thefuzz
- python-Levenshtein
- requests
- google-auth
- openai
- matplotlib
- SpeechRecognition
- streamlit-audiorecorder

## Recent Changes
- 2024-12-25: Major rebuild as Study Station LMS with timer, Spotify, AI consultant, Trilha dashboard, quiz/essay modes
- 2024-12-25: Added advanced filtering with discipline, tema, and assunto selection
- 2024-12-24: Initial creation of Active Recall Study Tool
