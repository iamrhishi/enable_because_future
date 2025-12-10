# 🚀 GCP VM Deployment Guide (Step-by-Step)

This guide will help you deploy your Flask backend on a GCP VM and connect your Chrome extension to it.

---

## 📋 Prerequisites

Before you start, make sure you have:
- ✅ A GCP VM created and running
- ✅ SSH access to your VM
- ✅ Your Git repository URL
- ✅ Your Gemini API key and other environment variables

---

## 🎯 Part 1: Switch Between Dev and Production Mode

### **Quick Switch Method**

In `chrome-extension/popup.js` (lines 1-14), you'll see:

```javascript
// ============================
// API Configuration
// ============================
// 🔧 DEVELOPMENT MODE: Uncomment the line below for local development
const API_BASE_URL = 'http://localhost:5000';

// 🚀 PRODUCTION MODE: Uncomment the line below when deploying to GCP
// Replace 'YOUR_VM_IP' with your actual GCP VM's external IP address
// const API_BASE_URL = 'http://YOUR_VM_IP:5000';
```

**To switch modes:**
1. **Local Development**: Keep first line uncommented
2. **Production**: Comment out localhost line, uncomment VM IP line, and replace `YOUR_VM_IP` with your actual external IP

**All 20+ API endpoints in your extension will automatically use the correct URL!**

---

## 🖥️ Part 2: Set Up Your GCP VM

### **Step 1: Get Your VM's External IP Address**

1. Go to GCP Console → Compute Engine → VM Instances
2. Find your VM and note the **External IP** (e.g., `34.123.45.67`)
3. Keep this handy - you'll need it!

### **Step 2: Configure Firewall Rules**

Your VM needs to allow incoming traffic on port 5000 (Flask default).

**Option A: Using GCP Console (Easier)**
1. Go to **VPC Network** → **Firewall**
2. Click **CREATE FIREWALL RULE**
3. Fill in:
   - **Name**: `allow-flask-5000`
   - **Direction**: Ingress
   - **Targets**: All instances in the network (or specified target tags)
   - **Source IP ranges**: `0.0.0.0/0` (allow from anywhere)
   - **Protocols and ports**: Check **tcp** and enter `5000`
4. Click **CREATE**

**Option B: Using gcloud command**
```bash
gcloud compute firewall-rules create allow-flask-5000 \
    --allow tcp:5000 \
    --source-ranges 0.0.0.0/0 \
    --description="Allow Flask app on port 5000"
```

### **Step 3: SSH into Your VM**

```bash
# From your local terminal (replace YOUR_VM_NAME and YOUR_PROJECT)
gcloud compute ssh YOUR_VM_NAME --zone=YOUR_ZONE --project=YOUR_PROJECT

# OR use the SSH button in GCP Console
```

---

## 🛠️ Part 3: Install Required Software on VM

Once SSH'd into your VM, run these commands:

### **Step 1: Update System Packages**
```bash
sudo apt update
sudo apt upgrade -y
```

### **Step 2: Install Python 3 and pip**
```bash
# Check if Python 3 is already installed
python3 --version

# If not installed:
sudo apt install python3 python3-pip python3-venv -y
```

### **Step 3: Install Git**
```bash
sudo apt install git -y
```

### **Step 4: Install MySQL (if not using Cloud SQL)**
```bash
sudo apt install mysql-server -y
sudo systemctl start mysql
sudo systemctl enable mysql

# Secure MySQL installation
sudo mysql_secure_installation
```

---

## 📦 Part 4: Clone and Set Up Your Repository

### **Step 1: Clone Your Repository**
```bash
cd ~
git clone https://github.com/YOUR_USERNAME/enable_because_future.git
cd enable_because_future/backend
```

### **Step 2: Create Python Virtual Environment**
```bash
# Create virtual environment
python3 -m venv venv

# Activate it
source venv/bin/activate

# You should see (venv) in your terminal prompt now
```

### **Step 3: Install Python Dependencies**
```bash
pip install -r requirements.txt
```

**If you don't have a `requirements.txt`, create one:**
```bash
cat > requirements.txt << EOF
Flask==3.0.0
flask-cors==4.0.0
mysql-connector-python==8.2.0
requests==2.31.0
beautifulsoup4==4.12.2
Werkzeug==3.0.1
python-dotenv==1.0.0
google-genai==0.2.2
Pillow==10.1.0
numpy==1.26.2
google-api-python-client==2.108.0
rembg==2.0.50
EOF

pip install -r requirements.txt
```

---

## 🔑 Part 5: Configure Environment Variables

### **Step 1: Create .env File**
```bash
cd ~/enable_because_future/backend

# Create .env file
nano .env
```

### **Step 2: Add Your Environment Variables**
Paste this and **replace with your actual values**:

