#!/bin/bash

################################################################################
# Install Flask Backend as Systemd Service
# This script sets up the Flask server to run automatically on boot
# and restart automatically if it crashes
################################################################################

set -e

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}================================${NC}"
echo -e "${BLUE}Flask Backend Service Installer${NC}"
echo -e "${BLUE}================================${NC}"
echo ""

# Check if running as root
if [ "$EUID" -ne 0 ]; then 
    echo -e "${RED}✗${NC} This script must be run as root (use sudo)"
    exit 1
fi

# Get the actual user (not root)
ACTUAL_USER="${SUDO_USER:-$USER}"
echo -e "${GREEN}✓${NC} Running as root"
echo -e "${GREEN}✓${NC} Service will run as user: $ACTUAL_USER"

# Get script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
echo -e "${GREEN}✓${NC} Backend directory: $SCRIPT_DIR"

# Get home directory
USER_HOME=$(eval echo ~$ACTUAL_USER)
echo -e "${GREEN}✓${NC} User home: $USER_HOME"

# Create the service file with correct paths
SERVICE_FILE="/etc/systemd/system/bcf-backend.service"
echo ""
echo -e "${YELLOW}Creating systemd service file...${NC}"

cat > "$SERVICE_FILE" << EOF
[Unit]
Description=Enable Because Future - Flask Backend Server
After=network.target mysql.service
Wants=mysql.service

[Service]
Type=simple
User=$ACTUAL_USER
Group=$ACTUAL_USER
WorkingDirectory=$SCRIPT_DIR
Environment="PATH=$SCRIPT_DIR/venv/bin:/usr/local/bin:/usr/bin:/bin"

# Load environment variables from .env file
EnvironmentFile=$SCRIPT_DIR/.env

# Start command using virtual environment Python
ExecStart=$SCRIPT_DIR/venv/bin/python $SCRIPT_DIR/app.py

# Restart policy
Restart=always
RestartSec=10

# Resource limits
LimitNOFILE=65536
TimeoutStopSec=30

# Logging
StandardOutput=append:$SCRIPT_DIR/flask_server.log
StandardError=append:$SCRIPT_DIR/flask_server.log

[Install]
WantedBy=multi-user.target
EOF

echo -e "${GREEN}✓${NC} Service file created: $SERVICE_FILE"

# Check if .env file exists
if [ ! -f "$SCRIPT_DIR/.env" ]; then
    echo -e "${YELLOW}⚠${NC} Warning: .env file not found at $SCRIPT_DIR/.env"
    echo "   The service needs this file for environment variables."
    echo "   Please create it before starting the service."
fi

# Check if virtual environment exists
if [ ! -d "$SCRIPT_DIR/venv" ]; then
    echo -e "${YELLOW}⚠${NC} Warning: Virtual environment not found at $SCRIPT_DIR/venv"
    echo "   Please create it: python3 -m venv venv"
fi

# Reload systemd
echo ""
echo -e "${YELLOW}Reloading systemd daemon...${NC}"
systemctl daemon-reload
echo -e "${GREEN}✓${NC} Systemd reloaded"

# Enable the service
echo ""
echo -e "${YELLOW}Enabling service to start on boot...${NC}"
systemctl enable bcf-backend.service
echo -e "${GREEN}✓${NC} Service enabled"

echo ""
echo -e "${GREEN}================================${NC}"
echo -e "${GREEN}Installation Complete!${NC}"
echo -e "${GREEN}================================${NC}"
echo ""
echo "Service Management Commands:"
echo ""
echo -e "  ${BLUE}Start service:${NC}"
echo "    sudo systemctl start bcf-backend"
echo ""
echo -e "  ${BLUE}Stop service:${NC}"
echo "    sudo systemctl stop bcf-backend"
echo ""
echo -e "  ${BLUE}Restart service:${NC}"
echo "    sudo systemctl restart bcf-backend"
echo ""
echo -e "  ${BLUE}Check status:${NC}"
echo "    sudo systemctl status bcf-backend"
echo ""
echo -e "  ${BLUE}View logs:${NC}"
echo "    sudo journalctl -u bcf-backend -f"
echo "    tail -f $SCRIPT_DIR/flask_server.log"
echo ""
echo -e "  ${BLUE}Disable auto-start:${NC}"
echo "    sudo systemctl disable bcf-backend"
echo ""
echo -e "${YELLOW}To start the service now, run:${NC}"
echo "  sudo systemctl start bcf-backend"
echo ""
