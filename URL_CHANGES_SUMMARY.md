# ✅ URL Configuration Changes Summary

## What Was Changed

I've updated your Chrome extension to use a **centralized configuration** for API URLs, making it easy to switch between development and production modes.

---

## 🎯 The One-Line Switch

**File:** `chrome-extension/popup.js` (Lines 1-14)

### Current Configuration (Development Mode):
```javascript
// 🔧 DEVELOPMENT MODE: Uncomment the line below for local development
const API_BASE_URL = 'http://localhost:5000';

// 🚀 PRODUCTION MODE: Uncomment the line below when deploying to GCP
// const API_BASE_URL = 'http://YOUR_VM_IP:5000';
```

### To Switch to Production:
```javascript
// 🔧 DEVELOPMENT MODE: Uncomment the line below for local development
// const API_BASE_URL = 'http://localhost:5000';

// 🚀 PRODUCTION MODE: Uncomment the line below when deploying to GCP
const API_BASE_URL = 'http://34.123.45.67:5000';  // Replace with your actual VM IP
```

---

## 📝 All Updated Endpoints

I've replaced **all 20+ hardcoded localhost URLs** in your extension with the `API_BASE_URL` variable:

### Updated API Calls:
1. ✅ `/api/wardrobe/user/${userId}` - Load wardrobe items
2. ✅ `/api/proxy-image` - Proxy external images
3. ✅ `/api/wardrobe/save` - Save garment to wardrobe
4. ✅ `/api/wardrobe/remove` - Remove garment from wardrobe
5. ✅ `/api/remove-bg` - Background removal (Garmash)
6. ✅ `/api/remove-bg-rembg` - Background removal (Rembg)
7. ✅ `/api/remove-person-bg` - Background removal (Gemini)
8. ✅ `/api/tryon-gemini` - Virtual try-on API
9. ✅ `/api/login` - User login
10. ✅ `/api/create-account` - Create new account
11. ✅ `/api/update-avatar` - Update user avatar
12. ✅ `/api/get-avatar/${userId}` - Get user avatar
13. ✅ `/api/unified-search` - Search API
14. ✅ `/api/tryon` - Legacy try-on API (debug)

### Updated Error Messages:
- ✅ Connection timeout messages now show dynamic URL
- ✅ Connection refused messages now show dynamic URL
- ✅ All user-facing error messages updated

---

## 🚀 Next Steps

### 1. **Set Up Your GCP VM** (Follow GCP_DEPLOYMENT_GUIDE.md)
   - Create firewall rule for port 5000
   - Clone your repository
   - Install Python dependencies
   - Configure MySQL database
   - Set up environment variables
   - Run Flask as a service

### 2. **Get Your VM External IP**
   ```bash
   # From GCP Console or run this on your VM:
   curl ifconfig.me
   ```

### 3. **Update Chrome Extension**
   - Edit `chrome-extension/popup.js` line 6
   - Replace `YOUR_VM_IP` with your actual external IP
   - Comment out localhost, uncomment production line
   - Reload extension in Chrome

### 4. **Test Everything**
   - Test login/logout
   - Test wardrobe save/load
   - Test try-on functionality
   - Test background removal
   - Check browser console for any errors

---

## 🔄 Switching Between Modes

### Local Development Mode:
```javascript
const API_BASE_URL = 'http://localhost:5000';
// const API_BASE_URL = 'http://34.123.45.67:5000';
```

### Production Mode:
```javascript
// const API_BASE_URL = 'http://localhost:5000';
const API_BASE_URL = 'http://34.123.45.67:5000';
```

**That's it!** Just comment/uncomment these two lines to switch modes.

---

## 🔧 Backend Configuration

Your backend (`app.py`) is already configured correctly:

```python
# Line 2698
app.run(debug=True, host="0.0.0.0", port=5000)
```

- ✅ `host="0.0.0.0"` means it accepts connections from any IP (required for GCP)
- ✅ `port=5000` is the port your extension will connect to
- ✅ CORS is already enabled (line 30: `CORS(app)`)

---

## 📚 Documentation Created

1. **GCP_DEPLOYMENT_GUIDE.md** - Complete step-by-step deployment guide
2. **URL_CHANGES_SUMMARY.md** (this file) - Quick reference for URL configuration

---

## ⚠️ Important Notes

### Security Considerations:
- **Don't commit your .env file** with API keys to Git
- **Consider HTTPS** for production (requires domain + SSL certificate)
- **Restrict firewall rules** to specific IPs if possible (not `0.0.0.0/0`)

### For Better Production Setup:
- Use Gunicorn instead of Flask's development server
- Set up as systemd service for auto-restart
- Use Cloud SQL for managed database
- Implement proper logging and monitoring

---

## 🆘 Quick Troubleshooting

### Extension shows connection errors:
1. ✅ Check `API_BASE_URL` is set to correct IP
2. ✅ Reload Chrome extension
3. ✅ Check browser console (F12) for errors
4. ✅ Verify VM firewall allows port 5000

### Backend not accessible:
1. ✅ Check Flask is running: `sudo systemctl status bcf-backend`
2. ✅ Check port is open: `sudo netstat -tlnp | grep 5000`
3. ✅ Test locally on VM: `curl http://localhost:5000/api/message`
4. ✅ Test externally: `curl http://YOUR_VM_IP:5000/api/message`

### CORS errors:
1. ✅ Verify CORS is enabled in app.py (line 30)
2. ✅ Restart Flask service
3. ✅ Check browser console for specific CORS error

---

## 🎉 Summary

✅ **All URL changes are complete**
✅ **Easy mode switching implemented**
✅ **Complete deployment guide created**
✅ **Backend already configured for external access**

**You're ready to deploy!** Follow the GCP_DEPLOYMENT_GUIDE.md step by step.
