#!/bin/bash

################################################################################
# Quick Server Start Script
# Simple wrapper to start Flask with auto-restart in a screen session
################################################################################

set -e

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m'

APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SESSION_NAME="flask-server"

echo -e "${BLUE}================================${NC}"
echo -e "${BLUE}Flask Quick Start${NC}"
echo -e "${BLUE}================================${NC}"

# Check if screen is installed
if ! command -v screen &> /dev/null; then
    echo -e "${YELLOW}⚠${NC} 'screen' not installed. Installing..."
    sudo apt-get update && sudo apt-get install -y screen
fi

# Check if session already exists
if screen -list | grep -q "$SESSION_NAME"; then
    echo -e "${YELLOW}⚠${NC} Flask server is already running in screen session '$SESSION_NAME'"
    echo ""
    echo "Options:"
    echo "  1. View logs: tail -f $APP_DIR/flask_server.log"
    echo "  2. Attach to session: screen -r $SESSION_NAME"
    echo "  3. Stop server: screen -X -S $SESSION_NAME quit"
    echo "  4. Check status: curl http://localhost:5000/api/message"
    exit 0
fi

# Start new screen session
echo -e "${GREEN}✓${NC} Starting Flask server in screen session '$SESSION_NAME'..."
cd "$APP_DIR"

screen -dmS "$SESSION_NAME" bash -c "
    source venv/bin/activate
    ./keep-server-running.sh
"

sleep 2

echo -e "${GREEN}✓${NC} Flask server started!"
echo ""
echo "Useful commands:"
echo -e "  ${BLUE}View logs:${NC}      tail -f $APP_DIR/flask_server.log"
echo -e "  ${BLUE}Attach to screen:${NC} screen -r $SESSION_NAME"
echo -e "  ${BLUE}Detach:${NC}          Press Ctrl+A then D"
echo -e "  ${BLUE}Stop server:${NC}     screen -X -S $SESSION_NAME quit"
echo -e "  ${BLUE}Test API:${NC}        curl http://localhost:5000/api/message"
echo ""
echo -e "${GREEN}Server is running in the background with auto-restart!${NC}"
