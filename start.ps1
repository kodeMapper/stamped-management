# PowerShell Start Script for Integrated Surveillance System

Write-Host "============================================" -ForegroundColor Cyan
Write-Host "Integrated Surveillance System - Quick Start" -ForegroundColor Cyan
Write-Host "============================================" -ForegroundColor Cyan
Write-Host ""

# Check if virtual environment exists
if (-not (Test-Path "venv")) {
    Write-Host "Creating virtual environment..." -ForegroundColor Yellow
    python -m venv venv
    Write-Host ""
}

# Activate virtual environment
Write-Host "Activating virtual environment..." -ForegroundColor Yellow
& ".\venv\Scripts\Activate.ps1"

# Install dependencies
Write-Host ""
Write-Host "Checking dependencies..." -ForegroundColor Yellow
pip install -q -r requirements.txt

# Copy YOLO model if not exists
if (-not (Test-Path "yolov8n.pt")) {
    if (Test-Path "..\final_weapon\yolov8n.pt") {
        Write-Host "Copying YOLO model..." -ForegroundColor Yellow
        Copy-Item "..\final_weapon\yolov8n.pt" -Destination "yolov8n.pt"
    }
}

# Start application
Write-Host ""
Write-Host "============================================" -ForegroundColor Green
Write-Host "Starting Integrated Surveillance System..." -ForegroundColor Green
Write-Host "============================================" -ForegroundColor Green
Write-Host ""
Write-Host "Access the dashboard at: http://localhost:5000" -ForegroundColor Cyan
Write-Host "Default credentials: admin / admin123" -ForegroundColor Cyan
Write-Host ""
Write-Host "Press Ctrl+C to stop the server" -ForegroundColor Yellow
Write-Host ""

python app.py
