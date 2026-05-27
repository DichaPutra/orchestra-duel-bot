@echo off
title Yu-Gi-Oh! Master Duel Bot

echo ========================================
echo   Yu-Gi-Oh! Master Duel Bot — LLM-based
echo ========================================
echo.
echo Pastikan:
echo  1. Steam + Master Duel sudah jalan
echo  2. .env sudah diisi API key
echo  3. prompts/system.txt sudah diedit
echo.

:: Cek Python
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo ERROR: Python gak ketemu. Install Python 3.11+.
    pause
    exit /b 1
)

:: Cek .env
if not exist .env (
    echo ERROR: .env gak ada. Copy dari .env.example dan isi API key.
    pause
    exit /b 1
)

:: Run bot
python main.py %*
if %errorlevel% neq 0 (
    echo.
    echo Bot error. Cek logs/bot.log buat detail.
    pause
)
