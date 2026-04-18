#!/bin/bash
# run_local.sh - Start backend with ngrok tunnel for local development

PORT=8000
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "=== BecauseFuture Backend - Local Development ==="

# Kill existing processes on port
echo "Checking for existing processes on port $PORT..."
PID=$(lsof -ti :$PORT 2>/dev/null)
if [ -n "$PID" ]; then
    echo "Killing existing process(es) on port $PORT: $PID"
    kill -9 $PID 2>/dev/null
    sleep 1
fi

# Kill existing ngrok
echo "Stopping existing ngrok tunnels..."
pkill -f ngrok 2>/dev/null
sleep 1

# Activate virtual environment and start server
echo "Starting Flask server on port $PORT..."
cd "$SCRIPT_DIR"

if [ -d "./venv" ]; then
    source ./venv/bin/activate
elif [ -d "../venv" ]; then
    source ../venv/bin/activate
fi

# Start server in background
python app.py > /tmp/backend.log 2>&1 &
SERVER_PID=$!
echo "Server started with PID: $SERVER_PID"

# Wait for server to be ready
echo "Waiting for server to start..."
for i in {1..10}; do
    if curl -s http://localhost:$PORT/api/health > /dev/null 2>&1; then
        echo "Server is ready!"
        break
    fi
    sleep 1
done

# Start ngrok
echo "Starting ngrok tunnel..."
ngrok http $PORT --log=stdout > /tmp/ngrok.log 2>&1 &
NGROK_PID=$!
sleep 3

# Get ngrok URL
NGROK_URL=$(curl -s http://localhost:4040/api/tunnels 2>/dev/null | python3 -c "import sys,json; d=json.load(sys.stdin); print(d['tunnels'][0]['public_url'])" 2>/dev/null)

if [ -n "$NGROK_URL" ]; then
    echo ""
    echo "========================================"
    echo "Server running successfully!"
    echo "========================================"
    echo ""
    echo "Local:  http://localhost:$PORT"
    echo "Public: $NGROK_URL"
    echo ""
    echo "API Base: $NGROK_URL/api"
    echo ""
    echo "Logs:"
    echo "  Server: tail -f /tmp/backend.log"
    echo "  Ngrok:  tail -f /tmp/ngrok.log"
    echo ""
    echo "To stop: kill $SERVER_PID $NGROK_PID"
    echo "========================================"
else
    echo "ERROR: Failed to get ngrok URL"
    echo "Check /tmp/ngrok.log for details"
    exit 1
fi
