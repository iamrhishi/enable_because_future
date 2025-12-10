# Flask Server Auto-Restart Scripts

This directory contains multiple solutions to keep your Flask server running continuously on remote instances without shutting down.

## 📋 Available Solutions

### 1. **Systemd Service (Recommended for Production) ⭐**

The most robust solution - runs as a system service with automatic restart on failure and boot.

**Features:**
- ✅ Starts automatically on server boot
- ✅ Restarts automatically on crashes
- ✅ Runs in background as daemon
- ✅ Integrated with system logging
- ✅ Easy management with `systemctl` commands

**Installation:**

```bash
# On your GCP VM, run:
cd ~/enable_because_future/backend
chmod +x install-service.sh
sudo ./install-service.sh
```

**Usage:**

```bash
# Start the service
sudo systemctl start bcf-backend

# Stop the service
sudo systemctl stop bcf-backend

# Restart the service
sudo systemctl restart bcf-backend

# Check status
sudo systemctl status bcf-backend

# View logs
sudo journalctl -u bcf-backend -f
# OR
tail -f ~/enable_because_future/backend/flask_server.log

# Enable auto-start on boot (already done by installer)
sudo systemctl enable bcf-backend

# Disable auto-start on boot
sudo systemctl disable bcf-backend
```

---

### 2. **Bash Monitor Script (Simple & Effective)**

A shell script that monitors Flask and restarts it if it crashes.

**Features:**
- ✅ Simple to understand
- ✅ Automatic restart on crash (up to 10 times)
- ✅ Logs all activity
- ✅ Graceful shutdown handling

**Usage:**

```bash
cd ~/enable_because_future/backend

# Make executable
chmod +x keep-server-running.sh

# Run in foreground
./keep-server-running.sh

# Run in background
nohup ./keep-server-running.sh &

# Or with screen (recommended)
screen -S flask
./keep-server-running.sh
# Press Ctrl+A then D to detach
# Reattach with: screen -r flask
```

---

### 3. **Python Monitor Script (Advanced)**

A Python-based monitor with health checks and better error handling.

**Features:**
- ✅ HTTP health checks every 30 seconds
- ✅ Automatic restart on crash or unresponsiveness
- ✅ Better error logging
- ✅ Resets restart counter on successful health check

**Usage:**

```bash
cd ~/enable_because_future/backend

# Make executable
chmod +x keep-server-running.py

# Activate virtual environment first
source venv/bin/activate

# Run in foreground
python keep-server-running.py

# Run in background
nohup python keep-server-running.py &

# Or with screen
screen -S flask
python keep-server-running.py
# Press Ctrl+A then D to detach
```

---

## 🚀 Quick Start (GCP VM)

### Option A: Systemd Service (Recommended)

```bash
# SSH to your GCP VM
ssh your-vm-name

# Navigate to backend
cd ~/enable_because_future/backend

# Install as system service
chmod +x install-service.sh
sudo ./install-service.sh

# Start the service
sudo systemctl start bcf-backend

# Check it's running
sudo systemctl status bcf-backend

# Test the API
curl http://localhost:5000/api/message
```

### Option B: Screen Session (Quick & Simple)

```bash
# SSH to your GCP VM
ssh your-vm-name

# Navigate to backend
cd ~/enable_because_future/backend

# Start a screen session
screen -S flask

# Activate venv
source venv/bin/activate

# Run the monitor script
chmod +x keep-server-running.sh
./keep-server-running.sh

# Detach from screen: Press Ctrl+A then D
# Reattach later: screen -r flask
# Kill session: screen -X -S flask quit
```

---

## 📊 Comparison Table

| Feature | Systemd Service | Bash Script | Python Script |
|---------|----------------|-------------|---------------|
| Auto-start on boot | ✅ | ❌ | ❌ |
| Auto-restart on crash | ✅ | ✅ | ✅ |
| Health checks | ❌ | ❌ | ✅ |
| System integration | ✅ | ❌ | ❌ |
| Easy to setup | ⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ |
| Resource usage | Low | Low | Medium |
| Logging | Systemd + File | File only | File only |
| Complexity | Medium | Low | Medium |

---

## 🔍 Monitoring & Logs

### Check if server is running:

```bash
# Using systemctl (if using systemd)
sudo systemctl status bcf-backend

# Using ps
ps aux | grep python

# Using curl
curl http://localhost:5000/api/message
```

### View logs:

```bash
# Application logs
tail -f ~/enable_because_future/backend/flask_server.log

# Systemd logs (if using systemd)
sudo journalctl -u bcf-backend -f

# Last 100 lines
tail -n 100 ~/enable_because_future/backend/flask_server.log
```

---

## 🛠️ Troubleshooting

### Server won't start:

1. **Check .env file exists:**
   ```bash
   ls -la ~/enable_because_future/backend/.env
   ```

2. **Check virtual environment:**
   ```bash
   ls -la ~/enable_because_future/backend/venv
   ```

3. **Check permissions:**
   ```bash
   chmod +x keep-server-running.sh
   chmod +x keep-server-running.py
   ```

4. **Check logs:**
   ```bash
   tail -n 50 ~/enable_because_future/backend/flask_server.log
   ```

### Server keeps crashing:

1. **Check error logs:**
   ```bash
   tail -f ~/enable_because_future/backend/flask_server.log
   ```

2. **Check MySQL is running:**
   ```bash
   sudo systemctl status mysql
   ```

3. **Test manually:**
   ```bash
   cd ~/enable_because_future/backend
   source venv/bin/activate
   python app.py
   ```

### Systemd service won't start:

1. **Check service file syntax:**
   ```bash
   sudo systemd-analyze verify bcf-backend.service
   ```

2. **Check service status:**
   ```bash
   sudo systemctl status bcf-backend
   ```

3. **View detailed logs:**
   ```bash
   sudo journalctl -u bcf-backend -n 50 --no-pager
   ```

---

## 🎯 Best Practices

1. **For Production:** Use **systemd service** - it's the most reliable
2. **For Testing:** Use **bash script** with `screen` - quick and easy
3. **For Development:** Use **python script** with health checks
4. **Always monitor logs** to catch issues early
5. **Set up firewall rules** for port 5000
6. **Use .env file** for sensitive configuration
7. **Backup your .env file** regularly

---

## 📝 Notes

- All scripts log to `flask_server.log` in the backend directory
- Restart delay is 5-10 seconds to avoid rapid restart loops
- Maximum restart attempts: 10 (configurable)
- Default port: 5000 (configured in app.py)
- Health check interval: 30 seconds (Python script only)

---

## 🆘 Support

If you encounter issues:

1. Check the logs first
2. Verify .env file has all required variables
3. Ensure MySQL is running
4. Check firewall allows port 5000
5. Verify virtual environment is activated

For systemd issues:
```bash
sudo journalctl -u bcf-backend --since "1 hour ago"
```

For script issues:
```bash
tail -f ~/enable_because_future/backend/flask_server.log
```