```bash
# API Keys
GEMINI_API_KEY=your_actual_gemini_api_key_here
GOOGLE_API_KEY=your_google_api_key_here
GOOGLE_CSE_ID=your_custom_search_engine_id_here

# Database Configuration
DB_HOST=localhost
DB_USER=root
DB_PASSWORD=your_mysql_password_here
DB_NAME=hello_db

# MySQL Config (used by app.py directly)
MYSQL_HOST=localhost
MYSQL_USER=root
MYSQL_PASSWORD=your_mysql_password_here
MYSQL_DATABASE=hello_db
```

**Save and exit**: Press `Ctrl+X`, then `Y`, then `Enter`

### **Step 3: Make Sure .env is in .gitignore**
```bash
# Check if .env is ignored
cat .gitignore | grep .env

# If not, add it:
echo ".env" >> .gitignore
```

---

## 🗄️ Part 6: Set Up MySQL Database

### **Step 1: Log into MySQL**
```bash
sudo mysql -u root -p
# Enter your MySQL password when prompted
```

### **Step 2: Create Database and User**
```sql
-- Create database
CREATE DATABASE hello_db CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

-- Create user (replace 'your_password' with a strong password)
CREATE USER 'root'@'localhost' IDENTIFIED BY 'your_password';

-- Grant privileges
GRANT ALL PRIVILEGES ON hello_db.* TO 'root'@'localhost';
FLUSH PRIVILEGES;

-- Exit MySQL
EXIT;
```

### **Step 3: Import Database Schema**

If you have SQL setup files:
```bash
# For wardrobe setup
mysql -u root -p hello_db < ~/enable_because_future/backend/wardrobe_setup.sql

# For MySQL setup
mysql -u root -p hello_db < ~/enable_because_future/backend/mysql_setup.sql
```

**Or create tables manually:**
```bash
sudo mysql -u root -p hello_db
```

Then paste your table creation SQL (users table, wardrobe table, etc.)

---

## 🚀 Part 7: Run Your Flask Application

### **Method 1: Direct Run (for testing)**
```bash
cd ~/enable_because_future/backend
source venv/bin/activate
python3 app.py
```

You should see:
```
 * Running on http://0.0.0.0:5000
```

**Test it:**
```bash
# In a new SSH session or from your local machine:
curl http://YOUR_VM_EXTERNAL_IP:5000/api/message
```

### **Method 2: Using Gunicorn (Production - Recommended)**

**Install Gunicorn:**
```bash
pip install gunicorn
```

**Run with Gunicorn:**
```bash
gunicorn --bind 0.0.0.0:5000 --workers 4 --timeout 120 app:app
```

### **Method 3: Run as Background Service (Best for Production)**

Create a systemd service:

```bash
sudo nano /etc/systemd/system/bcf-backend.service
```

Paste this configuration:
```ini
[Unit]
Description=Because Future Backend Flask App
After=network.target mysql.service

[Service]
Type=simple
User=YOUR_USERNAME
WorkingDirectory=/home/YOUR_USERNAME/enable_because_future/backend
Environment="PATH=/home/YOUR_USERNAME/enable_because_future/backend/venv/bin"
ExecStart=/home/YOUR_USERNAME/enable_because_future/backend/venv/bin/gunicorn --bind 0.0.0.0:5000 --workers 4 --timeout 120 app:app
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

**Replace `YOUR_USERNAME` with your actual VM username** (run `whoami` to check)

**Enable and start the service:**
```bash
sudo systemctl daemon-reload
sudo systemctl enable bcf-backend.service
sudo systemctl start bcf-backend.service

# Check status
sudo systemctl status bcf-backend.service
```

**Useful commands:**
```bash
# Stop the service
sudo systemctl stop bcf-backend.service

# Restart the service
sudo systemctl restart bcf-backend.service

# View logs
sudo journalctl -u bcf-backend.service -f
```

---

## 🔄 Part 8: Update Chrome Extension Configuration

### **Step 1: Get Your VM External IP**
```bash
curl ifconfig.me
# OR check GCP Console
```

### **Step 2: Update popup.js**

Edit `chrome-extension/popup.js` (line 6):

**Before:**
```javascript
const API_BASE_URL = 'http://localhost:5000';
```

**After (for production):**
```javascript
// const API_BASE_URL = 'http://localhost:5000';  // Commented out for production
const API_BASE_URL = 'http://34.123.45.67:5000';  // Replace with YOUR external IP
```

### **Step 3: Reload Your Chrome Extension**

1. Open Chrome → `chrome://extensions/`
2. Find your extension
3. Click the **Reload** button (🔄)
4. Test the extension!

---

## ✅ Part 9: Testing Your Deployment

### **Test 1: Basic API Connection**
```bash
curl http://YOUR_VM_IP:5000/api/message
```

Expected response: Some message from database

### **Test 2: Background Removal API**
Use your Chrome extension to test background removal

### **Test 3: Try-On API**
Use your Chrome extension to test virtual try-on

