@echo off
setlocal enabledelayedexpansion
chcp 936 >nul 2>&1

cls
echo ================================================
echo Starrain-BOT Environment Check
echo ================================================

REM Go to script directory
cd /d "%~dp0"

REM Detect and use virtual environment if available
set "PYTHON_EXE=python"
set "VENV_FOUND=0"

REM Check for virtual environment in common locations
if exist "venv\Scripts\python.exe" (
    set "PYTHON_EXE=venv\Scripts\python.exe"
    set "VENV_FOUND=1"
    echo [INFO] Found virtual environment: venv\
) else if exist ".venv\Scripts\python.exe" (
    set "PYTHON_EXE=.venv\Scripts\python.exe"
    set "VENV_FOUND=1"
    echo [INFO] Found virtual environment: .venv\
)

REM Check Python
"%PYTHON_EXE%" --version >nul 2>&1
if errorlevel 1 (
    echo Error: Python is not installed or not in PATH
    echo Please install Python 3.8+ from https://www.python.org/
    echo.
    pause
    exit /b 1
)

echo Checking Python version...
"%PYTHON_EXE%" --version
if %VENV_FOUND%==1 (
    echo [INFO] Using virtual environment
) else (
    echo [WARNING] No virtual environment detected, using system Python
)
echo.

echo.
echo Running environment check script...
echo.

"%PYTHON_EXE%" test_env.py

pause
