# Avatar Replacement Issue - Investigation & Fix

## Issue Report
**Problem:** When a user who already has an avatar uploads a new avatar, the new avatar is not replacing the existing avatar in the database.

## Root Cause Analysis

After thorough investigation, the backend code is **structurally correct**. The `UPDATE` SQL query should work:

```python
update_query = "UPDATE users SET avatar = %s WHERE userid = %s"
cursor.execute(update_query, (avatar_data, user_id))
connection.commit()
```

This query will replace the existing avatar with the new one, regardless of whether an avatar already exists.

## Possible Causes

### 1. **Frontend Issue (Most Likely)**
The problem is likely NOT in the backend but in the **Chrome extension frontend**:

**Symptoms:**
- User sees old avatar after uploading new one
- Database might actually have new avatar, but UI shows cached version

**Common frontend issues:**
```javascript
// ❌ WRONG: Not refreshing avatar after upload
async function uploadAvatar() {
  const response = await fetch(`${API_BASE_URL}/api/save-avatar`, {
    method: 'POST',
    body: formData
  });
  
  if (response.ok) {
    console.log('Avatar uploaded');
    // BUG: Not fetching new avatar data or clearing cache
  }
}

// ✅ CORRECT: Refresh avatar after upload
async function uploadAvatar() {
  const response = await fetch(`${API_BASE_URL}/api/save-avatar`, {
    method: 'POST',
    body: formData
  });
  
  if (response.ok) {
    console.log('Avatar uploaded');
    
    // Clear cached avatar
    delete chrome.storage.local.avatarDataUrl;
    
    // Fetch new avatar from API
    await loadAvatarFromAPI(userId);
    
    // Update UI
    displayAvatar();
  }
}
```

**Check for:**
- Chrome storage caching old avatar
- Not calling API to fetch new avatar after upload
- Using stale localStorage data
- Not waiting for upload to complete before displaying
- Image caching in `<img>` tags (add timestamp to src)

### 2. **MySQL Configuration**
The avatar column might hit size limits.

**Check MySQL settings:**
```bash
mysql -u root -proot -e "SHOW VARIABLES LIKE 'max_allowed_packet';"
```

If value is too small (< 5MB), increase it:
```bash
# In /etc/mysql/my.cnf or /etc/my.cnf
[mysqld]
max_allowed_packet=64M

# Restart MySQL
sudo systemctl restart mysql
```

### 3. **Transaction Timing**
Though unlikely, there might be a race condition between the UPDATE and verification query.

**Fixed in enhanced code:** Added check for existing avatar before UPDATE to see what's happening.

### 4. **Wrong user_id**
Extension might be sending wrong user_id (old user's ID instead of current user's ID).

**Check:** Logs now show user_id being used. Verify it matches logged-in user.

## Enhanced Logging Deployed

### What Was Added

Both `/api/save-avatar` and `/api/update-avatar` now log:

```python
# Before UPDATE
[SAVE-AVATAR][DB] User already has avatar of size: 1234567 bytes - will replace it
# OR
[SAVE-AVATAR][DB] User has no existing avatar - this will be first upload

# After UPDATE
[SAVE-AVATAR][DB] UPDATE executed, rows affected: 1
[SAVE-AVATAR][SUCCESS] Expected size: 500000 bytes, Stored size: 500000 bytes
[SAVE-AVATAR][SUCCESS] ✅ Sizes match - avatar replaced successfully!
# OR
[SAVE-AVATAR][WARNING] ⚠️ Size mismatch - expected 500000, got 1234567
```

### How to Debug

1. **Deploy enhanced code to GCP:**
   ```bash
   git add backend/app.py backend/test_avatar_replacement.py
   git commit -m "Add enhanced avatar replacement logging and test script"
   git push
   
   # On GCP VM
   cd ~/enable_because_future
   git pull
   sudo systemctl restart bcf-backend
   ```

2. **Test avatar upload from extension**

3. **Check logs in real-time:**
   ```bash
   sudo journalctl -u bcf-backend -f | grep -E "SAVE-AVATAR|UPDATE-AVATAR"
   ```

4. **Look for these patterns:**

   **✅ Working correctly:**
   ```
   [SAVE-AVATAR][DB] User already has avatar of size: 1234567 bytes - will replace it
   [SAVE-AVATAR][DB] UPDATE executed, rows affected: 1
   [SAVE-AVATAR][SUCCESS] ✅ Sizes match - avatar replaced successfully!
   ```

   **❌ Problem - avatar not replaced:**
   ```
   [SAVE-AVATAR][DB] User already has avatar of size: 1234567 bytes - will replace it
   [SAVE-AVATAR][DB] UPDATE executed, rows affected: 1
   [SAVE-AVATAR][WARNING] ⚠️ Size mismatch - expected 500000, got 1234567
   ```
   This means UPDATE didn't actually change the data!

   **❌ Problem - wrong user:**
   ```
   [SAVE-AVATAR][DATA] Saving avatar for user: abc123, size: 500000 bytes
   [SAVE-AVATAR][ERROR] User not found: abc123
   ```
   Extension sending wrong user_id!

