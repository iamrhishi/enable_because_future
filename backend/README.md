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

Server will run on `http://localhost:8000` (default port)

## Web Scraping Support

The backend uses **Scrape.do** with **Scrapy** for extracting product information from e-commerce sites (e.g., Zara). 

**Features:**
- **Scrape.do Integration**: Uses residential proxies and JavaScript rendering to bypass bot detection (required for Zara)
- **Scrapy Selectors**: Powerful CSS/XPath selectors for robust data extraction
- **Brand-Specific Extractors**: Abstract Factory pattern for brand-specific logic (Zara, default extractor)
- **Fail-Fast**: No fallbacks - errors are raised immediately to surface issues

**Configuration:**
- `SCRAPE_DO_API_KEY` - Your Scrape.do API key (required for Zara and protected sites)
- `SCRAPE_DO_ENABLED=True` - Enable Scrape.do (default: False)

**Adding new brands:**
Edit `backend/services/brand_extractors.py` and create a new extractor class inheriting from `BrandExtractor`.

## Logging

The application uses a daily rotating logger that creates log files in the `logs/` directory:
- `logs/app.log` - All application logs (rotated daily, keeps 30 days)
- `logs/errors.log` - Error-level logs only (rotated daily, keeps 30 days)

Logs are in JSON format for easy parsing and debugging. Configure log level via `LOG_LEVEL` in `.env` (DEBUG, INFO, WARNING, ERROR, CRITICAL).

## API Endpoints

### Authentication
- `POST /api/create-account` - Create new account with personal info and body measurements (returns JWT token)
- `POST /api/login` - Login with email and password (returns JWT token)

### User Management
- `GET /api/users/profile` - Get authenticated user's profile (requires auth)
- `PUT /api/users/profile` - Update authenticated user's profile (requires auth)

### Body Measurements
- `POST /api/body-measurements` - Create/update measurements for authenticated user (requires auth)
- `GET /api/body-measurements` - Get authenticated user's measurements (requires auth)
- `PUT /api/body-measurements` - Update authenticated user's measurements (requires auth)

### Avatar
- `POST /api/save-avatar` - Save avatar image (requires auth)
- `GET /api/get-avatar` - Get authenticated user's avatar image (requires auth)
- `PUT /api/update-avatar` - Update avatar (requires auth)

### Garments
- `POST /api/garments/scrape` - Scrape comprehensive product information (RECOMMENDED - returns title, price, images, sizes, colors, brand, category)
- `POST /api/garments/categorize` - Categorize garment from image or metadata
- `POST /api/garments/extract-images` - Extract only images from URL (uses same brand extractors as /scrape)

### Fitting
- `POST /api/fitting/check` - Check if garment fits (requires auth)
- `GET /api/fitting/size-recommendation` - Get size recommendation (requires auth)

### Try-On
- `POST /api/tryon` - Create try-on job (async, requires auth)
  - Supports: `selfie` (file) OR `avatar_id`, `item_urls[]` (JSON array), `garment_image` (file), or `garment_url` (single URL)
  - Automatically scrapes product pages if `item_urls` provided
  - Returns: `{"job_id": "uuid", "status": "queued"}`
- `GET /api/job/<job_id>` - Get job status (requires auth)
  - Returns: `{"status": "queued|processing|done|failed", "result_url": "...", "progress": 0-100}`
- `GET /api/job/<job_id>/result` - Get result image (requires auth)
  - Returns image file or local storage URL
- `POST /api/tryon/multi` - Multi-garment try-on (top + bottom, requires auth)

### Wardrobe Management
- `POST /api/wardrobe/items` - Add garment to wardrobe (requires auth)
  - Supports: image upload (`garment_image`) or URL extraction (`garment_url`)
  - Fields: `fabric` (JSON: `[{"name": "cotton", "percentage": 100}]`), `care_instructions`, `size`, `description`, `category_section`, `category_id`, etc.
- `GET /api/wardrobe/items` - Get wardrobe items (requires auth)
  - Query params: `category`, `category_id`, `search`
