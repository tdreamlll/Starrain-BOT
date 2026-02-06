@echo off
setlocal enabledelayedexpansion
chcp 936 >nul 2>&1

cls
echo ================================================
echo Starrain-BOT Environment Check
echo ================================================

REM Check Python
python --version >nul 2>&1
if errorlevel 1 (
    echo Error: Python is not installed or not in PATH
    echo Please install Python 3.8+ from https://www.python.org/
    echo.
    pause
    exit /b 1
)

echo Checking Python version...
python --version
echo.

REM Go to script directory
cd /d "%~dp0"

echo.
echo Running environment check script...
echo.

python test_env.py

pause