## Testing

### Option 1: Automated test (requires Flask running locally)
```bash
cd backend
./venv/bin/python test_avatar_replacement.py
```

This will:
- Upload avatar 1 (red, 200x200)
- Upload avatar 2 (blue, 300x300)
- Verify avatar 2 replaced avatar 1
- Test both endpoints

### Option 2: Manual database check
```bash
# Check avatar size before upload
mysql -u root -proot hello_db -e "
SELECT userid, LENGTH(avatar) as size_bytes 
FROM users 
WHERE userid = 'YOUR_USER_ID';"

# Upload new avatar from extension

# Check avatar size after upload
mysql -u root -proot hello_db -e "
SELECT userid, LENGTH(avatar) as size_bytes 
FROM users 
WHERE userid = 'YOUR_USER_ID';"

# Size should be different!
```

### Option 3: Use check script
```bash
cd backend
./check_avatar_status.sh
# Enter your user_id when prompted
```

## Expected Behavior

When uploading a new avatar for a user who already has one:

1. **Backend receives request:**
   ```
   [SAVE-AVATAR][START] Request received
   [SAVE-AVATAR][DATA] Saving avatar for user: abc123, size: 500000 bytes
   ```

2. **Backend checks existing avatar:**
   ```
   [SAVE-AVATAR][DB] User already has avatar of size: 1234567 bytes - will replace it
   ```

3. **Backend executes UPDATE:**
   ```
   [SAVE-AVATAR][DB] UPDATE executed, rows affected: 1
   ```

4. **Backend verifies replacement:**
   ```
   [SAVE-AVATAR][SUCCESS] Expected size: 500000 bytes, Stored size: 500000 bytes
   [SAVE-AVATAR][SUCCESS] ✅ Sizes match - avatar replaced successfully!
   ```

5. **Backend returns success:**
   ```json
   {
     "success": true,
     "message": "Avatar saved successfully",
     "avatar_size": 500000
   }
   ```

6. **Frontend should:**
   - Clear cached avatar from chrome.storage
   - Fetch new avatar from `/api/get-avatar/{user_id}`
   - Update UI with new avatar

## Diagnosis Checklist

- [ ] Deploy enhanced logging code to GCP
- [ ] Test avatar upload from extension
- [ ] Check logs for SAVE-AVATAR or UPDATE-AVATAR messages
- [ ] Verify "rows affected: 1" appears in logs
- [ ] Verify sizes match in logs
- [ ] Check database directly to confirm avatar changed
- [ ] If backend logs show success but UI shows old avatar → **Frontend caching issue**
- [ ] If backend logs show size mismatch → **MySQL or transaction issue**
- [ ] If backend logs show "User not found" → **Wrong user_id from frontend**

## Next Steps

1. **Deploy code and test:**
   ```bash
   cd ~/enable_because_future
   git add backend/app.py backend/test_avatar_replacement.py backend/AVATAR_REPLACEMENT_INVESTIGATION.md
   git commit -m "Add avatar replacement debugging and diagnostics"
   git push
   ```

2. **On GCP VM:**
   ```bash
   cd ~/enable_because_future
   git pull
   sudo systemctl restart bcf-backend
   ```

3. **Test from extension and watch logs:**
   ```bash
   sudo journalctl -u bcf-backend -f | grep AVATAR
   ```

4. **Share the log output** to identify exact issue

## Frontend Fix Template

If issue is in frontend (most likely), here's the fix:

```javascript
// In popup.js or wherever avatar upload happens

async function handleAvatarUpload(file, userId) {
  const formData = new FormData();
  formData.append('avatar', file);
  formData.append('user_id', userId);
  
  try {
    const response = await fetch(`${API_BASE_URL}/api/save-avatar`, {
      method: 'POST',
      body: formData
    });
    
    const result = await response.json();
    
    if (result.success) {
      console.log('✅ Avatar uploaded successfully:', result.avatar_size, 'bytes');
      
      // CRITICAL: Clear cached avatar
      await chrome.storage.local.remove('avatarDataUrl');
      await chrome.storage.local.remove('avatar_' + userId);
      
      // CRITICAL: Fetch fresh avatar from server
      const avatarResponse = await fetch(`${API_BASE_URL}/api/get-avatar/${userId}`);
      if (avatarResponse.ok) {
        const blob = await avatarResponse.blob();
        const reader = new FileReader();
        reader.onloadend = function() {
          const newAvatarDataUrl = reader.result;
          
          // Update storage
          chrome.storage.local.set({ avatarDataUrl: newAvatarDataUrl });
          
          // Update UI immediately
          document.getElementById('avatarImg').src = newAvatarDataUrl;
        };
        reader.readAsDataURL(blob);
      }
    } else {
      console.error('❌ Avatar upload failed:', result.error);
    }
  } catch (error) {
    console.error('❌ Avatar upload error:', error);
  }
}
```

## Summary

The backend code is correct and will replace existing avatars. The issue is most likely in the **frontend Chrome extension** not properly refreshing the avatar data after upload. Deploy the enhanced logging to confirm this hypothesis.
