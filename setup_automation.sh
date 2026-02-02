#!/bin/bash
set -e

PROJECT_DIR="/Users/alexander/.gemini/antigravity/scratch"
VENV_DIR="$PROJECT_DIR/.venv"

echo "Setting up environment in $PROJECT_DIR"

if [ ! -d "$VENV_DIR" ]; then
    echo "Creating virtual environment..."
    python3 -m venv "$VENV_DIR"
else
    echo "Virtual environment already exists."
fi

source "$VENV_DIR/bin/activate"

echo "Installing Playwright..."
pip install playwright

echo "Installing Browsers..."
python -m playwright install chromium

echo "Making script executable..."
chmod +x "$PROJECT_DIR/fetch_energy.py"

echo "Setup complete."
