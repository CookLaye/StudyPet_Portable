#!/bin/bash

# StudyPet - Zero-Setup Launcher (macOS)
# Using uv for standalone Python environment management

# Set project root
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_ROOT"

# Text colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo "======================================================"
echo "       StudyPet - Zero-Setup Launcher (macOS)"
echo "======================================================"
echo ""

# Helper for fatal errors
fatal_error() {
    echo -e "${RED}[X] FATAL ERROR: $1${NC}"
    echo ""
    read -p "Press Enter to exit..."
    exit 1
}

# 1. Ensure 'bin' directory exists
mkdir -p bin

# 2. Check for uv (Standalone Python Manager)
if [ -f "bin/uv" ]; then
    UV_BIN="bin/uv"
else
    echo -e "${YELLOW}[!] uv not found. Downloading standalone Python manager...${NC}"
    # Detect architecture for uv binary
    ARCH=$(uname -m)
    if [ "$ARCH" == "arm64" ]; then
        UV_URL="https://github.com/astral-sh/uv/releases/latest/download/uv-aarch64-apple-darwin.tar.gz"
    else
        UV_URL="https://github.com/astral-sh/uv/releases/latest/download/uv-x86_64-apple-darwin.tar.gz"
    fi

    curl -L "$UV_URL" -o bin/uv.tar.gz || fatal_error "Failed to download uv."
    tar -xzf bin/uv.tar.gz -C bin/
    rm bin/uv.tar.gz

    # uv tarballs usually extract into a subdirectory. Find the binary and move it to bin/
    find bin/ -name "uv" -type f -exec mv {} bin/uv \;
    chmod +x bin/uv

    if [ ! -f "bin/uv" ]; then
        fatal_error "Could not find uv binary after extraction."
    fi
    UV_BIN="bin/uv"
fi

# 3. Portable-First Check for AI Backend
if [[ -f "bin/llama-server" ]] || [[ -f "assets/models/gpt_pet/bin/llama-server" ]]; then
    echo -e "${GREEN}[V] Portable AI Backend found. Skipping installation...${NC}"
    goto_launch=true
else
    goto_launch=false
fi

if [ "$goto_launch" = true ]; then
    echo -e "\n${GREEN}[V] Everything is ready. Starting StudyPet...${NC}"
    echo "------------------------------------------------------"
    # Use the venv python if it exists, otherwise use uv run
    if [ -f ".venv/bin/python" ]; then
        .venv/bin/python src/StudyPet.py
    else
        $UV_BIN run src/StudyPet.py
    fi
    if [ $? -ne 0 ]; then
        echo -e "${RED}[X] Application crashed with code $?.${NC}"
    fi
    echo ""
    echo "Application session ended."
    exit 0
fi

# 4. Setup Virtual Environment using uv
if [ ! -d ".venv" ]; then
    echo -e "${YELLOW}[!] Creating standalone Python environment...${NC}"
    $UV_BIN venv || fatal_error "Could not create virtual environment."
fi

# 5. Install Dependencies using uv
echo -e "${YELLOW}[!] Syncing dependencies...${NC}"
$UV_BIN pip install -r requirements.txt || fatal_error "Dependency installation failed."

echo -e "${YELLOW}[!] Installing AI Backend (llama-cpp-python) with Metal support...${NC}"
CMAKE_ARGS="-DLLAMA_METAL=on" $UV_BIN pip install "llama-cpp-python[server]" --prefer-binary || fatal_error "AI Backend installation failed."

# 6. AI Asset Setup
echo -e "${YELLOW}[!] Preparing AI model assets...${NC}"
.venv/bin/python src/utils/setup_ai.py
if [ $? -ne 0 ]; then
    echo -e "${YELLOW}[!] AI Setup had warnings, but attempting to launch...${NC}"
fi

# 7. Application Launch
echo -e "\n${GREEN}[V] Everything is ready. Starting StudyPet...${NC}"
echo "------------------------------------------------------"
.venv/bin/python src/StudyPet.py
if [ $? -ne 0 ]; then
    echo -e "${RED}[X] Application crashed with code $?.${NC}"
fi

echo ""
echo "Application session ended."
