#!/bin/bash

# ============================================
# Pre-Push Security Check
# ============================================
# Run this script before pushing to GitHub
# to ensure no secrets are being committed

echo "🔍 Checking for sensitive files..."
echo ""

# Check if .env is in staging area
if git diff --cached --name-only | grep -q "\.env$"; then
    echo "❌ ERROR: .env file found in staging area!"
    echo "   Run: git restore --staged backend/.env"
    exit 1
else
    echo "✅ .env files are not staged"
fi

# Check if venv is in staging area
if git diff --cached --name-only | grep -q "venv/"; then
    echo "⚠️  WARNING: venv files found in staging area"
    echo "   These will be removed from Git"
fi

# Check for API keys in staged files
echo ""
echo "🔍 Scanning for potential API keys in staged files..."

# Check for Google API key patterns
if git diff --cached | grep -iE "AIza[0-9A-Za-z_-]{35}"; then
    echo "❌ ERROR: Potential Google API key found in staged changes!"
    echo "   Please remove hardcoded API keys"
    exit 1
else
    echo "✅ No Google API keys found in staged changes"
fi

# Check for potential passwords (basic check)
if git diff --cached | grep -iE "password.*=.*['\"][^'\"]{8,}['\"]"; then
    echo "⚠️  WARNING: Potential password found in staged changes"
    echo "   Please review your changes carefully"
fi

echo ""
echo "✅ Security check passed!"
echo ""
echo "📋 Files to be committed:"
git diff --cached --name-only
echo ""
echo "Ready to commit and push! 🚀"
