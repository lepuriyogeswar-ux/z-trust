@echo off
echo ============================================
echo  Z-TRUST - AI Verification Firewall
echo ============================================
echo.

REM Check for .env file
if not exist .env (
    echo [WARNING] .env file not found.
    echo Copying .env.example to .env...
    copy .env.example .env >nul
    echo Please edit .env and paste your GROQ_API_KEY.
    echo The server will start but verification will be limited.
    echo.
)

REM Activate virtual environment
if exist .venv\Scripts\activate.bat (
    call .venv\Scripts\activate.bat
) else (
    echo [ERROR] Virtual environment not found. Run:
    echo   python -m venv .venv
    echo   .venv\Scripts\activate
    echo   pip install -r requirements.txt
    pause
    exit /b 1
)

echo Starting Z-TRUST server...
echo.
echo   Web UI:  http://127.0.0.1:8000
echo   API Docs: http://127.0.0.1:8000/docs
echo   Health:   http://127.0.0.1:8000/health
echo.
echo Press Ctrl+C to stop.
echo.

python -m uvicorn main:app --host 127.0.0.1 --port 8000 --reload
