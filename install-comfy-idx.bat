@echo off
REM ComfyUI Indexer - Windows Installation Script
REM This script creates a virtual environment and installs the package

echo ========================================
echo ComfyUI Indexer - Installation
echo ========================================
echo.

REM Check if Python is available
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python is not installed or not in PATH
    echo Please install Python 3.10 or later from https://python.org
    pause
    exit /b 1
)

REM Check Python version
for /f "tokens=2 delims= " %%a in ('python --version 2^>^&1') do set PYVER=%%a
echo Found Python %PYVER%
echo.

REM Check if venv exists
if exist "venv" (
    echo Virtual environment already exists.
    echo Skipping venv creation...
) else (
    echo Creating virtual environment...
    python -m venv venv
    if errorlevel 1 (
        echo ERROR: Failed to create virtual environment
        pause
        exit /b 1
    )
    echo Virtual environment created successfully.
)
echo.

REM Activate venv and install
echo Installing ComfyUI Indexer...
call venv\Scripts\activate.bat

REM Upgrade pip first
python -m pip install --upgrade pip >nul 2>&1

REM Install the package
pip install -e .
if errorlevel 1 (
    echo ERROR: Installation failed
    pause
    exit /b 1
)

echo.
echo ========================================
echo Installation Complete!
echo ========================================
echo.
echo To use ComfyUI Indexer:
echo   1. Run start-server.bat to launch the web UI
echo   2. Or activate the venv and use the CLI:
echo      venv\Scripts\activate
echo      comfy-idx --help
echo.
pause
