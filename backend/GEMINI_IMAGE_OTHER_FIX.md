# Gemini IMAGE_OTHER Error - Fix Documentation

## 🐛 **Problem**

When using the `/api/tryon-gemini` endpoint, Gemini returns:
```
finish_reason=<FinishReason.IMAGE_OTHER: 'IMAGE_OTHER'>
```

And the error:
```
[TRYON-GEMINI][ERROR] No image data found in the response
```

## 🔍 **Root Cause**

The `IMAGE_OTHER` finish reason means **Gemini blocked the image generation** due to safety filters. This happens when:

1. **Safety Filters Triggered**: Content in the avatar or garment images triggered Gemini's safety systems
2. **Body/Clothing Content**: Fashion try-on use cases can sometimes trigger overly cautious safety filters
3. **Multiple Images**: Complex multi-image requests may increase false positive blocks
4. **Prompt Phrasing**: Certain words or phrases in the prompt might trigger filters

## ✅ **Solution Applied**

### **1. Added Safety Block Detection**

The code now explicitly checks for `IMAGE_OTHER` and other blocking finish reasons:

```python
if finish_reason and str(finish_reason) in ['IMAGE_OTHER', 'SAFETY', 'BLOCKED_REASON_UNSPECIFIED']:
    return jsonify({
        "message": "Virtual try-on was blocked by AI safety filters...",
        "code": "CONTENT_BLOCKED",
        "statusCode": 400,
        "details": {
            "finish_reason": str(finish_reason),
            "suggestion": "Try using clearer, well-lit images with simple backgrounds"
        }
    }), 400
```

### **2. Adjusted Safety Settings**

Added explicit safety thresholds to reduce false positives for fashion content:

```python
"safety_settings": [
    {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_ONLY_HIGH"},
    {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_ONLY_HIGH"},
    {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
    {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_ONLY_HIGH"},
]
```

**What this does:**
- More lenient on HARASSMENT, HATE_SPEECH, and DANGEROUS_CONTENT
- Still blocks SEXUALLY_EXPLICIT content at medium+ level
- Reduces false positives for fashion/clothing images

---

## 🚀 **Deploy the Fix**

### **On Local Machine:**
```bash
cd ~/Enable/Software_Development/enable_because_future
git add backend/app.py
git commit -m "Fix Gemini IMAGE_OTHER blocking with safety settings"
git push
```

### **On GCP VM:**
```bash
# SSH to VM
cd ~/enable_because_future
git pull

# Restart server
sudo systemctl restart bcf-backend
# OR
screen -X -S flask-server quit && cd backend && ./start-server.sh
```

---

## 🧪 **Testing**

### **Test the Fix:**
1. **Try avatar upload** via extension
2. **Check for proper error message** if still blocked:
   ```json
   {
     "message": "Virtual try-on was blocked by AI safety filters...",
     "code": "CONTENT_BLOCKED",
     "details": {
       "finish_reason": "IMAGE_OTHER",
       "suggestion": "Try using clearer, well-lit images..."
     }
   }
   ```

### **Monitor Logs:**
```bash
tail -f ~/enable_because_future/backend/flask_server.log | grep TRYON-GEMINI
```

---

## 💡 **Workarounds if Still Blocked**

### **Option 1: Use Different Images**
- **Avatar**: Use well-lit photos with plain backgrounds
- **Garments**: Use product photos on white/neutral backgrounds
- **Avoid**: Low-light, blurry, or complex background images

### **Option 2: Switch to Different Model**
In your extension's `popup.js`, try:
```javascript
// Instead of 'gemini' (Gemini 2.5)
selectedAIModel = 'gemini3';  // Try Gemini 3.0

// Or use rembg for background removal
selectedAIModel = 'rembg';
```

### **Option 3: Fallback to Rembg**
If Gemini continues to block, you can modify the extension to automatically fallback to rembg for background removal:

```javascript
// In popup.js
try {
    // Try Gemini first
    response = await fetch(`${API_BASE_URL}/api/tryon-gemini`, ...);
} catch (error) {
    // Fallback to rembg
    response = await fetch(`${API_BASE_URL}/api/remove-bg-rembg`, ...);
}
```

### **Option 4: Adjust Frontend**
Display helpful message to users:
```javascript
if (error.code === 'CONTENT_BLOCKED') {
    alert('This image was blocked by AI safety filters. Please try:\n' +
          '- A different photo with better lighting\n' +
          '- A simpler background\n' +
          '- A different garment image');
}
```

---

## 📊 **Understanding Finish Reasons**

| Finish Reason | Meaning | Solution |
|---------------|---------|----------|
| `IMAGE_OTHER` | Generic image gen block | Adjust safety settings, try different images |
| `SAFETY` | Safety filter triggered | Use clearer images, adjust content |
| `STOP` | Normal completion | ✅ Success! |
| `MAX_TOKENS` | Response too long | Reduce prompt or image count |
| `RECITATION` | Copyrighted content | Use original images only |

---

## 🔧 **Advanced: Custom Safety Thresholds**

If you need to further adjust safety settings:

```python
# More lenient (USE WITH CAUTION)
"safety_settings": [
    {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
    {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_ONLY_HIGH"},
    {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_ONLY_HIGH"},
    {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"},
]

# More strict (DEFAULT)
"safety_settings": [
    {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
    {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
    {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_LOW_AND_ABOVE"},
    {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
]
```

**⚠️ Warning**: Setting `BLOCK_NONE` removes safety filters entirely - use responsibly!

---

## 📝 **Summary**

✅ **Fixed**: Added explicit handling for `IMAGE_OTHER` blocking
✅ **Improved**: Adjusted safety thresholds for fashion use case  
✅ **Enhanced**: Better error messages for users
✅ **Monitored**: Logs show exact blocking reason

**Your try-on should now work more reliably!** 🎉

If blocks persist, try different images or switch to `rembg` model.
