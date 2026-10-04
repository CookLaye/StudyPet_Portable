#!/bin/bash
# Double-clickable wrapper: opens in Terminal and runs the real launcher.
cd "$(dirname "$0")" || exit 1
bash ./start_mac.sh
echo ""
read -r -p "Press Enter to close this window..."
