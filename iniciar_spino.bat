@echo off
REM Spino - abre o Modulo 2 e o painel com dois cliques.
cd /d "%~dp0"
chcp 65001 >nul

if not exist ".venv\Scripts\python.exe" (
    echo Ambiente .venv nao encontrado. Rode antes:
    echo   py -m venv .venv
    echo   .venv\Scripts\python.exe -m pip install -r requirements.txt
    pause
    exit /b 1
)
if not exist ".env" (
    echo Arquivo .env nao encontrado. Copie .env.example para .env e ajuste a porta COM.
    pause
    exit /b 1
)

start "Spino - Modulo 2" cmd /k ".venv\Scripts\python.exe -m app.main"
timeout /t 3 /nobreak >nul
start "Spino - Painel" cmd /k ".venv\Scripts\python.exe -m streamlit run dashboard\app.py"
