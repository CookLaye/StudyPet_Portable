#!/bin/bash

# StudyPet - Zero-Setup Launcher (macOS)
# Flow: uv -> Python env (.venv) -> core deps -> face-scan deps (optional) -> AI assets -> launch.
# Every step is safe to repeat: when everything is already installed it does nothing and starts the app.

# Python version the project is developed and tested on
PY_VERSION="3.13"

# Set project root
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_ROOT" || exit 1

# Text colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

VENV_PY=".venv/bin/python"
SCAN_OK=1

echo "======================================================"
echo "       StudyPet - Zero-Setup Launcher (macOS)"
echo "======================================================"
echo ""

# Helper for fatal errors
fatal_error() {
    echo -e "${RED}[X] FATAL ERROR: $1${NC}"
    echo ""
    read -r -p "Press Enter to exit..."
    exit 1
}

# True on Apple Silicon, even inside a Rosetta terminal (where `uname -m` lies and says x86_64)
is_apple_silicon() {
    [ "$(uname -m)" = "arm64" ] || [ "$(sysctl -in hw.optional.arm64 2>/dev/null)" = "1" ]
}

# 1. Ensure 'bin' directory exists
mkdir -p bin

# 2. Check for uv (Standalone Python Manager)
if [ ! -x "bin/uv" ]; then
    echo -e "${YELLOW}[!] uv not found. Downloading standalone Python manager...${NC}"
    if is_apple_silicon; then
        UV_URL="https://github.com/astral-sh/uv/releases/latest/download/uv-aarch64-apple-darwin.tar.gz"
    else
        UV_URL="https://github.com/astral-sh/uv/releases/latest/download/uv-x86_64-apple-darwin.tar.gz"
    fi

    TMP_DIR="$(mktemp -d)"
    # -f: an HTTP error (404 etc.) is an error, not a saved HTML page
    if ! curl -fL --retry 3 "$UV_URL" -o "$TMP_DIR/uv.tar.gz"; then
        rm -rf "$TMP_DIR"
        fatal_error "Failed to download uv. Check your internet connection and run this file again."
    fi
    if ! tar -xzf "$TMP_DIR/uv.tar.gz" -C "$TMP_DIR"; then
        rm -rf "$TMP_DIR"
        fatal_error "Could not unpack the downloaded uv archive."
    fi
    # The tarball extracts into a sub-folder; find the binary wherever it is.
    UV_FOUND="$(find "$TMP_DIR" -name uv -type f | head -n 1)"
    if [ -z "$UV_FOUND" ]; then
        rm -rf "$TMP_DIR"
        fatal_error "Could not find uv binary after extraction."
    fi
    mv "$UV_FOUND" bin/uv
    chmod +x bin/uv
    xattr -d com.apple.quarantine bin/uv 2>/dev/null || true
    rm -rf "$TMP_DIR"
fi
UV_BIN="bin/uv"

# 3. Python environment (.venv), pinned to $PY_VERSION (uv downloads that Python if needed)
if [ ! -x "$VENV_PY" ]; then
    echo -e "${YELLOW}[!] Creating standalone Python $PY_VERSION environment...${NC}"
    "$UV_BIN" venv --python "$PY_VERSION" .venv || fatal_error "Could not create virtual environment."
fi

# 4a. Core dependencies (required).
#     First try OFFLINE: if everything is already installed this succeeds instantly with no network.
#     --python makes uv always target THIS project's .venv, never some other active environment.
if ! "$UV_BIN" pip install --quiet --offline --python "$VENV_PY" -r requirements.txt >/dev/null 2>&1; then
    echo -e "${YELLOW}[!] Installing core dependencies (first run or requirements changed)...${NC}"
    "$UV_BIN" pip install --python "$VENV_PY" -r requirements.txt \
        || fatal_error "Dependency installation failed. Check your internet connection and run this file again."
fi