### **Test 4: User Login**
Try logging in through the extension

---

## 🐛 Part 10: Troubleshooting

### **Problem: Cannot connect to VM**
**Solution:**
1. Check firewall rules allow port 5000
2. Verify Flask is running: `sudo systemctl status bcf-backend.service`
3. Check if port is listening: `sudo netstat -tlnp | grep 5000`

### **Problem: CORS errors in browser**
**Solution:**
Your `app.py` already has CORS enabled (`CORS(app)` on line 30).
If issues persist, update CORS configuration:

```python
from flask_cors import CORS

CORS(app, resources={
    r"/api/*": {
        "origins": "*",  # Allow all origins (use specific domain in production)
        "methods": ["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        "allow_headers": ["Content-Type"]
    }
})
```

### **Problem: Database connection errors**
**Solution:**
1. Check MySQL is running: `sudo systemctl status mysql`
2. Verify credentials in `.env` file
3. Test MySQL connection:
   ```bash
   mysql -u root -p hello_db -e "SELECT 1;"
   ```

### **Problem: Gemini API errors**
**Solution:**
1. Verify API key is correct in `.env`
2. Check API quota: https://console.cloud.google.com/apis/dashboard
3. View Flask logs: `sudo journalctl -u bcf-backend.service -n 100`

### **Problem: Extension shows old localhost errors**
**Solution:**
1. Make sure you updated `API_BASE_URL` in `popup.js`
2. Reload the extension in Chrome
3. Clear browser cache
4. Check browser console for errors (F12)

---

## 🔄 Part 11: Updating Your Code

When you push code changes to GitHub and want to update on your VM:

```bash
# SSH into VM
gcloud compute ssh YOUR_VM_NAME

# Navigate to repo
cd ~/enable_because_future

# Pull latest changes
git pull origin main

# If backend changed, restart service
cd backend
source venv/bin/activate
pip install -r requirements.txt  # Install any new dependencies
sudo systemctl restart bcf-backend.service

# Check if it's running
sudo systemctl status bcf-backend.service
```

---

## 🔐 Part 12: Security Improvements (Recommended)

### **1. Use HTTPS Instead of HTTP**

For production, you should use HTTPS. Options:
- Use a domain name + SSL certificate (Let's Encrypt)
- Use GCP Load Balancer with SSL
- Use Cloudflare for SSL termination

### **2. Restrict Firewall Rules**

Instead of `0.0.0.0/0`, limit to specific IP ranges:
```bash
gcloud compute firewall-rules update allow-flask-5000 \
    --source-ranges=YOUR_OFFICE_IP/32,YOUR_HOME_IP/32
```

### **3. Use Cloud SQL Instead of Local MySQL**

Benefits: Automatic backups, high availability, managed service

### **4. Use Environment-Specific Configs**

Keep separate configs for dev/staging/production

---

## 📊 Part 13: Monitoring and Logs

### **View Flask Application Logs**
```bash
# Real-time logs
sudo journalctl -u bcf-backend.service -f

# Last 100 lines
sudo journalctl -u bcf-backend.service -n 100

# Logs from today
sudo journalctl -u bcf-backend.service --since today
```

### **View MySQL Logs**
```bash
sudo tail -f /var/log/mysql/error.log
```

### **Check Resource Usage**
```bash
# CPU and memory
top

# Disk space
df -h

# Service status
sudo systemctl status bcf-backend.service
```

---

## 🎉 Summary Checklist

Before going live:
- ✅ VM created with external IP
- ✅ Firewall allows port 5000
- ✅ Code cloned from Git
- ✅ Python dependencies installed
- ✅ .env file configured with API keys
- ✅ MySQL database created and populated
- ✅ Flask app running as systemd service
- ✅ Chrome extension updated with VM IP
- ✅ All APIs tested (login, try-on, background removal)
- ✅ Monitoring and logs working

---

## 🆘 Need Help?

If you encounter issues:
1. Check logs: `sudo journalctl -u bcf-backend.service -f`
2. Test API manually: `curl http://YOUR_VM_IP:5000/api/message`
3. Verify environment variables: `cat ~/enable_because_future/backend/.env`
4. Check Flask is listening: `sudo netstat -tlnp | grep 5000`

---

## 🚀 Quick Reference Commands

```bash
# Start service
sudo systemctl start bcf-backend.service

# Stop service
sudo systemctl stop bcf-backend.service

# Restart service
sudo systemctl restart bcf-backend.service

# View logs
sudo journalctl -u bcf-backend.service -f

# Pull latest code
cd ~/enable_because_future && git pull

# Activate virtual environment
source ~/enable_because_future/backend/venv/bin/activate

# Test database
mysql -u root -p hello_db -e "SHOW TABLES;"
```

---

**You're all set! 🎊** Your backend is now running on GCP and your Chrome extension can connect to it from anywhere!
