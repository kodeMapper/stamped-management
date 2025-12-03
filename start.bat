@echo off
echo ============================================
echo Integrated Surveillance System - Quick Start
echo ============================================
echo.

REM Check if virtual environment exists
if not exist "venv\" (
    echo Creating virtual environment...
    python -m venv venv
    echo.
)

REM Activate virtual environment
echo Activating virtual environment...
call venv\Scripts\activate.bat

REM Install dependencies if needed
echo.
echo Checking dependencies...
pip install -q -r requirements.txt

REM Copy YOLO model if not exists
if not exist "yolov8n.pt" (
    if exist "..\final_weapon\yolov8n.pt" (
        echo Copying YOLO model...
        copy "..\final_weapon\yolov8n.pt" "yolov8n.pt"
    )
)

REM Start the application
echo.
echo ============================================
echo Starting Integrated Surveillance System...
echo ============================================
echo.
echo Access the dashboard at: http://localhost:5000
echo Default credentials: admin / admin123
echo.
echo Press Ctrl+C to stop the server
echo.

python app.py

pause
