# Try-On API Documentation

**Project:** BecauseFuture Virtual Try-On System
**Last Updated:** April 13, 2026
**Base URL:** `https://your-server.com/api`

---

## Overview

The BecauseFuture backend provides multiple try-on APIs for different use cases:

| Endpoint | Use Case | Type |
|----------|----------|------|
| `POST /api/tryon` | Single garment try-on | Async (job queue) |
| `POST /api/tryon/layered` | Multi-garment layering (top + jacket) | Sync |
| `POST /api/tryon/multi` | Parallel multi-garment (separate results) | Async |
| `GET /api/job/{job_id}` | Check job status | - |
| `GET /api/job/{job_id}/result` | Get try-on result image | - |

---

## Authentication

All try-on endpoints require JWT authentication:

```
Authorization: Bearer <jwt_token>
```

Get token via `/api/login` or `/api/create-account`.

---

## 1. Single Garment Try-On

### `POST /api/tryon`

Apply a single garment on the user's avatar. Returns a job ID for async processing.

### Request (multipart/form-data)

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `selfie` | File | No | Person image. If omitted, uses saved avatar |
| `wardrobe_item_id` | String | Option 1 | ID of wardrobe item to try on |
| `item_urls` | JSON Array | Option 2 | Product URLs to scrape, e.g. `["https://zara.com/..."]` |
| `garment_image` | File | Option 3 | Direct garment image upload |
| `garment_url` | String | Option 4 | Direct garment image URL |
| `options` | JSON | No | `{"garment_index": 0}` for selecting image from scraped results |

**Note:** Provide at least one garment source (wardrobe_item_id, item_urls, garment_image, or garment_url).

Poll `GET /api/job/{job_id}` using `poll_interval_ms` from the creation response until `status` is `done` or `failed`.

### Response

```json
{
  "success": true,
  "data": {
    "job_id": "c6e2dd9f-34cd-4578-9055-107034e827ce",
    "status": "queued",
    "estimated_time": 15,
    "poll_interval_ms": 1000
  }
}
```

**Polling:** Clients choose the scheduler; `poll_interval_ms` is the server recommendation (configured with `JOB_STATUS_POLL_INTERVAL_MS` in `.env`, default **1000** ms so you land near **1s** polling; use **1500** there if you prefer 1.5s). Narrower intervals trim perceived wait after inference finishes earlier; inference time itself is unchanged.

### Example

```bash
curl -X POST "https://server.com/api/tryon" \
  -H "Authorization: Bearer <token>" \
  -F "item_urls=[\"https://www.zara.com/product/12345\"]"
```

---

## 2. Layered Multi-Garment Try-On

### `POST /api/tryon/layered`

Apply multiple garments sequentially with layering. Result of garment 1 becomes the base for garment 2, etc.

**Use case:** Top + Jacket, Dress + Coat, Shirt + Blazer

### How It Works

1. **Garment 1:** Applied on original avatar using standard try-on
2. **Garment 2+:** Applied OVER the previous result (preserves existing clothing)

### Request (multipart/form-data)

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `person_image` | File | No | Person image. If omitted, uses saved avatar |
| `garment_images[]` | Files | Option 1 | Array of garment images (in order to apply) |
| `garment_urls[]` | Strings | Option 2 | Array of product URLs to scrape |
| `garment_types[]` | Strings | No | Array of types: 'upper', 'lower', 'outerwear' |

### Response

```json
{
  "success": true,
  "data": {
    "results": [
      {
        "layer": 1,
        "garment_type": "upper",
        "result_url": "https://server.com/images/tryon-results/user123/abc_layer1.png"
      },
      {
        "layer": 2,
        "garment_type": "upper",
        "result_url": "https://server.com/images/tryon-results/user123/abc_layer2.png"
      }
    ],
    "final_result_url": "https://server.com/images/tryon-results/user123/abc_layer2.png",
    "layers_processed": 2
  },
  "message": "Layered try-on complete with 2 garments"
}
```

### Example

```bash
curl -X POST "https://server.com/api/tryon/layered" \
  -H "Authorization: Bearer <token>" \
  -F "garment_images[]=@top.png" \
  -F "garment_images[]=@jacket.png" \
  -F "garment_types[]=upper" \
  -F "garment_types[]=outerwear"
```

### Limits

- Maximum 5 garments per request
- Synchronous processing (30-60+ seconds for multiple garments)
- All intermediate results are saved and returned

---

## 3. Parallel Multi-Garment Try-On

### `POST /api/tryon/multi`

Creates separate try-on jobs for top and bottom garments. Each processes independently on the original avatar.

