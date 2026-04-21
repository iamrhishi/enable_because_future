# Frontend-Backend API Configuration Guide

## Overview
The frontend and backend are now configured to work together across different environments (local development and production).

## Environment Configuration

### Frontend (.env files)

#### `.env.production` (for production deployment)
```
REACT_APP_API_URL=http://agents.enableyou.co:5000
REACT_APP_FRONTEND_URL=http://agents.enableyou.co:3000
```

#### `.env.development` (for local development)
```
REACT_APP_API_URL=http://localhost:5000
REACT_APP_FRONTEND_URL=http://localhost:3000
```

### Backend Configuration

The backend loads `FRONTEND_URL` from the `.env` file:
```
FRONTEND_URL=http://agents.enableyou.co:3000
```

## How It Works

### Local Development
1. Frontend runs on `http://localhost:3000` with `npm start`
2. Backend runs on `http://localhost:5000`
3. Frontend uses the `proxy` setting in `package.json` to route API calls to `http://localhost:5000`
4. Environment: `REACT_APP_API_URL` is empty/relative, so API calls use proxy

### Production Deployment (Remote Server)
1. Frontend builds with `.env.production` and is served from `http://agents.enableyou.co:3000`
2. Backend runs on `http://agents.enableyou.co:5000`
3. Frontend uses `REACT_APP_API_URL=http://agents.enableyou.co:5000` to make API calls
4. Backend OAuth callback redirects to `FRONTEND_URL=http://agents.enableyou.co:3000/agents`

## API Request Flow

### Using the API Service
Update components to use the centralized API service:

```javascript
import { apiRequest, endpoints } from '../services/api';

// Example: Remove background
const response = await apiRequest(endpoints.removeBg, {
  method: 'POST',
  body: formData
});

// The service automatically prepends REACT_APP_API_URL if set
```

## Deployment Steps

### On Remote Server (agents.enableyou.co)

1. **Build Frontend:**
   ```bash
   cd frontend
   npm run build
   ```
   This uses `.env.production` with `REACT_APP_API_URL=http://agents.enableyou.co:5000`

2. **Serve Frontend:**
   - Static files from `frontend/build/` on port 3000
   - Or use `serve -s build -l 3000`

3. **Backend Configuration:**
   ```bash
   cd backend
   # In .env:
   FRONTEND_URL=http://agents.enableyou.co:3000
   ```

4. **Run Backend:**
   ```bash
   python app.py
   # Runs on port 5000
   ```

## Verification Checklist

- [ ] Backend `.env` has `FRONTEND_URL=http://agents.enableyou.co:3000`
- [ ] Frontend `.env.production` has `REACT_APP_API_URL=http://agents.enableyou.co:5000`
- [ ] Frontend built with `npm run build` (uses `.env.production`)
- [ ] Frontend served on port 3000
- [ ] Backend running on port 5000
- [ ] CORS enabled on backend for `http://agents.enableyou.co:3000`
- [ ] OAuth callback redirects to correct frontend URL

## OAuth Flow

1. User clicks "Login with Google"
2. Frontend redirects to Google OAuth consent screen
3. After user approves, Google redirects to: `http://agents.enableyou.co:5000/api/oauth/google/callback?code=...`
4. Backend processes code and redirects to: `http://agents.enableyou.co:3000/agents`
5. Frontend loads `/agents` page with user authenticated

## Troubleshooting

### API calls return 404
- Check that `REACT_APP_API_URL` matches backend URL
- Verify backend is running on correct port
- Check CORS configuration in backend

### OAuth redirects to wrong URL
- Verify `FRONTEND_URL` in backend `.env`
- Check Google OAuth application settings for correct redirect URI

### Frontend served but API calls fail
- Frontend might still be using relative paths
- Update components to use the `apiRequest` service
- Check browser console for actual API request URL
