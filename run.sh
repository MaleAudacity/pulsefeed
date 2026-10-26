#!/usr/bin/env bash
# PulseFeed - 1-Click Launcher for macOS & Linux

DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"
cd "$DIR"

echo "=============================================================="
echo "          PulseFeed - Local RSS & Alert Engine"
echo "=============================================================="
echo ""

# Check python
if ! command -v python3 &> /dev/null; then
    echo "Python 3 is required. Please install Python 3.8+."
    exit 1
fi

# Check dependencies
python3 -c "import fastapi, uvicorn, feedparser" > /dev/null 2>&1
if [ $? -ne 0 ]; then
    echo "Installing required Python dependencies..."
    python3 -m pip install -r requirements.txt
fi

echo ""
echo "Starting PulseFeed at http://127.0.0.1:8000 ..."
python3 main.py
