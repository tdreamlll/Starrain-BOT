@echo off
chcp 65001 >nul 2>&1
cd /d "%~dp0"
set "PYTHON_EXE=python"
if exist "venv\Scripts\python.exe" set "PYTHON_EXE=venv\Scripts\python.exe"
if exist ".venv\Scripts\python.exe" set "PYTHON_EXE=.venv\Scripts\python.exe"
"%PYTHON_EXE%" test_env.py
pause
