#!/bin/bash

# StudyPet - Zero-Setup Launcher (macOS)
# Inspired by techjarves/Uncensored-Local-Studio

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

# 1. Portable-First Check
# Check common locations for a pre-compiled llama-server
if [[ -f "bin/llama-server" ]] || [[ -f "assets/models/gpt_pet/bin/llama-server" ]]; then
    echo -e "${GREEN}[V] Portable AI Backend found. Skipping installation...${NC}"
    goto_launch=true
else
    goto_launch=false
fi

if [ "$goto_launch" = true ]; then
    # Skip to launch
    echo -e "\n${GREEN}[V] Everything is ready. Starting StudyPet...${NC}"
    echo "------------------------------------------------------"
    python3 src/StudyPet.py
    if [ $? -ne 0 ]; then
        echo -e "${RED}[X] Application crashed with code $?.${NC}"
    fi
    echo ""
    echo "Application session ended."
    exit 0
fi

# 2. Check for Python 3
if ! command -v python3 &> /dev/null; then
    fatal_error "Python 3 not found. Please install it from python.org or via 'brew install python'."
fi

# 3. Setup Virtual Environment
if [ ! -d ".venv" ]; then
    echo -e "${YELLOW}[!] No virtual environment found. Creating one...${NC}"
    python3 -m venv .venv || fatal_error "Could not create virtual environment."
fi

echo -e "${YELLOW}[!] Activating environment...${NC}"
source .venv/bin/activate || fatal_error "Could not activate .venv."

# 4. Install Dependencies
echo -e "${YELLOW}[!] Checking for general dependencies...${NC}"
pip install --upgrade pip || echo "Warning: Failed to upgrade pip"
pip install --default-timeout=100 -r requirements.txt || fatal_error "Dependency installation failed."

echo -e "${YELLOW}[!] Installing AI Backend (llama-cpp-python) with Metal support...${NC}"
# Use CMAKE_ARGS to enable Metal for Apple Silicon
CMAKE_ARGS="-DLLAMA_METAL=on" pip install "llama-cpp-python[server]" --prefer-binary || fatal_error "AI Backend installation failed. Ensure you have Xcode Command Line Tools installed ('xcode-select --install')."

# 5. AI Asset Setup
echo -e "${YELLOW}[!] Preparing AI model assets...${NC}"
python3 src/utils/setup_ai.py
if [ $? -ne 0 ]; then
    echo -e "${YELLOW}[!] AI Setup had warnings, but attempting to launch...${NC}"
fi

# 6. Application Launch
echo -e "\n${GREEN}[V] Everything is ready. Starting StudyPet...${NC}"
echo "------------------------------------------------------"
python3 src/StudyPet.py
if [ $? -ne 0 ]; then
    echo -e "${RED}[X] Application crashed with code $?.${NC}"
fi

echo ""
echo "Application session ended."
