@echo off
REM ComfyUI Indexer - Start Web Server
REM Activates the virtual environment and launches the web UI

echo Starting ComfyUI Indexer...
echo.

REM Check if venv exists
if not exist "venv\Scripts\activate.bat" (
    echo ERROR: Virtual environment not found!
    echo Please run install-comfy-idx.bat first.
    pause
    exit /b 1
)

REM Activate venv
call venv\Scripts\activate.bat

REM Start the server
echo.
echo ========================================
echo ComfyUI Indexer Web Server
echo ========================================
echo.
echo Server starting at: http://localhost:8000
echo Press Ctrl+C to stop the server
echo.

comfy-idx serve --host 127.0.0.1 --port 8000
