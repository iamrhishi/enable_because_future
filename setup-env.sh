#!/bin/bash
# Quick fix script for setting up .env file on GCP VM
# Run this on your GCP VM

echo "🔧 Setting up environment variables..."
echo ""

# Check if we're in the backend directory
if [ ! -f "app.py" ]; then
    echo "❌ Error: Not in backend directory!"
    echo "Please run: cd ~/enable_because_future/backend"
    exit 1
fi

# Check if .env.example exists
if [ ! -f ".env.example" ]; then
    echo "❌ Error: .env.example not found!"
    echo "Please pull latest code: git pull origin main"
    exit 1
fi

# Copy template
echo "📋 Copying .env.example to .env..."
cp .env.example .env

echo "✅ .env file created!"
echo ""
echo "📝 Now edit the .env file with your actual API keys:"
echo ""
echo "Run: nano .env"
echo ""
echo "Then add your keys:"
echo "  GEMINI_API_KEY=AIzaSyBs8KSx2mxNpCxHNFXQChvUd2tKF9MhUd0"
echo "  GOOGLE_API_KEY=AIzaSyBHE08s9nMnSebWRJcVwMGMA8hlG1-L3AQ"
echo "  GOOGLE_CSE_ID=06a400b037d3d4024"
echo "  MYSQL_PASSWORD=root"
echo "  BG_SERVICE_PASSWORD=becausefuture!2025"
echo "  TRYON_SERVICE_PASSWORD=becausefuture!2025"
echo ""
echo "Save with: Ctrl+X, then Y, then Enter"
echo ""
echo "After saving, restart the server:"
echo "  python app.py"
echo "  OR: sudo systemctl restart bcf-backend.service"
