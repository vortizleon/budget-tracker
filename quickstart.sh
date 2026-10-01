#!/bin/bash
# Quick start script for budgeting app

echo "🏦 Budgeting App - Quick Start"
echo "=============================="
echo ""

# Check if venv exists
if [ ! -d "venv" ]; then
    echo "Creating virtual environment with Python 3.13..."
    python3.13 -m venv venv
    echo "✓ Virtual environment created"
fi

# Activate venv
echo "Activating virtual environment..."
source venv/bin/activate

# Install dependencies
echo "Installing dependencies..."
pip install -q -r requirements.txt
echo "✓ Dependencies installed"

echo ""
echo "=============================="
echo "Setup complete! Next steps:"
echo "=============================="
echo ""
echo "1. Make sure credentials.json is in this directory"
echo "2. Run: python backend/init_db.py"
echo "   - Create default categories"
echo "   - Add your cards"
echo ""
echo "3. Run: python backend/sync.py"
echo "   - Sync transactions from Gmail"
echo ""
echo "=============================="
