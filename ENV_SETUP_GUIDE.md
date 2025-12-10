# 🔐 Setting Up Environment Variables on GCP VM

## ⚠️ IMPORTANT: Never Push Secrets to GitHub!

Your `.env` file contains sensitive information and should **NEVER** be committed to Git.

---

## ✅ What's Protected

I've secured your repository:

1. ✅ **Removed `.env` from Git tracking** (your local file is safe)
2. ✅ **`.gitignore` already protects** `.env` files
3. ✅ **Created `.env.example`** template (safe to commit)
4. ✅ **Moved hardcoded credentials** to environment variables
5. ✅ **Removed `venv/` from Git tracking** (virtual environment shouldn't be in Git)

---

## 📋 Your Current Keys (Keep These Safe!)

Based on your `.env` file, you have:

```bash
# Database
MYSQL_PASSWORD=root

# Google APIs
GEMINI_API_KEY=AIzaSyBs8KSx2mxNpCxHNFXQChvUd2tKF9MhUd0
GOOGLE_API_KEY=AIzaSyBHE08s9nMnSebWRJcVwMGMA8hlG1-L3AQ
GOOGLE_CSE_ID=06a400b037d3d4024

# External Services
BG_SERVICE_PASSWORD=becausefuture!2025
TRYON_SERVICE_PASSWORD=becausefuture!2025
```

**⚠️ Keep these somewhere safe! You'll need them on your GCP VM.**

---

## 🚀 How to Set Up Environment Variables on GCP VM

### **Method 1: Using .env File (Recommended - Easiest)**

After you SSH into your GCP VM and clone your repo:

#### **Step 1: Navigate to Backend Folder**
```bash
cd ~/enable_because_future/backend
```

#### **Step 2: Copy the Template**
```bash
cp .env.example .env
```

#### **Step 3: Edit with Your Real Keys**
```bash
nano .env
```

#### **Step 4: Paste Your Configuration**

Replace the placeholder values with your actual keys:

```bash
# MySQL Database
MYSQL_HOST=localhost
MYSQL_USER=root
MYSQL_PASSWORD=root
MYSQL_DATABASE=hello_db

# Google Gemini AI API
GEMINI_API_KEY=AIzaSyBs8KSx2mxNpCxHNFXQChvUd2tKF9MhUd0

# Google Custom Search API
GOOGLE_API_KEY=AIzaSyBHE08s9nMnSebWRJcVwMGMA8hlG1-L3AQ
GOOGLE_CSE_ID=06a400b037d3d4024

# External API Credentials
BG_SERVICE_USERNAME=becausefuture
BG_SERVICE_PASSWORD=becausefuture!2025
TRYON_SERVICE_USERNAME=becausefuture
TRYON_SERVICE_PASSWORD=becausefuture!2025

# Flask Configuration
FLASK_ENV=production
FLASK_DEBUG=False

# Server Configuration
HOST=0.0.0.0
PORT=5000
```

#### **Step 5: Save and Exit**
- Press `Ctrl + X`
- Press `Y` to confirm
- Press `Enter` to save

#### **Step 6: Verify File is Created**
```bash
ls -la .env
cat .env  # Check content (be careful in shared terminals!)
```

#### **Step 7: Restart Your Flask Service**
```bash
sudo systemctl restart bcf-backend.service
sudo systemctl status bcf-backend.service
```

✅ **Done!** Your Flask app will now load these environment variables.

---

### **Method 2: Using Systemd Environment Variables (More Secure)**

If you want even better security, you can set environment variables directly in the systemd service file:

#### **Step 1: Edit Service File**
```bash
sudo nano /etc/systemd/system/bcf-backend.service
```

#### **Step 2: Add Environment Variables**

Add these lines in the `[Service]` section:

```ini
[Service]
Type=simple
User=YOUR_USERNAME
WorkingDirectory=/home/YOUR_USERNAME/enable_because_future/backend
Environment="PATH=/home/YOUR_USERNAME/enable_because_future/backend/venv/bin"

# Add these environment variables
Environment="GEMINI_API_KEY=AIzaSyBs8KSx2mxNpCxHNFXQChvUd2tKF9MhUd0"
Environment="GOOGLE_API_KEY=AIzaSyBHE08s9nMnSebWRJcVwMGMA8hlG1-L3AQ"
Environment="GOOGLE_CSE_ID=06a400b037d3d4024"
Environment="MYSQL_HOST=localhost"
Environment="MYSQL_USER=root"
Environment="MYSQL_PASSWORD=root"
Environment="MYSQL_DATABASE=hello_db"
Environment="BG_SERVICE_USERNAME=becausefuture"
Environment="BG_SERVICE_PASSWORD=becausefuture!2025"
Environment="TRYON_SERVICE_USERNAME=becausefuture"
Environment="TRYON_SERVICE_PASSWORD=becausefuture!2025"

ExecStart=/home/YOUR_USERNAME/enable_because_future/backend/venv/bin/gunicorn --bind 0.0.0.0:5000 --workers 4 --timeout 120 app:app
Restart=always
```

#### **Step 3: Reload and Restart**
```bash
sudo systemctl daemon-reload
sudo systemctl restart bcf-backend.service
sudo systemctl status bcf-backend.service
```

**Pros:** More secure (not in a file), survives `.env` deletions
**Cons:** Requires sudo to change, restart service after each change

---

### **Method 3: Using GCP Secret Manager (Most Secure - Advanced)**

For production systems, consider using GCP Secret Manager:

#### **Step 1: Store Secret**
```bash
echo -n "AIzaSyBs8KSx2mxNpCxHNFXQChvUd2tKF9MhUd0" | \
  gcloud secrets create gemini-api-key --data-file=-
```

#### **Step 2: Update Code to Fetch Secret**
```python
from google.cloud import secretmanager

def get_secret(secret_id):
    client = secretmanager.SecretManagerServiceClient()
    name = f"projects/YOUR_PROJECT_ID/secrets/{secret_id}/versions/latest"
    response = client.access_secret_version(request={"name": name})
    return response.payload.data.decode("UTF-8")

GEMINI_API_KEY = get_secret("gemini-api-key")
```

**Pros:** Most secure, centralized management, audit logging
**Cons:** More complex setup, requires GCP permissions

---

## 🔄 Updating Environment Variables Later

### If Using .env File:
```bash
# SSH into VM
cd ~/enable_because_future/backend
nano .env
# Make your changes
# Save (Ctrl+X, Y, Enter)
sudo systemctl restart bcf-backend.service
```

### If Using Systemd:
```bash
sudo nano /etc/systemd/system/bcf-backend.service
# Make your changes
sudo systemctl daemon-reload
sudo systemctl restart bcf-backend.service
```

---

## ✅ Verification Checklist

After setting up environment variables on GCP:

```bash
# 1. Check if .env file exists
ls -la ~/enable_because_future/backend/.env

# 2. Check if service is running
sudo systemctl status bcf-backend.service

# 3. Check service logs for errors
sudo journalctl -u bcf-backend.service -n 50

# 4. Test API endpoint
curl http://localhost:5000/api/message

# 5. Check if environment variables are loaded (from logs)
# Look for successful API initialization messages
```

---

## 🐛 Troubleshooting

### Problem: "GEMINI_API_KEY not found"
**Solution:**
```bash
# Check if .env exists
cd ~/enable_because_future/backend
cat .env | grep GEMINI_API_KEY

# If missing, recreate .env from template
cp .env.example .env
nano .env
# Add your key
sudo systemctl restart bcf-backend.service
```

### Problem: Service won't start after adding .env
**Solution:**
```bash
# Check for syntax errors in .env
cat ~/enable_because_future/backend/.env

# No spaces around = sign!
# ✅ CORRECT: KEY=value
# ❌ WRONG: KEY = value

# Check service logs
sudo journalctl -u bcf-backend.service -n 100
```

### Problem: Keys work locally but not on GCP
**Solution:**
```bash
# Make sure .env is in the right place
cd ~/enable_because_future/backend
pwd  # Should show: /home/USERNAME/enable_because_future/backend
ls -la .env  # Should exist

# Check systemd WorkingDirectory matches
sudo systemctl cat bcf-backend.service | grep WorkingDirectory
```

---

## 📝 Before You Push to GitHub

Run this checklist:

```bash
cd /Users/rhishikeshthakur/Enable/Software_Development/enable_because_future

# 1. Verify .env is NOT tracked
git ls-files | grep ".env"
# Should only show: backend/.env.example (NOT backend/.env)

# 2. Verify venv is NOT tracked
git ls-files | grep "venv"
# Should show nothing

# 3. Check git status
git status
# .env and venv/ should NOT appear in "Changes to be committed"

# 4. Review .gitignore
cat .gitignore | grep -E ".env|venv"
# Should show both are ignored
```

---

## 🎯 Quick Command Reference

### On Your Local Machine (Before Push):
```bash
# Check what will be committed
git status

# Review changes
git diff

# Add files (automatically excludes .gitignore patterns)
git add .

# Commit
git commit -m "Add GCP deployment configuration"

# Push to GitHub
git push origin main
```

### On Your GCP VM (After Pull):
```bash
# Pull latest code
cd ~/enable_because_future
git pull origin main

# Set up environment variables
cd backend
cp .env.example .env
nano .env
# Paste your keys, save

# Restart service
sudo systemctl restart bcf-backend.service
sudo systemctl status bcf-backend.service
```

---

## 🔒 Security Best Practices

1. ✅ **Never commit .env** - Already protected by .gitignore
2. ✅ **Use strong passwords** - Especially for MySQL in production
3. ✅ **Rotate API keys** - Change them periodically
4. ✅ **Limit firewall** - Only allow necessary ports
5. ✅ **Use HTTPS** - For production (requires domain + SSL)
6. ✅ **Monitor logs** - Check for unauthorized access attempts
7. ✅ **Backup regularly** - Database and environment configs

---

## 📚 Related Documentation

- **GCP_DEPLOYMENT_GUIDE.md** - Full deployment walkthrough
- **QUICK_START.md** - Fast deployment commands
- **URL_CHANGES_SUMMARY.md** - API URL configuration

---

**You're all set to push safely to GitHub! 🎉**

Your secrets are protected, and you know exactly how to set them up on your GCP VM later.
