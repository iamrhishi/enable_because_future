#!/bin/bash

################################################################################
# Flask Server Auto-Restart Script
# Keeps the Flask server running continuously on remote instances
# Automatically restarts if the server crashes or stops
################################################################################

set -e

# Configuration
APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APP_FILE="app.py"
PYTHON_VENV="$APP_DIR/venv"
LOG_FILE="$APP_DIR/flask_server.log"
PID_FILE="$APP_DIR/flask_server.pid"
MAX_RESTARTS=10
RESTART_DELAY=5

# Colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}================================${NC}"
echo -e "${GREEN}Flask Auto-Restart Monitor${NC}"
echo -e "${GREEN}================================${NC}"
echo "App Directory: $APP_DIR"
echo "Log File: $LOG_FILE"
echo "PID File: $PID_FILE"
echo ""

# Function to cleanup on exit
cleanup() {
    echo -e "\n${YELLOW}Received shutdown signal. Cleaning up...${NC}"
    if [ -f "$PID_FILE" ]; then
        PID=$(cat "$PID_FILE")
        if ps -p $PID > /dev/null 2>&1; then
            echo "Stopping Flask server (PID: $PID)..."
            kill $PID
            rm -f "$PID_FILE"
        fi
    fi
    echo -e "${GREEN}Cleanup complete. Exiting.${NC}"
    exit 0
}

# Trap signals for graceful shutdown
trap cleanup SIGINT SIGTERM

# Activate virtual environment
if [ -d "$PYTHON_VENV" ]; then
    echo -e "${GREEN}✓${NC} Activating virtual environment..."
    source "$PYTHON_VENV/bin/activate"
else
    echo -e "${RED}✗${NC} Virtual environment not found at $PYTHON_VENV"
    echo "Please create it first: python3 -m venv venv"
    exit 1
fi

# Check if app.py exists
if [ ! -f "$APP_DIR/$APP_FILE" ]; then
    echo -e "${RED}✗${NC} Flask app not found: $APP_DIR/$APP_FILE"
    exit 1
fi

# Change to app directory
cd "$APP_DIR"

# Main monitoring loop
restart_count=0
while true; do
    echo -e "\n${GREEN}================================${NC}"
    echo -e "${GREEN}Starting Flask Server (Attempt $((restart_count + 1)))${NC}"
    echo -e "${GREEN}================================${NC}"
    echo "Time: $(date)"
    
    # Start Flask server
    python "$APP_FILE" >> "$LOG_FILE" 2>&1 &
    FLASK_PID=$!
    
    # Save PID to file
    echo $FLASK_PID > "$PID_FILE"
    
    echo -e "${GREEN}✓${NC} Flask server started with PID: $FLASK_PID"
    echo -e "${GREEN}✓${NC} Logs: tail -f $LOG_FILE"
    
    # Monitor the process
    wait $FLASK_PID
    EXIT_CODE=$?
    
    # Remove PID file
    rm -f "$PID_FILE"
    
    # Check exit status
    if [ $EXIT_CODE -eq 0 ]; then
        echo -e "${YELLOW}⚠${NC} Flask server exited normally (exit code: $EXIT_CODE)"
    else
        echo -e "${RED}✗${NC} Flask server crashed (exit code: $EXIT_CODE)"
    fi
    
    # Increment restart counter
    restart_count=$((restart_count + 1))
    
    # Check if we've exceeded max restarts
    if [ $restart_count -ge $MAX_RESTARTS ]; then
        echo -e "${RED}✗${NC} Maximum restart attempts ($MAX_RESTARTS) reached."
        echo -e "${RED}✗${NC} Please check the logs: $LOG_FILE"
        exit 1
    fi
    
    # Wait before restarting
    echo -e "${YELLOW}⏳${NC} Waiting $RESTART_DELAY seconds before restart..."
    sleep $RESTART_DELAY
done