- `GET /api/wardrobe/items/<id>` - Get specific wardrobe item (requires auth)
- `PUT /api/wardrobe/items/<id>` - Update wardrobe item (requires auth)
- `DELETE /api/wardrobe/items/<id>` - Delete wardrobe item (requires auth)
- `POST /api/wardrobe/categories` - Create user category (requires auth, requires `category_section`)
- `GET /api/wardrobe/categories` - Get all categories grouped by section (platform + user-created) (requires auth)
- `GET /api/wardrobe/category-sections` - Get all category sections (platform + user-created) (requires auth)
- `POST /api/wardrobe/category-sections` - Create user-specific category section (requires auth)
- `PUT /api/wardrobe/categories/<id>` - Update category (requires auth)
- `DELETE /api/wardrobe/categories/<id>` - Delete category (requires auth)

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
│   ├── auth.py      # Authentication endpoints
│   ├── users.py     # User profile endpoints
│   ├── body_measurements.py  # Body measurements endpoints
│   ├── tryon.py     # Try-on job endpoints
│   ├── garments.py  # Garment scraping/categorization
│   ├── fitting.py   # Fitting and sizing endpoints
│   └── wardrobe.py  # Wardrobe management
├── services/         # Business logic
│   ├── database.py  # Database abstraction layer
│   ├── auth.py      # JWT token generation/validation
│   ├── ai_integration.py  # AI model integration (Gemini API)
│   ├── job_queue.py # Async job processing
│   ├── image_processing.py  # Image validation/resizing
│   ├── storage.py   # Local file storage
│   └── garment_scraper.py  # Product page scraping
├── models/          # Data models
│   ├── user.py      # User model
│   ├── body_measurements.py  # Body measurements model
│   ├── wardrobe.py  # Wardrobe item model
│   └── tryon_job.py # Try-on job model
├── utils/           # Utilities
│   ├── logger.py    # Structured logging
│   ├── validators.py  # Input validation
│   ├── errors.py    # Custom exceptions
│   ├── response.py  # Standardized API responses
│   └── middleware.py # JWT authentication middleware
├── migrations/      # Database migrations
├── scripts/         # Utility scripts
├── config.py        # Configuration
├── app.py          # Main Flask app
└── requirements.txt # Dependencies
```

## Features

### ✅ Implemented Features

- **Custom Authentication:** Form-based sign-up and sign-in with JWT tokens
- **User Profile Management:** CRUD operations for user profiles and body measurements
- **Try-On System:** Async job-based try-on processing with support for:
  - Product URLs (`item_urls[]` array)
  - Direct image uploads
  - Avatar reuse
  - Multi-garment try-on (top + bottom)
- **AI Integration:** Gemini (Nano Banana) API for background removal and try-on processing
- **Image Processing:** Validation, resizing, normalization
- **Local File Storage:** Images stored in local `/images` directory with organized structure
- **Garment Scraping:** Product page scraping and image extraction
- **Garment Categorization:** Automatic categorization of garments
- **Fitting & Sizing:** Fit checking and size recommendations
- **Wardrobe Management:** Complete CRUD operations for wardrobe items and categories
  - Platform-defined category sections (Upper body, Lower body, Accessoires, Wishlist)
  - User-created category sections (custom sections beyond platform ones)
  - Icon support (icon_name/icon_url - not stored in DB, returned via API)
  - Wardrobe items with fabric, care_instructions, size, description fields
  - Platform categories (T-shirts, Shirts, Tops, etc.) + user-created categories
  - All categories properly associated with users
- **Quality Guardrails:** File size limits, dimension validation, queue limits, timeouts
- **Logging:** Daily rotating JSON logs with entry/exit tracking
- **Error Handling:** Standardized error responses, fail-fast approach
- **Code Consistency:** All endpoints use model objects, consistent logging, JWT documentation

### 🔄 Pending Features

- Comprehensive testing (manual testing required)
- Advanced image processing (segmentation, pose estimation)

## Environment Variables

See `.env.example` for all required environment variables.

Key variables:
- `DATABASE_PATH` - SQLite database file path
- `SECRET_KEY` - Flask secret key
- `JWT_SECRET_KEY` - JWT signing key
- `GEMINI_API_KEY` - Google Gemini API key (required for background removal and try-on)
- `GEMINI_MODEL_NAME` - Gemini model to use (default: `gemini-1.5-pro`)
- `IMAGES_DIR` - Base directory for storing images (default: `images`)
- `IMAGES_BASE_URL` - Base URL for serving images (default: `/images`)
- `MAX_QUEUE_SIZE` - Maximum job queue size (default: 50)
- `JOB_TIMEOUT_SECONDS` - Job timeout in seconds (default: 120)

