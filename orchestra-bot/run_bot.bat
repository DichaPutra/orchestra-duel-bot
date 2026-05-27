@echo off
title Orchestra Duel Bot (Opsi B — Memory First)

echo.
echo ╔══════════════════════════════════════╗
echo ║   Orchestra Duel Bot — Memory Mode   ║
║   LP + Phase + Turn dari memory       ║
║   Kartu dari Vision (LLM)             ║
╚══════════════════════════════════════╝
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

:: Check psutil (needed for memory hacking)
python -c "import psutil" 2>nul
if %errorlevel% neq 0 (
    echo [INFO] Installing psutil for memory hacking...
    pip install psutil
)

:: Optional: auto-calibrate on first run
if not exist memory_offsets.txt (
    echo [INFO] No memory offsets found. Auto-calibrating...
    python auto_calibrate.py --save
)

:: Run
echo [INFO] Starting Orchestra Bot (Memory + Vision hybrid)...
python main.py

if %errorlevel% neq 0 (
    echo [ERROR] Bot crashed. Check logs above.
    pause
)
