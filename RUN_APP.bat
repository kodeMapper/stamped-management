@echo off
setlocal
title Integrated Surveillance System Launcher

echo ===============================================================================
echo                     INTEGRATED SURVEILLANCE SYSTEM
echo ===============================================================================
echo.

REM 1. Check for Python
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python is not installed or not in your PATH.
    echo Please install Python 3.8+ from https://www.python.org/downloads/
    echo and make sure to check "Add Python to PATH" during installation.
    pause
    exit /b
)

REM 2. Navigate to script directory
cd /d "%~dp0"

REM 3. Setup Virtual Environment
if not exist "venv" (
    echo [INFO] Creating virtual environment...
    python -m venv venv
    if %errorlevel% neq 0 (
        echo [ERROR] Failed to create virtual environment.
        pause
        exit /b
    )
)

REM 4. Activate Virtual Environment
echo [INFO] Activating virtual environment...
call venv\Scripts\activate.bat

REM 5. Install dependencies
echo [INFO] Installing dependencies...
pip install -r requirements.txt
if %errorlevel% neq 0 (
    echo [ERROR] Failed to install dependencies.
    pause
    exit /b
)

REM 6. Check for Model File
if not exist "yolov8n.pt" (
    echo [INFO] YOLO model not found. It will be downloaded automatically on first run.
    REM Optional: Try to copy from sibling directories if they exist
    if exist "..\final_weapon\yolov8n.pt" (
        echo [INFO] Found model in sibling directory, copying...
        copy "..\final_weapon\yolov8n.pt" "yolov8n.pt" >nul
    )
)

REM 7. Launch Browser and App
echo.
echo [INFO] Starting Application...
echo [INFO] Opening default browser to http://localhost:5000 ...
echo.

REM Start browser in a separate process after 5 seconds
start "" /B cmd /c "timeout /t 5 >nul & start http://localhost:5000"

REM Run the Flask App
python app.py

pause
