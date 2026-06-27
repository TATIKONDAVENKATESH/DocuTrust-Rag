@echo off
setlocal enabledelayedexpansion

set "ROOT_DIR=%~dp0"
set "BACKEND_DIR=%ROOT_DIR%backend"
set "VENV_DIR=%BACKEND_DIR%\.venv"

echo.
echo ============================================================
echo  DocuTrust — Local venv setup for PyCharm (Windows)
echo ============================================================
echo.

python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python not found. Install Python 3.11 and add to PATH.
    pause
    exit /b 1
)

echo [1/4] Creating virtual environment...
python -m venv "%VENV_DIR%"
if errorlevel 1 (
    echo [ERROR] Failed to create virtual environment.
    pause
    exit /b 1
)

echo [2/4] Upgrading pip...
"%VENV_DIR%\Scripts\python.exe" -m pip install --upgrade pip
if errorlevel 1 (
    echo [ERROR] pip upgrade failed.
    pause
    exit /b 1
)

echo.
echo [3/4] Installing CPU-only PyTorch...
echo       This may take a few minutes...
echo.
"%VENV_DIR%\Scripts\python.exe" -m pip install torch==2.3.0 --index-url https://download.pytorch.org/whl/cpu
if errorlevel 1 (
    echo [ERROR] PyTorch installation failed.
    pause
    exit /b 1
)

echo.
echo [4/4] Installing project dependencies...
echo       This may take several minutes...
echo.
"%VENV_DIR%\Scripts\python.exe" -m pip install -r "%BACKEND_DIR%\requirements.txt"
if errorlevel 1 (
    echo [ERROR] Dependency installation failed.
    pause
    exit /b 1
)

echo.
echo ============================================================
echo  SUCCESS! Virtual environment is ready.
echo ============================================================
echo.
echo Next steps in PyCharm:
echo   1. File ^> Settings ^> Project ^> Python Interpreter
echo   2. Gear icon ^> Add Interpreter ^> Add Local Interpreter
echo   3. Select "Existing" and browse to:
echo      %VENV_DIR%\Scripts\python.exe
echo   4. Click OK
echo.
pause
