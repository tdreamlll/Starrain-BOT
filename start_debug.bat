@echo off
setlocal enabledelayedexpansion
chcp 936 >nul 2>&1

cd /d "%~dp0"

cls
echo ================================================
echo Starrain-BOT Diagnostic Mode
echo ================================================
echo.
echo This mode will display detailed error information
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

echo Checking Python version...
python --version
echo.

REM Check if virtual environment exists
echo [STEP 1] Creating virtual environment...
if not exist "venv\" (
    python -m venv venv
    if errorlevel 1 (
        echo Error: Failed to create virtual environment
        echo Possible reasons:
        echo - Python not properly installed
        echo - Insufficient permissions
        echo - Antivirus blocking the operation
        echo.
        pause
        exit /b 1
    )
    echo [SUCCESS] Virtual environment created
    echo.
)

REM Activate virtual environment
echo [STEP 2] Activating virtual environment...
call venv\Scripts\activate.bat
if errorlevel 1 (
    echo Error: Failed to activate virtual environment
    echo The venv\Scripts\activate.bat file may be corrupted
    echo Try deleting the venv folder and run this script again
    echo.
    pause
    exit /b 1
)
echo [SUCCESS] Virtual environment activated
echo.

REM Check pip
echo [STEP 3] Checking pip...
pip --version
if errorlevel 1 (
    echo Warning: pip may not be working correctly
    echo.
)
echo.

echo [STEP 4] Checking Python modules...
python -c "import sys; print(f'Python version: {sys.version}')"
python -c "import asyncio; print('[OK] asyncio: installed')"
python -c "import yaml; print('[OK] yaml: installed')" 2>nul || echo "[ERROR] yaml: not installed"
python -c "import aiohttp; print('[OK] aiohttp: installed')" 2>nul || echo "[ERROR] aiohttp: not installed"
python -c "import websockets; print('[OK] websockets: installed')" 2>nul || echo "[ERROR] websockets: not installed"
python -c "import rich; print('[OK] rich: installed')" 2>nul || echo "[ERROR] rich: not installed"
python -c "import watchdog; print('[OK] watchdog: installed')" 2>nul || echo "[ERROR] watchdog: not installed"
python -c "import PIL; print('[OK] Pillow: installed')" 2>nul || echo "[ERROR] Pillow: not installed"
echo.

REM Ask if user wants to install dependencies
echo [STEP 5] Dependencies check
echo.
choice /C YN /M "Do you want to install/update dependencies"
if errorlevel 2 goto skip_install

echo.
echo Installing dependencies...
pip install -r requirements.txt --no-cache-dir
echo.

:skip_install

REM Check config file
echo [STEP 6] Checking configuration...
if not exist "config\config.yaml" (
    echo Error: config\config.yaml not found!
    echo Please copy config.yaml.example to config.yaml and configure it
    echo.
    pause
    exit /b 1
)
echo [SUCCESS] Configuration file found
echo.

REM Create log directory
if not exist "logs\" mkdir logs

REM Start bot
echo [STEP 7] Starting bot...
echo.
echo ================================================
echo Press Ctrl+C to stop the bot
echo ================================================
echo.

python src\main.py

REM If bot exits, show exit code
echo.
echo ================================================
echo Bot exited with code: %ERRORLEVEL%
echo ================================================
echo.

pause
