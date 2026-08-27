@echo off
setlocal
cd /d "%~dp0"
where py >nul 2>nul
if %errorlevel%==0 (
  py -m pip install -r requirements.txt
  py -m streamlit run app.py
) else (
  python -m pip install -r requirements.txt
  python -m streamlit run app.py
)
pause
