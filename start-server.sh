#!/bin/bash
# ComfyUI Indexer - Start Web Server
# Activates the virtual environment and launches the web UI

echo "Starting ComfyUI Indexer..."
echo

# Check if venv exists
if [ ! -f "venv/bin/activate" ]; then
    echo "ERROR: Virtual environment not found!"
    echo "Please run ./install-comfy-idx.sh first."
    exit 1
fi

# Activate venv
source venv/bin/activate

# Start the server
echo
echo "========================================"
echo "ComfyUI Indexer Web Server"
echo "========================================"
echo
echo "Server starting at: http://localhost:8000"
echo "Press Ctrl+C to stop the server"
echo

comfy-idx serve --host 0.0.0.0 --port 8000
