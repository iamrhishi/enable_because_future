# Login API Not Being Called - Debugging Guide

## Issue Report
**Problem:** Login API (`/api/login`) is not being called when user clicks Sign In button.

## Debugging Steps Added

### 1. Event Listener Attachment Logging
Added console logs to verify the event listener is properly attached:

```javascript
console.log('🔧 [LOGIN] Attaching event listener to signinBtn:', signinBtn);

if (!signinBtn) {
  console.error('❌ [LOGIN] signinBtn element not found! Cannot attach event listener.');
} else {
  console.log('✅ [LOGIN] signinBtn found, attaching click event listener');
}
```

### 2. Button Click Logging
Added logs when button is clicked:

```javascript
signinBtn.addEventListener('click', async function() {
  console.log('🔐 [LOGIN] Sign In button clicked!');
  console.log('📧 [LOGIN] Email field value:', signinEmail?.value);
  console.log('🔑 [LOGIN] Password field exists:', !!signinPassword);
  // ...
});
```

### 3. API Call Logging
Added logs when API is called:

```javascript
console.log('🌐 [LOGIN] Calling login API...');
console.log('🌐 [LOGIN] API URL:', `${API_BASE_URL}/api/login`);
console.log('📤 [LOGIN] Sending credentials:', { email, password: '***' });

const response = await fetch(`${API_BASE_URL}/api/login`, { /* ... */ });

console.log('📥 [LOGIN] Response received:', response.status, response.statusText);
```

## How to Debug

### Step 1: Reload Extension
1. Go to `chrome://extensions/`
2. Find your extension
3. Click "Reload" button

### Step 2: Open Extension and Check Console
1. Click your extension icon to open popup
2. Right-click on popup → "Inspect"
3. Go to "Console" tab

### Step 3: Analyze Logs

#### Scenario A: Event Listener Not Attached
**Look for:**
```
❌ [LOGIN] signinBtn element not found! Cannot attach event listener.
```

**Cause:** Button element doesn't exist in HTML or wrong ID
**Fix:** Check `popup.html` for `<button id="signin-btn">`

#### Scenario B: Button Not Clickable
**Look for:**
```
✅ [LOGIN] signinBtn found, attaching click event listener
```
But when you click the button, you don't see:
```
🔐 [LOGIN] Sign In button clicked!
```

**Possible causes:**
1. Button is disabled
2. Another element is covering the button (z-index issue)
3. Click event is being prevented by another handler
4. Form is submitting and reloading page

**Fix:** 
- Check if button has `disabled` attribute in HTML
- Check CSS for overlapping elements
- Check for other click handlers on button or parent elements

#### Scenario C: Button Clicked But API Not Called
**Look for:**
```
🔐 [LOGIN] Sign In button clicked!
📧 [LOGIN] Email field value: user@example.com
🔑 [LOGIN] Password field exists: true
⚠️ Please fill all fields
```

**Cause:** Validation failing (empty fields)
**Fix:** Make sure email and password fields have values

#### Scenario D: API Call Fails
**Look for:**
```
🌐 [LOGIN] Calling login API...
🌐 [LOGIN] API URL: http://35.198.124.100:5000/api/login
📤 [LOGIN] Sending credentials: { email: 'user@example.com', password: '***' }
❌ [ERROR] Failed to fetch
```

**Possible causes:**
1. Network error (server down, firewall blocking)
2. CORS error
3. Wrong API URL

**Fix:**
- Verify API_BASE_URL is correct
- Check server is running: `curl http://35.198.124.100:5000/api/message`
- Check browser Network tab for CORS errors

#### Scenario E: API Returns Error
**Look for:**
```
📥 [LOGIN] Response received: 401 Unauthorized
❌ Login failed: Invalid credentials
```

**Cause:** Wrong email/password or backend error
**Fix:** Check backend logs, verify credentials

## Common Issues and Solutions

### Issue 1: Form Submitting Instead of Calling Handler
**Symptom:** Page refreshes immediately when clicking button

**Check:** Is the button inside a `<form>` tag?
```html
<form>
  <input id="signin-email" ...>
  <input id="signin-password" ...>
  <button id="signin-btn">Sign In</button> <!-- This will submit form! -->
</form>
```

**Fix:** Either:
1. Change button type to "button":
   ```html
   <button id="signin-btn" type="button">Sign In</button>
   ```
2. Or add `event.preventDefault()`:
   ```javascript
   signinBtn.addEventListener('click', async function(event) {
     event.preventDefault();
     // ... rest of code
   });
   ```

### Issue 2: Async Function Not Awaited
**Check:** Are there any errors in console about unhandled promise rejections?

### Issue 3: API_BASE_URL Wrong
**Check:** Verify at top of `popup.js`:
```javascript
const API_BASE_URL = 'http://35.198.124.100:5000';
```

**Test API manually:**
```bash
curl -X POST http://35.198.124.100:5000/api/login \
  -H "Content-Type: application/json" \
  -d '{"email":"test@example.com","password":"test123"}'
```

### Issue 4: CSP Blocking Fetch
**Check console for:**
```
Refused to connect to 'http://35.198.124.100:5000' because it violates the following Content Security Policy directive: "connect-src 'self'".
```

**Fix:** Update `manifest.json`:
```json
{
  "content_security_policy": {
    "extension_pages": "script-src 'self'; connect-src 'self' http://35.198.124.100:5000 http://localhost:5000 http://127.0.0.1:5000;"
  }
}
```

## Expected Console Output (Success)

```
🔧 [LOGIN] Attaching event listener to signinBtn: <button id="signin-btn" ...>
✅ [LOGIN] signinBtn found, attaching click event listener
🔐 [LOGIN] Sign In button clicked!
📧 [LOGIN] Email field value: user@example.com
🔑 [LOGIN] Password field exists: true
🌐 [LOGIN] Calling login API...
🌐 [LOGIN] API URL: http://35.198.124.100:5000/api/login
📤 [LOGIN] Sending credentials: { email: 'user@example.com', password: '***' }
📥 [LOGIN] Response received: 200 OK
✅ Login successful: { userid: 'abc123', email: 'user@example.com', ... }
```

## Next Steps

1. **Test the extension** with the new logging
2. **Share the console output** - copy all logs from console
3. **Check for the specific scenario** from the list above
4. **Fix based on the scenario** identified

The logs will tell us exactly where the flow is breaking!
