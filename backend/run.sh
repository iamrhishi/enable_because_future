#!/bin/bash
# run.sh - Start backend server normally

PORT=8000
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "=== BecauseFuture Backend ==="

# Kill existing processes on port
echo "Checking for existing processes on port $PORT..."
PID=$(lsof -ti :$PORT 2>/dev/null)
if [ -n "$PID" ]; then
    echo "Killing existing process(es) on port $PORT: $PID"
    kill -9 $PID 2>/dev/null
    sleep 1
fi

# Activate virtual environment and start server
echo "Starting Flask server on port $PORT..."
cd "$SCRIPT_DIR"

if [ -d "./venv" ]; then
    source ./venv/bin/activate
elif [ -d "../venv" ]; then
    source ../venv/bin/activate
fi

echo ""
echo "========================================"
echo "Server starting on http://localhost:$PORT"
echo "API Base: http://localhost:$PORT/api"
echo "Press Ctrl+C to stop"
echo "========================================"
echo ""

# Run server in foreground
python app.py
