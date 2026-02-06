@echo off
setlocal enabledelayedexpansion
chcp 936 >nul 2>&1

cls
echo ================================================
echo Starrain-BOT Quick Start
echo ================================================
echo.

REM Check Python
python --version >nul 2>&1
if errorlevel 1 (
    echo Error: Python is not installed or not in PATH
    echo Please install Python 3.8+ from https://www.python.org/
    echo.
    pause
    exit /b 1
)

echo [OK] Python is available
echo.

REM Check virtual environment
if not exist "venv\" (
    echo Creating virtual environment...
    python -m venv venv
    if errorlevel 1 (
        echo Error: Failed to create virtual environment
        pause
        exit /b 1
    )
    echo.
    
    echo Installing dependencies...
    call venv\Scripts\activate.bat
    pip install -r requirements.txt --no-cache-dir
    if errorlevel 1 (
        echo.
        echo Warning: Some dependencies may have failed
        echo.
    )
    echo.
    echo [DONE] Setup complete
    echo.
)

REM Start bot
call venv\Scripts\activate.bat
python src\main.py

pause