# 4b. Face-scan dependencies (optional: StudyPet starts without them).
#     One-time cleanup: older versions of this project installed plain opencv-python next to
#     opencv-contrib-python. Two OpenCV packages overwrite each other's files, so remove them all once
#     and let requirements-scan.txt install a single clean copy.
if [ ! -f ".venv/.cv2_single" ]; then
    "$UV_BIN" pip uninstall --python "$VENV_PY" opencv-python opencv-python-headless opencv-contrib-python >/dev/null 2>&1 || true
fi

if ! "$UV_BIN" pip install --quiet --offline --python "$VENV_PY" -r requirements-scan.txt >/dev/null 2>&1; then
    echo -e "${YELLOW}[!] Installing face-scan libraries (first run or requirements changed)...${NC}"
    rm -f .venv/.scan_import_ok
    if ! "$UV_BIN" pip install --python "$VENV_PY" -r requirements-scan.txt; then
        SCAN_OK=0
        echo -e "${YELLOW}[!] The face-scan libraries could not be installed on this Mac.${NC}"
        if ! is_apple_silicon; then
            echo -e "${YELLOW}    Reason (likely): the face scan needs an Apple Silicon Mac (M1 or newer); Intel Macs are not supported by these libraries.${NC}"
        elif [ "$(sw_vers -productVersion | cut -d. -f1)" -lt 14 ]; then
            echo -e "${YELLOW}    Reason (likely): the face scan needs macOS 14 (Sonoma) or newer. Your macOS is $(sw_vers -productVersion).${NC}"
        else
            echo -e "${YELLOW}    Check your internet connection and run this file again.${NC}"
        fi
        echo -e "${YELLOW}    StudyPet will still start; only the facial stress scan will be unavailable.${NC}"
    fi
fi

if [ "$SCAN_OK" = "1" ]; then
    touch .venv/.cv2_single
    # One-time check that the libraries really load (catches broken installs with a readable message).
    if [ ! -f ".venv/.scan_import_ok" ]; then
        if "$VENV_PY" -c "import cv2, numpy, onnxruntime, mediapipe" 2>/tmp/studypet_import_check.txt; then
            touch .venv/.scan_import_ok
        else
            SCAN_OK=0
            echo -e "${YELLOW}[!] The face-scan libraries are installed but cannot be loaded:${NC}"
            cat /tmp/studypet_import_check.txt
            echo -e "${YELLOW}    StudyPet will still start; the facial stress scan may be unavailable.${NC}"
        fi
    fi
fi

# 4c. Camera permission (first run only). macOS asks per app; the app here is Terminal.
#     Asking from a plain script (main thread, no window) is far more reliable than asking from
#     inside the app's background scan thread.
if [ "$SCAN_OK" = "1" ] && [ ! -f ".venv/.camera_prompted" ]; then
    echo -e "${YELLOW}[!] macOS may now ask to let Terminal use the camera. Please click Allow.${NC}"
    "$VENV_PY" -c "import cv2; c = cv2.VideoCapture(0, cv2.CAP_AVFOUNDATION); print('Camera opened:', c.isOpened()); c.release()" 2>/dev/null
    touch .venv/.camera_prompted
fi

# 5. AI assets: llama-server + chat model + face-scan models. Does nothing if all are present and valid.
if ! "$VENV_PY" src/utils/setup_ai.py; then
    echo -e "${YELLOW}[!] AI setup did not finish. StudyPet will start, but parts of it will not work${NC}"
    echo -e "${YELLOW}    (chat and/or face scan) until it succeeds. Connect to the internet and run this file again.${NC}"
fi

# 6. Launch
echo -e "\n${GREEN}[V] Setup finished. Starting StudyPet...${NC}"
echo "------------------------------------------------------"
"$VENV_PY" src/StudyPet.py
APP_STATUS=$?
if [ $APP_STATUS -ne 0 ]; then
    echo -e "${RED}[X] StudyPet exited with an error (code $APP_STATUS).${NC}"
fi

echo ""
echo "Application session ended."