**Note:** This does NOT combine garments - it creates 2 separate results.

### Request (multipart/form-data)

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `person_image` | File | No | Person image. If omitted, uses saved avatar |
| `top_garment_image` | File | Option 1 | Top garment image |
| `top_garment_url` | String | Option 2 | Top garment URL |
| `bottom_garment_image` | File | Option 1 | Bottom garment image |
| `bottom_garment_url` | String | Option 2 | Bottom garment URL |

### Response

```json
{
  "success": true,
  "data": {
    "top_job_id": "abc123",
    "bottom_job_id": "def456",
    "status": "queued",
    "estimated_time": 30,
    "poll_interval_ms": 1000
  },
  "message": "Multi-garment try-on jobs created"
}
```

---

## 4. Job Status

### `GET /api/job/{job_id}`

Check the status of an async try-on job.

While the job is in progress (`queued` or `processing`), each response includes `poll_interval_ms` (same meaning as `POST /api/tryon`; `null` when `done` or `failed`).

### Response - Queued

```json
{
  "success": true,
  "data": {
    "job_id": "c6e2dd9f-34cd-4578-9055-107034e827ce",
    "status": "queued",
    "progress": 0,
    "poll_interval_ms": 1000
  }
}
```

### Response - Processing

```json
{
  "success": true,
  "data": {
    "job_id": "c6e2dd9f-34cd-4578-9055-107034e827ce",
    "status": "processing",
    "progress": 50,
    "poll_interval_ms": 1000
  }
}
```

### Response - Done

```json
{
  "success": true,
  "data": {
    "job_id": "c6e2dd9f-34cd-4578-9055-107034e827ce",
    "status": "done",
    "progress": 100,
    "poll_interval_ms": null,
    "result_url": "https://server.com/images/tryon-results/user123/result.png",
    "garment_url": "https://www.zara.com/product/12345"
  }
}
```

### Response - Failed

```json
{
  "success": true,
  "data": {
    "job_id": "c6e2dd9f-34cd-4578-9055-107034e827ce",
    "status": "failed",
    "poll_interval_ms": null,
    "error": "Error message here"
  }
}
```

---

## 5. Job Result

### `GET /api/job/{job_id}/result`

Get the result image URL for a completed job.

### Response - Success

```json
{
  "success": true,
  "data": {
    "result_url": "https://server.com/images/tryon-results/user123/result.png",
    "garment_url": "https://www.zara.com/product/12345"
  }
}
```

### Response - Not Ready

```json
{
  "success": false,
  "error": "Job result not ready yet. Status: processing",
  "error_code": "VALIDATION_ERROR"
}
```

---

## Choosing the Right Endpoint

| Scenario | Recommended Endpoint |
|----------|---------------------|
| Try on a single top/bottom | `POST /api/tryon` |
| Try on top + jacket (layered) | `POST /api/tryon/layered` |
| Try on shirt + blazer | `POST /api/tryon/layered` |
| Try on top and bottom separately | `POST /api/tryon/multi` |
| Async processing with polling | `POST /api/tryon` + `GET /api/job/{id}` |
| Immediate result (wait for completion) | `POST /api/tryon/layered` |

---

## AI Model Details

All try-on processing uses **Google Gemini API** with image generation capabilities.

### Single Garment Mode
- Prompt: "dress the person with the garment"
- Replaces existing clothing with new garment

### Layered Mode (for 2nd+ garments)
- Prompt: "Add garment OVER existing outfit, preserve clothing underneath"
- Explicitly preserves existing clothes and adds new layer on top

---

## Error Codes

| Code | Description |
|------|-------------|
| `VALIDATION_ERROR` | Invalid input parameters |
| `AUTH_REQUIRED` | Missing or invalid JWT token |
| `NOT_FOUND` | Job or resource not found |
| `GENERATION_ERROR` | AI model failed to generate image |
| `EXTERNAL_SERVICE_ERROR` | Gemini API or scraping service failed |

---

## Rate Limits

- Try-on requests: Dependent on Gemini API quotas
- Recommended: Poll job status every 2-3 seconds
- Layered try-on: Allow 15-30 seconds per garment

---

## Notes

1. **Avatar:** If no person image is provided, the user's saved avatar (via `/api/save-avatar`) is used automatically.

2. **Garment URL Tracking:** All try-on results now include `garment_url` linking back to the source product page.

3. **Image Storage:** All result images are stored on the server with absolute URLs returned for frontend use.

4. **Background Removal:** Avatars should have background removed. Use `/api/save-avatar` which automatically removes background using Gemini.
