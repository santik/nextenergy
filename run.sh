#!/bin/bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="$SCRIPT_DIR/.venv"

# Create virtual environment if it doesn't exist
if [ ! -d "$VENV_DIR" ]; then
    echo "Creating virtual environment in $VENV_DIR..."
    python3 -m venv "$VENV_DIR"
    
    # Activate and install dependencies
    source "$VENV_DIR/bin/activate"
    echo "Installing playwright..."
    pip install playwright
    echo "Installing browsers..."
    playwright install chromium
else
    source "$VENV_DIR/bin/activate"
fi

# Run the python script
echo "Running fetch_energy.py..."
python "$SCRIPT_DIR/fetch_energy.py"
