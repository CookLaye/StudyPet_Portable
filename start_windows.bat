@echo off
setlocal
:: StudyPet - Zero-Setup Launcher (Windows)
:: Flow: uv -> Python env (.venv) -> core deps -> face-scan deps (optional) -> AI assets -> launch.
:: Every step is safe to repeat: when everything is already installed it does nothing and starts the app.

:: Python version the project is developed and tested on
set "PY_VERSION=3.13"

set "PROJECT_ROOT=%~dp0"
cd /d "%PROJECT_ROOT%"

set "UV_BIN=bin\uv.exe"
set "VENV_PY=.venv\Scripts\python.exe"
set "SCAN_OK=1"

echo ======================================================
echo        StudyPet - Zero-Setup Launcher (Windows)
echo ======================================================
echo.

:: 1. Ensure 'bin' directory exists
if not exist "bin" mkdir bin

:: 2. Check for uv (standalone Python manager)
if exist "%UV_BIN%" goto :HAVE_UV

echo [!] uv not found. Downloading standalone Python manager...
powershell -NoProfile -ExecutionPolicy Bypass -Command "$ProgressPreference='SilentlyContinue'; [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12; Invoke-WebRequest -UseBasicParsing -Uri 'https://github.com/astral-sh/uv/releases/latest/download/uv-x86_64-pc-windows-msvc.zip' -OutFile 'bin\uv.zip'; Expand-Archive -Path 'bin\uv.zip' -DestinationPath 'bin' -Force; Remove-Item 'bin\uv.zip'"

if not exist "%UV_BIN%" (
    echo [X] FATAL ERROR: Failed to download uv. Check your internet connection and run this file again.
    pause
    exit /b 1
)

:HAVE_UV

:: 3. Python environment (.venv), pinned to %PY_VERSION% (uv downloads that Python if needed)
if exist "%VENV_PY%" goto :HAVE_VENV

echo [!] Creating standalone Python %PY_VERSION% environment...
"%UV_BIN%" venv --python %PY_VERSION% .venv
if errorlevel 1 (
    echo [X] FATAL ERROR: Failed to create virtual environment.
    pause
    exit /b 1
)

:HAVE_VENV

:: 4a. Core dependencies (required).
::     First try OFFLINE: if everything is already installed this succeeds instantly with no network.
::     --python makes uv always target THIS project's .venv, never some other active environment.
"%UV_BIN%" pip install --quiet --offline --python "%VENV_PY%" -r requirements.txt >nul 2>&1
if not errorlevel 1 goto :CORE_OK

echo [!] Installing core dependencies (first run or requirements changed)...
"%UV_BIN%" pip install --python "%VENV_PY%" -r requirements.txt
if errorlevel 1 (
    echo [X] FATAL ERROR: Dependency installation failed. Check your internet connection and run this file again.
    pause
    exit /b 1
)

:CORE_OK

:: 4b. Face-scan dependencies (optional: StudyPet starts without them).
::     One-time cleanup: older versions of this project installed plain opencv-python next to
::     opencv-contrib-python. Two OpenCV packages overwrite each other's files and can break the
::     camera, so remove them all once and let requirements-scan.txt install a single clean copy.
if exist ".venv\.cv2_single" goto :SCAN_INSTALL
"%UV_BIN%" pip uninstall --python "%VENV_PY%" opencv-python opencv-python-headless opencv-contrib-python >nul 2>&1

:SCAN_INSTALL
"%UV_BIN%" pip install --quiet --offline --python "%VENV_PY%" -r requirements-scan.txt >nul 2>&1
if not errorlevel 1 goto :SCAN_INSTALLED

echo [!] Installing face-scan libraries (first run or requirements changed)...
if exist ".venv\.scan_import_ok" del ".venv\.scan_import_ok" >nul 2>&1
"%UV_BIN%" pip install --python "%VENV_PY%" -r requirements-scan.txt
if errorlevel 1 (
    set "SCAN_OK=0"
    echo [!] The face-scan libraries could not be installed on this computer.
    echo     StudyPet will still start, but the facial stress scan will be unavailable.
    goto :AI_SETUP
)

:SCAN_INSTALLED
echo ok> ".venv\.cv2_single"

:: One-time check that the libraries really load (catches broken installs with a readable message).
if exist ".venv\.scan_import_ok" goto :AI_SETUP
"%VENV_PY%" -c "import cv2, numpy, onnxruntime, mediapipe" >nul 2>"%TEMP%\studypet_import_check.txt"
if errorlevel 1 (
    set "SCAN_OK=0"
    echo [!] The face-scan libraries are installed but cannot be loaded:
    type "%TEMP%\studypet_import_check.txt"
    echo     If it mentions a missing DLL, install the Microsoft Visual C++ Redistributable ^(x64^):
    echo     https://aka.ms/vc14/vc_redist.x64.exe  then restart Windows and run this file again.
    goto :AI_SETUP
)
echo ok> ".venv\.scan_import_ok"

:AI_SETUP

:: 5. AI assets: llama-server + chat model + face-scan models. Does nothing if all are present and valid.
"%VENV_PY%" src\utils\setup_ai.py
if errorlevel 1 (
    echo [!] AI setup did not finish. StudyPet will start, but parts of it will not work
    echo     ^(chat and/or face scan^) until it succeeds. Connect to the internet and run this file again.
)

:: 6. Launch
echo.
echo [V] Setup finished. Starting StudyPet...
echo ------------------------------------------------------
"%VENV_PY%" src\StudyPet.py
set "APP_EXIT=%ERRORLEVEL%"
if not "%APP_EXIT%"=="0" echo [X] StudyPet exited with an error - code %APP_EXIT%.

echo.
echo Application session ended.
pause
exit /b
