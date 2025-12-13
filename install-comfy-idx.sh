#!/bin/bash
# ComfyUI Indexer - Linux/macOS Installation Script
# This script creates a virtual environment and installs the package

echo "========================================"
echo "ComfyUI Indexer - Installation"
echo "========================================"
echo

# Check if Python is available
if ! command -v python3 &> /dev/null; then
    echo "ERROR: Python3 is not installed"
    echo "Please install Python 3.10 or later using your package manager"
    exit 1
fi

# Check Python version
PYVER=$(python3 --version 2>&1 | cut -d' ' -f2)
echo "Found Python $PYVER"
echo

# Check if venv exists
if [ -d "venv" ]; then
    echo "Virtual environment already exists."
    echo "Skipping venv creation..."
else
    echo "Creating virtual environment..."
    python3 -m venv venv
    if [ $? -ne 0 ]; then
        echo "ERROR: Failed to create virtual environment"
        exit 1
    fi
    echo "Virtual environment created successfully."
fi
echo

# Activate venv and install
echo "Installing ComfyUI Indexer..."
source venv/bin/activate

# Upgrade pip first
python -m pip install --upgrade pip > /dev/null 2>&1

# Install the package
pip install -e .
if [ $? -ne 0 ]; then
    echo "ERROR: Installation failed"
    exit 1
fi

echo
echo "========================================"
echo "Installation Complete!"
echo "========================================"
echo
echo "To use ComfyUI Indexer:"
echo "  1. Run ./start-server.sh to launch the web UI"
echo "  2. Or activate the venv and use the CLI:"
echo "     source venv/bin/activate"
echo "     comfy-idx --help"
echo
