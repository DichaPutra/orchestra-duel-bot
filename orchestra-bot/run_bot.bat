@echo off
cd /d "%~dp0"
title Orchestra Duel Bot (Pure Memory Mode)

echo.
echo ╔══════════════════════════════════════╗
echo ║   Orchestra Duel Bot — Memory Mode   ║
echo ║   LP + Phase + Turn dari memory      ║
echo ║   Pure Memory (Tanpa Vision / AI)    ║
echo ╚══════════════════════════════════════╝
echo.

:: Check Python
where python >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python not found! Install Python 3.11+.
    pause
    exit /b 1
)

:: Check .env
if not exist .env (
    echo [WARN] .env not found. Copy .env.example to .env and set GEMINI_API_KEY.
    copy .env.example .env >nul
)

:: Check dependencies (zmq, loguru, json5, psutil, requests, PIL, pyautogui, dotenv)
python -c "import zmq, loguru, json5, psutil, requests, PIL, pyautogui, dotenv" 2>nul
if %errorlevel% neq 0 (
    echo [INFO] Missing dependencies. Installing requirements...
    python -m pip install -r requirements.txt
)

:: Optional: auto-calibrate on first run
if not exist memory_offsets.txt (
    echo [INFO] No memory offsets found. Auto-calibrating...
    python auto_calibrate.py --save
)

:: Run
echo [INFO] Starting Orchestra Bot (Pure Memory Mode)...
python main.py

if %errorlevel% neq 0 (
    echo [ERROR] Bot crashed. Check logs above.
    pause
)
