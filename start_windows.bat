@echo off
:: Ultra-Safe Launcher - Zero-Setup with uv
set "PROJECT_ROOT=%~dp0"
cd /d "%PROJECT_ROOT%"

echo ======================================================
echo        StudyPet - Zero-Setup Launcher (Windows)
echo ======================================================
echo.

:: 1. Ensure 'bin' directory exists
if not exist "bin" mkdir bin

:: 2. Check for uv (Standalone Python Manager)
if exist "bin\uv.exe" goto :USE_UV
echo [!] uv not found. Downloading standalone Python manager...
powershell -Command "[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12; Invoke-WebRequest -Uri 'https://github.com/astral-sh/uv/releases/latest/download/uv-x86_64-pc-windows-msvc.zip' -OutFile 'bin\uv.zip'"
powershell -Command "Expand-Archive -Path 'bin\uv.zip' -DestinationPath 'bin' -Force"
powershell -Command "Remove-Item 'bin\uv.zip'"
if not exist "bin\uv.exe" (
    echo [X] FATAL ERROR: Failed to download uv.
    pause
    exit /b 1
)

:USE_UV
set "UV_BIN=bin\uv.exe"

:: 3. Portable AI Backend Check
if exist "bin\llama-server.exe" goto :LAUNCH_APP

:: 4. Setup Virtual Environment using uv
if not exist ".venv" (
    echo [!] Creating standalone Python environment...
    %UV_BIN% venv
    if %ERRORLEVEL% neq 0 (
        echo [X] FATAL ERROR: Failed to create virtual environment.
        pause
        exit /b 1
    )
)

:: 5. Install Dependencies using uv
echo [!] Syncing dependencies...
%UV_BIN% pip install -r requirements.txt
if %ERRORLEVEL% neq 0 (
    echo [X] FATAL ERROR: Dependency installation failed.
    pause
    exit /b 1
)

echo [!] Installing build tools (cmake)...
%UV_BIN% pip install cmake
if %ERRORLEVEL% neq 0 echo [!] Warning: CMake installation failed, attempting to proceed...

echo [!] Installing AI Backend (llama-cpp-python)...
%UV_BIN% pip install llama-cpp-python[server] --extra-index-url https://abetlen.github.io/llama-cpp-python/whl/cpu
if %ERRORLEVEL% neq 0 (
    echo [X] FATAL ERROR: AI Backend installation failed.
    echo Try installing Visual Studio C++ Build Tools if this persists.
    pause
    exit /b 1
)

:: 6. AI Asset Setup
echo [!] Preparing AI model assets...
.venv\Scripts\python src/utils/setup_ai.py
if %ERRORLEVEL% neq 0 echo [!] AI Setup had warnings, but attempting to launch...

:LAUNCH_APP
echo.
echo [V] Everything is ready. Starting StudyPet...
echo ------------------------------------------------------
.venv\Scripts\python src/StudyPet.py
if %ERRORLEVEL% neq 0 echo [X] Application crashed with code %ERRORLEVEL%.

echo.
echo Application session ended.
pause
exit /b
