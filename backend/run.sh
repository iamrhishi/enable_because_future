#!/bin/bash
# run.sh - Start backend server using nohup

PORT=5001
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "=== BecauseFuture Backend ==="

# Kill existing processes on port 5001
echo "Checking for existing processes on port $PORT..."
PID=$(lsof -ti :$PORT 2>/dev/null)
if [ -n "$PID" ]; then
    echo "Killing existing process(es) on port $PORT: $PID"
    kill -9 $PID 2>/dev/null
    sleep 1
fi

cd "$SCRIPT_DIR"

# Activate virtual environment
if [ -d "./venv" ]; then
    source ./venv/bin/activate
elif [ -d "../venv" ]; then
    source ../venv/bin/activate
fi

# Install/update dependencies
echo "Updating dependencies..."
pip install -q -r requirements.txt 2>/dev/null || pip3 install -q -r requirements.txt

# Run pending migrations
echo "Running migrations..."
python scripts/run_migrations.py 2>/dev/null || python3 scripts/run_migrations.py 2>/dev/null

echo "Starting Flask server on port $PORT..."
PORT=$PORT nohup python app.py > app.log 2>&1 &
SERVER_PID=$!

echo ""
echo "========================================"
echo "Server started with PID: $SERVER_PID"
echo "Port:    $PORT"
echo "Logs:    tail -f $SCRIPT_DIR/app.log"
echo "========================================"
