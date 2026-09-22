#!/usr/bin/env bash
# ==============================================================================
# BorsTerminal Cloud Bootstrap & Agent Runner for Freestyle.sh / Linux VMs
# ==============================================================================
set -e

echo "[1/5] Updating system packages and installing prerequisites..."
sudo apt-get update -y
sudo apt-get install -y python3 python3-pip python3-venv git curl tmux htop

echo "[2/5] Setting up Node.js 22 LTS (for Agent CLIs)..."
if ! command -v node &> /dev/null; then
    curl -fsSL https://deb.nodesource.com/setup_22.x | sudo -E bash -
    sudo apt-get install -y nodejs
fi
echo "Node version: $(node -v)"

echo "[3/5] Cloning / Updating BorsTerminal repository..."
WORKSPACE="$HOME/BorsTerminal"
if [ ! -d "$WORKSPACE" ]; then
    git clone https://github.com/johnwarchief/BorsTerminal-src.git "$WORKSPACE"
else
    cd "$WORKSPACE" && git pull origin main
fi
cd "$WORKSPACE"

echo "[4/5] Setting up Python virtual environment and dependencies..."
if [ ! -d "venv" ]; then
    python3 -m venv venv
fi
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
pip install python-telegram-bot

echo "[5/5] Extracting market database baseline..."
if [ ! -f "market.db" ] && [ -f "market.db.lzma" ]; then
    python3 -c "import lzma, shutil; shutil.copyfileobj(lzma.open('market.db.lzma'), open('market.db', 'wb'))"
    echo "market.db extracted successfully!"
fi

echo "=============================================================================="
echo "BorsTerminal Cloud Environment Ready!"
echo "Working directory: $WORKSPACE"
echo "To activate environment: cd $WORKSPACE && source venv/bin/activate"
echo "=============================================================================="
