@echo off
cd /d "%~dp0"
set STREAMLIT_BROWSER_GATHER_USAGE_STATS=false
set STREAMLIT_SERVER_SHOW_EMAIL_PROMPT=false
python -m streamlit run app.py --browser.gatherUsageStats false --server.showEmailPrompt false
