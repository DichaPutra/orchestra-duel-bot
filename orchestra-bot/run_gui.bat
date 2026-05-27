@echo off
title Orchestra Duel Bot GUI Launcher

echo.
echo ╔══════════════════════════════════════╗
echo ║   Orchestra Duel Bot — GUI Manager   ║
echo ║   Windows Desktop Launcher           ║
echo ╚══════════════════════════════════════╝
echo.

:: Check Python
where python >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python tidak ditemukan! Silakan install Python 3.11+.
    pause
    exit /b 1
)

:: Check .env
if not exist .env (
    echo [INFO] .env tidak ditemukan. Membuat .env baru dari .env.example...
    copy .env.example .env >nul
)

:: Check dependencies (zmq, loguru, json5, psutil, requests, PIL, pyautogui, dotenv)
python -c "import zmq, loguru, json5, psutil, requests, PIL, pyautogui, dotenv" 2>nul
if %errorlevel% neq 0 (
    echo [INFO] Ada dependency yang kurang. Menginstal requirements.txt...
    python -m pip install -r requirements.txt
)

:: Run GUI
echo [INFO] Meluncurkan Orchestra GUI...
start pythonw gui.py

if %errorlevel% neq 0 (
    echo [ERROR] Gagal meluncurkan GUI.
    pause
)
