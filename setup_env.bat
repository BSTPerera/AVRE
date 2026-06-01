
@echo off
echo [INFO] Setting up AVRE Environment...

if not exist "venv" (
    echo [INFO] Creating virtual environment...
    python -m venv venv
) else (
    echo [INFO] Virtual environment already exists.
)

echo [INFO] Installing requirements...
call venv\Scripts\activate
pip install -r requirements.txt
python -m playwright install chromium

where git >nul 2>nul
if %errorlevel% neq 0 (
    echo [ERROR] Git is not found in your PATH!
    echo [ERROR] Please install Git from https://git-scm.com/
    pause
    exit /b 1
)

echo [INFO] Environment ready. Launching AVRE...
set PYTHONPATH=%CD%
set GIT_PYTHON_REFRESH=quiet
streamlit run avre/app.py
pause
