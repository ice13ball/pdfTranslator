#Requires -Version 5.1

<#
.SYNOPSIS
    Installs dependencies for the PDF Translator app.
.DESCRIPTION
    This script checks for Python, creates a virtual environment,
    and installs all required dependencies from requirements.txt.
.NOTES
    Requires Python 3.12 or later to be installed.
#>

# Check if Python is installed
$pythonCmd = Get-Command python -ErrorAction SilentlyContinue
if (!$pythonCmd) {
    Write-Host "Error: Python is not installed or not in PATH." -ForegroundColor Red
    Write-Host "Please install Python 3.12 from https://python.org/downloads/" -ForegroundColor Yellow
    exit 1
}

# Check Python version (basic check)
$pythonVersion = python --version 2>&1
if ($pythonVersion -notmatch "Python 3\.(1[2-9]|[2-9][0-9])") {
    Write-Host "Warning: Python version might not be compatible. Recommended: Python 3.12" -ForegroundColor Yellow
    Write-Host "Current version: $pythonVersion" -ForegroundColor Yellow
}

Write-Host "Creating virtual environment..." -ForegroundColor Green
python -m venv venv

if ($LASTEXITCODE -ne 0) {
    Write-Host "Error: Failed to create virtual environment." -ForegroundColor Red
    exit 1
}

Write-Host "Activating virtual environment..." -ForegroundColor Green
& .\venv\Scripts\Activate.ps1

if ($LASTEXITCODE -ne 0) {
    Write-Host "Error: Failed to activate virtual environment." -ForegroundColor Red
    exit 1
}

Write-Host "Installing dependencies..." -ForegroundColor Green
pip install -r requirements.txt

if ($LASTEXITCODE -ne 0) {
    Write-Host "Error: Failed to install dependencies." -ForegroundColor Red
    exit 1
}

Write-Host "Installation complete!" -ForegroundColor Green
Write-Host ""
Write-Host "Next steps:" -ForegroundColor Cyan
Write-Host "1. Copy .env.example to .env and fill in your Azure OpenAI credentials" -ForegroundColor White
Write-Host "2. Run 'python app.py' to start the application" -ForegroundColor White
Write-Host "3. Open http://127.0.0.1:5000 in your browser" -ForegroundColor White
