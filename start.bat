@echo off
setlocal enabledelayedexpansion
chcp 936 >nul 2>&1

cls
echo ================================================
echo Starrain-BOT One-Click Start
echo ================================================
echo.

REM Check virtual environment
if not exist "venv\" (
    echo [INFO] Virtual environment not found, running setup...
    echo.
    python setup.py
    if errorlevel 1 (
        echo.
        echo [ERROR] Virtual environment setup failed!
        pause
        exit /b 1
    )
    echo.
)

REM Activate virtual environment and run
if exist "venv\Scripts\activate.bat" (
    echo [INFO] Activating virtual environment...
    call venv\Scripts\activate.bat
    echo.
    echo [INFO] Starting bot...
    echo.
    python src\main.py
    if errorlevel 1 (
        echo.
        echo [ERROR] Bot execution failed!
        echo.
        pause
        exit /b 1
    )
) else (
    echo [ERROR] Virtual environment activation script not found!
    echo Please run: python setup.py
    echo.
    pause
    exit /b 1
)

pause
