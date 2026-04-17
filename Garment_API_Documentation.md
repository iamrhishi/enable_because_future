# Garment API Documentation

**Project:** BecauseFuture Garment Sizing System  
**Last Updated:** April 11, 2026

---

## Base URL

```
https://ccjdxxgoahfsxnlthxmm.supabase.co/functions/v1
```

## Authentication

All requests require the `apikey` header:

```
apikey: eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImNjamR4eGdvYWhmc3hubHRoeG1tIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzU1MTE0MTUsImV4cCI6MjA5MTA4NzQxNX0.nS0QYp-_ubvp9uwvQhS1ElLVVeMAbgKxAXWeG0jRayw
```

> This is a **public (anon) key** — safe to embed in mobile apps. It does not grant write access.

---

## Endpoint: Get Garment

```
GET /get-garment
```

Retrieves a single garment with brand info and all measurements.

### Query Parameters (provide exactly one)

| Parameter | Type   | Description                          |
|-----------|--------|--------------------------------------|
| `url`     | string | The garment's product page URL       |
| `id`      | uuid   | The garment's unique ID              |
| `sku`     | string | The garment's SKU code               |

### Example Requests

**By URL:**
```
GET https://ccjdxxgoahfsxnlthxmm.supabase.co/functions/v1/get-garment?url=https://brand.com/product-page
```

**By ID:**
```
GET https://ccjdxxgoahfsxnlthxmm.supabase.co/functions/v1/get-garment?id=691905ca-e414-4e7c-a321-106b5e118232
```

**By SKU:**
```
GET https://ccjdxxgoahfsxnlthxmm.supabase.co/functions/v1/get-garment?sku=ASD
```

### Required Headers

```http
apikey: eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImNjamR4eGdvYWhmc3hubHRoeG1tIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzU1MTE0MTUsImV4cCI6MjA5MTA4NzQxNX0.nS0QYp-_ubvp9uwvQhS1ElLVVeMAbgKxAXWeG0jRayw
Content-Type: application/json
```

### cURL Example

```bash
curl -X GET \
  "https://ccjdxxgoahfsxnlthxmm.supabase.co/functions/v1/get-garment?url=https://lastdecades.de/collections/vintage-sweater-und-pullis/products/vintage-sweater-xl-057769" \
  -H "apikey: eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImNjamR4eGdvYWhmc3hubHRoeG1tIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzU1MTE0MTUsImV4cCI6MjA5MTA4NzQxNX0.nS0QYp-_ubvp9uwvQhS1ElLVVeMAbgKxAXWeG0jRayw"
```

---

## Response

### 200 OK — Garment Found

```json
{
  "id": "691905ca-e414-4e7c-a321-106b5e118232",
  "brand_id": "0369d916-39c4-469c-ac17-0379c12b7d87",
  "name": "T-shirt",
  "sku": "ASD",
  "category": "top",
  "subcategory": "T-shirt",
  "fit_type": "regular",
  "material_stretch": "slight",
  "size_label": "L, XL, M, S",
  "color": "Black",
  "collection": "ASD",
  "season": "ASD",
  "online_url": "https://lastdecades.de/collections/vintage-sweater-und-pullis/products/vintage-sweater-xl-057769",
  "description": null,
  "image_url": null,
  "is_active": true,
  "created_at": "2026-04-09T17:49:32.265915+00:00",
  "updated_at": "2026-04-11T09:46:49.667832+00:00",
  "brand_partners": null,
  "garment_measurements": [
    {
      "measurement_type": "breast_width",
      "value_cm": 55
    },
    {
      "measurement_type": "front_length",
      "value_cm": 55
    },
    {
      "measurement_type": "arm_length",
      "value_cm": 55
    },
    {
      "measurement_type": "arm_width",
      "value_cm": 55
    }
  ]
}
```

### Response Fields

| Field                  | Type     | Description                                              |
|------------------------|----------|----------------------------------------------------------|
| `id`                   | uuid     | Unique garment identifier                                |
| `brand_id`             | uuid     | ID of the brand that owns this garment                   |
| `name`                 | string   | Garment name                                             |
| `sku`                  | string?  | Stock keeping unit (nullable)                            |
| `category`             | enum     | `"top"` or `"bottom"`                                    |
| `subcategory`          | string?  | e.g. "T-shirt", "Trousers" (nullable)                    |
| `fit_type`             | enum     | `"fitted"`, `"regular"`, `"oversized"`, `"slim"`, `"wide"` |
| `material_stretch`     | enum     | `"none"`, `"slight"`, `"very_stretchy"`                  |
| `size_label`           | string   | Comma-separated sizes, e.g. `"S, M, L, XL"`             |
| `color`                | string?  | Color (nullable)                                         |
| `collection`           | string?  | Collection name (nullable)                               |
| `season`               | string?  | Season code, e.g. `"SS25"` (nullable)                    |
| `online_url`           | string?  | Product page URL (nullable)                              |
| `description`          | string?  | Product description (nullable)                           |
| `image_url`            | string?  | Image URL (nullable)                                     |
| `is_active`            | boolean  | Whether garment is active                                |
| `created_at`           | datetime | ISO 8601 timestamp                                       |
| `updated_at`           | datetime | ISO 8601 timestamp                                       |
| `brand_partners`       | object?  | `{ brand_name, website }` or null                        |
| `garment_measurements` | array    | List of measurements (see below)                         |

### Measurement Object

| Field              | Type   | Description                    |
|--------------------|--------|--------------------------------|
| `measurement_type` | string | See measurement types below    |
| `value_cm`         | number | Measurement value in cm        |

### Measurement Types

**For Tops (`category: "top"`):**
| Type            | Description                                      |
|-----------------|--------------------------------------------------|
| `breast_width`  | Breast width, under arm left to right (one way)  |
| `front_length`  | Front length from shoulder to hem                |
| `arm_length`    | Sleeve length                                    |
| `arm_width`     | Sleeve opening width                             |

**For Bottoms (`category: "bottom"`):**
| Type               | Description                                  |
|--------------------|----------------------------------------------|
| `waist`            | Waist width (one way)                        |
| `hip`              | Hip width (one way)                          |
| `front_crotch`     | Waistband to crotch seam                     |
| `inner_leg_length` | Crotch to hem                                |
| `thigh`            | Thigh width at widest point (one way)        |

---

## Error Responses

### 400 Bad Request — Missing Parameter

```json
{
  "error": "Provide 'id', 'sku', or 'url' query parameter"
}
```

### 404 Not Found — No Matching Garment

```json
{
  "error": "Garment not found"
}
```

### 500 Internal Server Error

```json
{
  "error": "Internal server error"
}
```

---

## Notes

- All measurements are in **centimeters** and represent **one-way front measurements** (not full circumference).
- The `url` parameter matches against the garment's `online_url` field exactly.
- No user authentication is required — this is a public read-only endpoint.
- The API key above is a publishable key safe to include in client apps.
