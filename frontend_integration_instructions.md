# Frontend Integration Instructions: Try-On Limit Enforcement

This document outlines the backend updates for the try-on limit enforcement feature and instructions on how the frontend should integrate with it.

---

## 1. Try-On Limit Concept
Each user has a dynamic try-on limit (loaded from backend configuration, defaulting to `30`). The backend tracks the user's `tryon_count` in the database.
* **Single try-on requests** (e.g. `/api/tryon`, `/api/tryon-gemini`): Increment `tryon_count` by `1`.
* **Multi try-on requests** (e.g. `/api/tryon/multi`): Increment `tryon_count` by `2`.
* **Layered try-on requests** (e.g. `/api/tryon/layered`): Increment `tryon_count` by the number of garments passed in the request.

---

## 2. API Endpoints for Checking Limits

### A. Dedicated Status Endpoint (Recommended)
Use this new lightweight endpoint to fetch the user's try-on statistics without fetching their full profile.

* **Endpoint**: `GET /api/users/tryon-status`
* **Headers**: `Authorization: Bearer <JWT_TOKEN>`
* **Success Response (`200 OK`)**:
  ```json
  {
    "success": true,
    "data": {
      "tryon_count": 10,
      "tryon_limit": 30,
      "remaining_tryons": 20
    }
  }
  ```

### B. User Profile / Session Payload (Fallback)
If the frontend already stores user profiles in local state, the full user profile payload now also includes the try-on metrics.

* **Endpoint**: `GET /api/users/profile` (also returned on `/login` and `/create-account` actions)
* **Payload Fields**:
  ```json
  {
    "success": true,
    "data": {
      "userid": "user_id_here",
      "email": "user@example.com",
      "tryon_count": 10,
      "tryon_limit": 30
      // ...other profile fields
    }
  }
  ```
* **Remaining Calculation**:
  ```javascript
  const remaining = Math.max(0, user.tryon_limit - user.tryon_count);
  ```

---

## 3. Handling Limit Exceeded Errors

If a user attempts a try-on when their remaining count is insufficient, the backend try-on endpoints will return a `403 Forbidden` response.

### Affected Endpoints:
* `POST /api/tryon`
* `POST /api/tryon/multi`
* `POST /api/tryon/layered`
* `POST /api/tryon-gemini`

### Error Response (`403 Forbidden`):
```json
{
  "success": false,
  "error": "You have reached the limit of 30 tryons. Please contact support or upgrade your plan to continue.",
  "error_code": "TRYON_LIMIT_EXCEEDED"
}
```

---

## 4. Frontend Integration Guidelines

1. **Disable Try-on Actions**:
   - Query `GET /api/users/tryon-status` when mounting the Try-on screen or wardrobe.
   - If `remaining_tryons <= 0`, disable try-on submission buttons and display a helpful banner (e.g., *"You've reached your limit of 30 try-ons. Upgrade your plan to try on more outfits!"*).
   - If a multi-garment / layered try-on is selected, verify that the number of garments is less than or equal to the `remaining_tryons`.

2. **Intercept and Catch 403 Errors**:
   - Wrap your API calls in error handlers.
   - If a `403` HTTP status code is received with `"error_code": "TRYON_LIMIT_EXCEEDED"`, display a modal dialog informing the user they have run out of try-on credits and prompt them with options (e.g., Contact Support, Upgrade Plan, Close).
