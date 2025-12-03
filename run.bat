@echo off
REM ============================================
REM Integrated Surveillance System Launcher
REM ============================================

echo.
echo ============================================
echo   INTEGRATED SURVEILLANCE SYSTEM
echo ============================================
echo.

REM Check if Python is installed
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python is not installed or not in PATH
    echo Please install Python 3.8 or higher from python.org
    pause
    exit /b 1
)

echo [INFO] Python found
echo.

REM Navigate to the integrated_surveillance directory
cd /d "%~dp0"

REM Check if we're in the right directory
if not exist "app.py" (
    echo [ERROR] app.py not found!
    echo Please make sure this script is in the integrated_surveillance folder
    pause
    exit /b 1
)

echo [INFO] Starting Integrated Surveillance System...
echo.

REM Install/Update required packages silently
echo [INFO] Checking dependencies...
pip install --quiet Flask Flask-Login opencv-python numpy ultralytics torch torchvision Pillow 2>nul
if errorlevel 1 (
    echo [WARNING] Some packages may not have installed correctly
    echo The application will try to start anyway...
)

echo.
echo ============================================
echo   SERVER STARTING
echo ============================================
echo.
echo Access the application at:
echo   http://localhost:5000
echo.
echo Default Login Credentials:
echo   Username: admin
echo   Password: admin123
echo.
echo Press Ctrl+C to stop the server
echo ============================================
echo.

REM Start the Flask application
python app.py

REM If the application exits, pause so user can see any error messages
echo.
echo.
echo [INFO] Application stopped
pause
