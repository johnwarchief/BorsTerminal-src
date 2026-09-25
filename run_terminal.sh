#!/bin/bash
# Linux/macOS launcher for BorsTerminal_Ultimate.
# Windows: use run_terminal.bat instead.
set -e

cd "$(dirname "$0")" || exit 1
echo "📁 $(basename "$0") — $(basename "$PWD")"

# Pillar: python3
if ! command -v python3 &>/dev/null; then
    echo "❌ python3 not found on PATH"
    echo "   Install: sudo apt install python3 python3-pip   (Debian/Ubuntu)"
    echo "            sudo dnf install python3 python3-pip   (Fedora)"
    read -rp "Press Enter to exit..."
    exit 1
fi
echo "✓ python3: $(python3 --version 2>&1)"

# Pillar: dependencies
echo "ℹ️  Checking / installing dependencies (first run may take a minute)..."
python3 -m pip install -r requirements.txt -q 2>&1 | tail -2 || {
    echo "⚠️  pip install had issues; trying full output..."
    python3 -m pip install -r requirements.txt 2>&1
}

# Verify critical deps
python3 -c "import uvicorn, fastapi, pandas, requests, numpy" 2>&1 || {
    echo "❌ Failed to import critical packages"
    read -rp "Press Enter to exit..."
    exit 1
}
echo "✓ All packages loaded"

# Launch
echo ""
echo "🚀 Starting server on http://localhost:8000"
echo "   Press Ctrl+C to stop"
echo ""

# Open browser in background (ignore failure)
(sleep 3; xdg-open http://localhost:8000 2>/dev/null || true) &

exec python3 -m uvicorn app:app --reload --host 127.0.0.1 --port 8000