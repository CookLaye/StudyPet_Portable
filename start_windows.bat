@echo off
:: Ultra-Safe Launcher - No Delayed Expansion, No Blocks
set "PROJECT_ROOT=%~dp0"
cd /d "%PROJECT_ROOT%"

echo ======================================================
echo        StudyPet - Zero-Setup Launcher (Windows)
echo ======================================================
echo.

:: 1. Check for Portable AI Backend (The "Local Studio" way)
if exist "bin\llama-server.exe" goto :LAUNCH_APP

:: 2. Check for Python
python --version >nul 2>&1
if %ERRORLEVEL% neq 0 goto :ERROR_PYTHON

:: 3. Setup Virtual Environment
if exist ".venv" goto :ACTIVATE_VENV
echo [!] No virtual environment found. Creating one...
python -m venv .venv
if %ERRORLEVEL% neq 0 goto :ERROR_VENV

:ACTIVATE_VENV
echo [!] Activating environment...
call .venv\Scripts\activate
if %ERRORLEVEL% neq 0 goto :ERROR_ACTIVATE

:: 4. Install Dependencies
echo [!] Checking for general dependencies...
python -m pip install --upgrade pip
python -m pip install --default-timeout=100 -r requirements.txt
if %ERRORLEVEL% neq 0 goto :ERROR_DEPS

echo [!] Installing AI Backend (llama-cpp-python)...
python -m pip install llama-cpp-python[server] --extra-index-url https://abetlen.github.io/llama-cpp-python/whl/cpu --prefer-binary
if %ERRORLEVEL% neq 0 goto :ERROR_AI

:: 5. AI Asset Setup
echo [!] Preparing AI model assets...
python src/utils/setup_ai.py
if %ERRORLEVEL% neq 0 echo [!] AI Setup had warnings, but attempting to launch...

:LAUNCH_APP
echo.
echo [V] Everything is ready. Starting StudyPet...
echo ------------------------------------------------------
python src/StudyPet.py
if %ERRORLEVEL% neq 0 echo [X] Application crashed with code %ERRORLEVEL%.

echo.
echo Application session ended.
pause
exit /b

:ERROR_PYTHON
echo [X] FATAL ERROR: Python not found.
echo Please install Python 3.10+ and check "Add Python to PATH".
pause
exit /b 1

:ERROR_VENV
echo [X] FATAL ERROR: Could not create virtual environment.
pause
exit /b 1

:ERROR_ACTIVATE
echo [X] FATAL ERROR: Could not activate .venv.
pause
exit /b 1

:ERROR_DEPS
echo [X] FATAL ERROR: Dependency installation failed.
pause
exit /b 1

:ERROR_AI
echo [X] FATAL ERROR: AI Backend installation failed.
echo Please install Visual Studio C++ Build Tools.
pause
exit /b 1
