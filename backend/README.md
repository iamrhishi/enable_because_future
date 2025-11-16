# Because Future Backend API

Backend API for Because Future - Virtual Try-On Platform

## Setup

1. **Install dependencies:**
   ```bash
   cd backend
   python3 -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   pip install -r requirements.txt
   ```

2. **Configure environment:**
   ```bash
   cp env.template .env
   # Edit .env with your credentials (see env.template for required variables)
   # Generate secret keys:
   # python -c "import secrets; print(secrets.token_hex(32))"
   ```

3. **Initialize database:**
   ```bash
   python init_db.py
   # Or run migrations directly:
   python scripts/run_migrations.py
   ```

4. **Validate setup (optional):**
   ```bash
   python scripts/validate.py
   ```

5. **Run the server:**
   ```bash
   python app.py
   ```

Server will run on `http://localhost:5000`

## Logging

The application uses a daily rotating logger that creates log files in the `logs/` directory:
- `logs/app.log` - All application logs (rotated daily, keeps 30 days)
- `logs/errors.log` - Error-level logs only (rotated daily, keeps 30 days)

Logs are in JSON format for easy parsing and debugging. Configure log level via `LOG_LEVEL` in `.env` (DEBUG, INFO, WARNING, ERROR, CRITICAL).

## API Endpoints

### Authentication
- `POST /api/create-account` - Create new account (returns JWT token)
- `POST /api/login` - Login (returns JWT token)
- `POST /api/oauth/google` - Google OAuth sign-in

### User Management
- `GET /api/get-user-data/<user_id>` - Get user data (requires auth)
- `PUT /api/update-user-data/<user_id>` - Update user data (requires auth)

### Body Measurements
- `POST /api/body-measurements` - Create/update measurements (requires auth)
- `GET /api/body-measurements/<user_id>` - Get measurements (requires auth)
- `PUT /api/body-measurements/<user_id>` - Update measurements (requires auth)

### Avatar
- `POST /api/save-avatar` - Save avatar image (requires auth)
- `GET /api/get-avatar/<user_id>` - Get avatar image (requires auth)
- `PUT /api/update-avatar` - Update avatar (requires auth)

### Garments
- `POST /api/garments/scrape` - Scrape product page
- `POST /api/garments/categorize` - Categorize garment
- `POST /api/garments/extract-images` - Extract images from URL

### Fitting
- `POST /api/fitting/check` - Check if garment fits (requires auth)
- `GET /api/fitting/size-recommendation` - Get size recommendation (requires auth)

### Try-On
- `POST /api/tryon` - Create try-on job (async, requires auth)
- `GET /api/job/<job_id>` - Get job status (requires auth)
- `GET /api/job/<job_id>/result` - Get result image (requires auth)
- `POST /api/tryon/multi` - Multi-garment try-on (requires auth)

### Wardrobe
- `POST /api/wardrobe/save` - Save garment to wardrobe (requires auth)
- `GET /api/wardrobe/user/<user_id>?category=upper&search=shirt` - Get wardrobe (requires auth)
- `DELETE /api/wardrobe/remove` - Remove garment (requires auth)

### Utilities
- `GET /health` - Health check
- `POST /api/remove-bg` - Remove background from image

## Authentication

Most endpoints require JWT authentication. Include the token in the Authorization header:

```
Authorization: Bearer <your_jwt_token>
```

Tokens are returned from `/api/create-account` and `/api/login` endpoints.

## Testing

Import `postman_collection.json` into Postman for easy testing. The collection includes:
- Pre-configured requests for all endpoints
- Automatic token extraction and storage
- Example request bodies

## Database Migrations

Run migrations to update database schema:

```bash
python scripts/run_migrations.py
```

Migrations are versioned and tracked in the `schema_migrations` table.

## Project Structure

```
backend/
├── api/              # API blueprints (routes)
├── services/         # Business logic
├── models/          # Data models
├── utils/           # Utilities (errors, validators, etc.)
├── migrations/      # Database migrations
├── scripts/         # Utility scripts
├── config.py        # Configuration
├── app.py          # Main Flask app
└── requirements.txt # Dependencies
```

## Environment Variables

See `.env.example` for all required environment variables.

Key variables:
- `DATABASE_PATH` - SQLite database file path
- `SECRET_KEY` - Flask secret key
- `JWT_SECRET_KEY` - JWT signing key
- `BG_SERVICE_URL` - Background removal service URL
- `MIXER_SERVICE_URL` - Try-on service URL
- `GEMINI_API_KEY` - Gemini API key (optional)
- `GOOGLE_CLIENT_ID` - Google OAuth client ID

