# Study Station LMS

## Overview
A high-performance Streamlit-based Learning Management System (LMS) that integrates with Google Sheets for study tracking, active recall quizzes, and AI-powered study assistance.

## Features

### Sidebar Features
- **Study Timer & History**: Stopwatch and manual entry for tracking study time with 7-day bar chart visualization
- **Spotify Player**: Embedded Petit Journal podcast player
- **AI Consultant**: OpenAI-powered quick question answering using gpt-4o-mini

### Main Content
- **Trilha Dashboard**: Advanced mission management with:
  - Mission selection from next 5 pending tasks via dropdown
  - Create New Mission feature with auto-ID assignment
  - Integrated focus timer with pause/resume and time accumulation
  - Tempo column for tracking time spent per mission
- **Study Material**: Multi-level filtering (Discipline, Theme, Subject)
- **Quiz Mode (Perguntas)**: Active recall with fuzzy matching, voice input support, and three-tier evaluation
- **Essay Mode (Dissertativo)**: Lists all topics to cover, then coverage analysis

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
6. **Minha_Resposta** - User's answer (auto-created, saved on submit)

### Trilha Worksheet
Tracks study missions with columns:
- **ID** - Mission identifier (auto-incremented)
- **Descrição** - Mission description
- **Disciplina** - Subject area
- **Status** - "sim" when complete, "não" when pending
- **Data** - Completion date
- **Tempo** - Minutes spent on mission (auto-created by app)

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
- 2024-12-27: Advanced Trilha features: mission selection (5 pending), create new mission, integrated focus timer with pause/resume, Tempo column for time tracking, essay mode lists all topics
- 2024-12-27: Fixed Spotify embed URL, updated OpenAI integration to use AI_INTEGRATIONS environment variables
- 2024-12-26: Added advanced review features: "Todos" theme aggregation, status/recency filters, jump-to-question navigation, review metadata display, Minha_Resposta column storage
- 2024-12-25: Major rebuild as Study Station LMS with timer, Spotify, AI consultant, Trilha dashboard, quiz/essay modes
- 2024-12-25: Added advanced filtering with discipline, tema, and assunto selection
- 2024-12-24: Initial creation of Active Recall Study Tool
