# Active Recall Study Tool

## Overview
A Streamlit-based study application that integrates with Google Sheets to provide an active recall learning experience. Users can review study questions, type their answers, compare them with reference answers using fuzzy string matching, and track their progress.

## Features
- Google Sheets integration for loading and updating study questions
- Session state management to track current question index
- Fuzzy string matching using thefuzz library (token_sort_ratio)
- Three-tier evaluation system: "Acertei" (Correct), "Posso melhorar" (Can improve), "Errei" (Incorrect)
- Automatic progress saving to Google Sheets with timestamps
- Visual feedback with color-coded similarity scores

## Google Sheet Structure
The Google Sheet should have these columns:
1. **Assunto** - Subject/Topic
2. **Pergunta** - Question
3. **Resposta** - Reference Answer
4. **Resultado** - Result (updated by the app)
5. **Data** - Date (updated by the app)

## Project Structure
- `app.py` - Main Streamlit application with quiz interface
- `google_sheets_auth.py` - Google Sheets authentication using Replit connector
- `.streamlit/config.toml` - Streamlit server configuration

## Running the Application
```bash
streamlit run app.py --server.port 5000
```

## Dependencies
- streamlit
- pandas
- gspread
- oauth2client
- thefuzz
- python-Levenshtein

## Recent Changes
- 2024-12-24: Initial creation of Active Recall Study Tool
