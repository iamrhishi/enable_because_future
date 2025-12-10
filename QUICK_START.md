# 🚀 Quick Start: Deploy to GCP VM

## 📋 Pre-Deployment Checklist
- [ ] GCP VM created
- [ ] External IP noted down: `__________________`
- [ ] SSH access working
- [ ] Git repo accessible

---

## ⚡ Fast Track Deployment (Copy-Paste Commands)

### 1️⃣ SSH into Your VM
```bash
gcloud compute ssh YOUR_VM_NAME --zone=YOUR_ZONE
```

### 2️⃣ Create Firewall Rule (Allow Port 5000)
```bash
gcloud compute firewall-rules create allow-flask-5000 \
    --allow tcp:5000 \
    --source-ranges 0.0.0.0/0 \
    --description="Allow Flask app on port 5000"
```

### 3️⃣ Install Required Packages
```bash
sudo apt update && sudo apt upgrade -y
sudo apt install -y python3 python3-pip python3-venv git mysql-server
```

### 4️⃣ Clone Repository
```bash
cd ~
git clone https://github.com/YOUR_USERNAME/enable_because_future.git
cd enable_because_future/backend
```

### 5️⃣ Set Up Python Environment
```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 6️⃣ Configure Environment Variables
```bash
nano .env
```

**Paste this (replace with your values):**
```env
GEMINI_API_KEY=your_key_here
GOOGLE_API_KEY=your_key_here
GOOGLE_CSE_ID=your_cse_id_here
DB_HOST=localhost
DB_USER=root
DB_PASSWORD=your_mysql_password
DB_NAME=hello_db
MYSQL_HOST=localhost
MYSQL_USER=root
MYSQL_PASSWORD=your_mysql_password
MYSQL_DATABASE=hello_db
```

**Save:** `Ctrl+X` → `Y` → `Enter`

### 7️⃣ Set Up MySQL Database
```bash
sudo mysql -u root -p
```

**Run in MySQL:**
```sql
CREATE DATABASE hello_db CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE USER 'root'@'localhost' IDENTIFIED BY 'your_password';
GRANT ALL PRIVILEGES ON hello_db.* TO 'root'@'localhost';
FLUSH PRIVILEGES;
EXIT;
```

**Import schema:**
```bash
mysql -u root -p hello_db < ~/enable_because_future/backend/wardrobe_setup.sql
mysql -u root -p hello_db < ~/enable_because_future/backend/mysql_setup.sql
```

### 8️⃣ Create Systemd Service
```bash
sudo nano /etc/systemd/system/bcf-backend.service
```

**Paste this (replace YOUR_USERNAME with result of `whoami`):**
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

### 9️⃣ Start the Service
```bash
pip install gunicorn
sudo systemctl daemon-reload
sudo systemctl enable bcf-backend.service
sudo systemctl start bcf-backend.service
sudo systemctl status bcf-backend.service
```

### 🔟 Get Your External IP
```bash
curl ifconfig.me
```

**Note it down:** `__________________`

---

## 💻 Update Chrome Extension

### Edit `chrome-extension/popup.js` (Line 6)

**Change from:**
```javascript
const API_BASE_URL = 'http://localhost:5000';
```

**To (replace with YOUR actual IP):**
```javascript
// const API_BASE_URL = 'http://localhost:5000';
const API_BASE_URL = 'http://YOUR_VM_IP:5000';
```

### Reload Extension
1. Go to `chrome://extensions/`
2. Click reload button (🔄) on your extension
3. Test it!

---

## ✅ Test Your Deployment

```bash
# Test from your local machine
curl http://YOUR_VM_IP:5000/api/message

# Expected: JSON response with a message
```

---

## 🔄 Update Code (After Git Push)

```bash
# SSH into VM
cd ~/enable_because_future
git pull origin main
cd backend
source venv/bin/activate
pip install -r requirements.txt
sudo systemctl restart bcf-backend.service
```

---

## 📊 Useful Commands

```bash
# View logs (real-time)
sudo journalctl -u bcf-backend.service -f

# Check service status
sudo systemctl status bcf-backend.service

# Restart service
sudo systemctl restart bcf-backend.service

# Stop service
sudo systemctl stop bcf-backend.service

# Test database connection
mysql -u root -p hello_db -e "SHOW TABLES;"

# Check if port 5000 is listening
sudo netstat -tlnp | grep 5000
```

---

## 🐛 Quick Fixes

### Can't connect to VM?
```bash
# Check firewall
gcloud compute firewall-rules list | grep 5000

# Check if Flask is running
sudo systemctl status bcf-backend.service

# Check port
sudo netstat -tlnp | grep 5000
```

### Service won't start?
```bash
# View detailed logs
sudo journalctl -u bcf-backend.service -n 50

# Check .env file exists
cat ~/enable_because_future/backend/.env

# Test manually
cd ~/enable_because_future/backend
source venv/bin/activate
python3 app.py
```

### Database errors?
```bash
# Check MySQL is running
sudo systemctl status mysql

# Test connection
mysql -u root -p hello_db -e "SELECT 1;"

# Reset MySQL password if needed
sudo mysql
ALTER USER 'root'@'localhost' IDENTIFIED BY 'new_password';
FLUSH PRIVILEGES;
EXIT;
```

---

## 🎯 Mode Switching Cheat Sheet

### Development Mode (Local):
**`chrome-extension/popup.js` line 6:**
```javascript
const API_BASE_URL = 'http://localhost:5000';
// const API_BASE_URL = 'http://34.123.45.67:5000';
```

### Production Mode (GCP):
**`chrome-extension/popup.js` line 6:**
```javascript
// const API_BASE_URL = 'http://localhost:5000';
const API_BASE_URL = 'http://34.123.45.67:5000';
```

---

## 📚 Full Documentation

- **Complete Guide:** `GCP_DEPLOYMENT_GUIDE.md`
- **URL Changes:** `URL_CHANGES_SUMMARY.md`
- **This Cheat Sheet:** `QUICK_START.md`

---

## ✨ You're Done!

✅ Backend deployed on GCP VM
✅ Running as systemd service
✅ Firewall configured
✅ Extension connected to production

**Test everything and you're live! 🚀**
