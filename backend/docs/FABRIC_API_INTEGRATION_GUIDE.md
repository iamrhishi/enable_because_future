# Fabric API Integration Guide

This guide describes how the new **Fabric Composition Extraction** feature is integrated into the backend and how to use it in the mobile app / API clients.

---

## Overview

When scraping garments or adding items via URLs (e.g., Zara), the backend automatically extracts fabric composition details (materials and their percentage) from the product page.
- **Extraction Mechanism**: Combines regex heuristics on product page texts (handles both prefix and suffix percentage patterns like `100% cotton` and `elastane 5% and cotton 95%`) and registers standardized names.
- **Normalization**: Automatically maps materials to standard keys (like `elasthan` for spandex/lycra, `viscose` for rayon, `lyocell` for tencel) and scales percentages so they always sum to exactly `100%`.
- **Database Caching**: Caches the extracted fabric composition JSON in the database (`garment_metadata`) to avoid duplicate scrapers/requests.

---

## Fabric Data Model

The `fabric` field is returned as a JSON array of objects:

| Field | Type | Description |
| :--- | :--- | :--- |
| `name` | `string` | Standardized fabric name: `'cotton'`, `'polyester'`, `'elasthan'`, `'wool'`, `'cashmere'`, `'viscose'`, `'lyocell'`, `'silk'`, or `'other'`. |
| `percentage` | `integer` | The percentage of the fabric composition (1-100). |

### Example JSON:
```json
[
  {
    "name": "cotton",
    "percentage": 95
  },
  {
    "name": "elasthan",
    "percentage": 5
  }
]
```

---

## Affected Endpoints

### 1. Scrape Product Details
- **Endpoint**: `POST /api/garments/scrape` (and `/api/garments/refresh`)
- **Response `data` block additions**:
  ```json
  {
    "success": true,
    "data": {
      "url": "https://www.zara.com/...",
      "title": "Oversized Leather Jacket",
      "price": "29990",
      "images": [...],
      "sizes": ["S", "M", "L"],
      "colors": ["Black"],
      "brand": "Zara",
      "category": "upper",
      "type": "jacket",
      "confidence": 0.95,
      "fabric": [
        {
          "name": "other",
          "percentage": 100
        }
      ]
    }
  }
  ```

### 2. Extract Product Info for Wardrobe
- **Endpoint**: `POST /api/wardrobe/items/extract-from-url`
- **Response `data` block additions**:
  Same as `/api/garments/scrape`, returns the `fabric` field parsed and cached.

### 3. Add Item to Wardrobe / Wishlist
- **Endpoint**: `POST /api/wardrobe/items`
- **Request Parameters**:
  - Can accept `fabric` either as a raw JSON string (e.g. `'[{"name": "cotton", "percentage": 100}]'`) or direct JSON array if submitted via JSON body.
  - If a URL is submitted and `fabric` is not provided in request body, the backend will auto-fill from scraped data.

---

## Database Caching Schema

The `garment_metadata` table contains a new column `fabric` (TEXT):
```sql
ALTER TABLE garment_metadata ADD COLUMN fabric TEXT;
```

---

## Frontend Flutter Integration Guide (Next Steps)

When you are ready to integrate this into the Flutter frontend, follow these steps:

### 1. Update `ScrapProductEntity`
File: `lib/features/garments/domain/entities/scrape_product_entity.dart`
- Import `FabricEntity` from the wardrobe package:
  ```dart
  import '../../../wardrobe/domain/entities/garment_entity.dart';
  ```
- Add the `fabric` field:
  ```dart
  final List<FabricEntity>? fabric;
  ```

### 2. Update `ScrapProductModel`
File: `lib/features/garments/data/models/scrape_product_model.dart`
- Deserialize the field in `fromJson`:
  ```dart
  fabric: (data?["fabric"] as List<dynamic>?)
      ?.map((e) => FabricModel.fromJson(e as Map<String, dynamic>))
      .toList(),
  ```
- Serialize it in `toJson`:
  ```dart
  "fabric": fabric?.map((e) => (e as FabricModel).toJson()).toList(),
  ```

### 3. Display in Detail UI
File: `lib/features/disovery online/presentation/online_product_detail_page.dart`
- Render the fabric info row in the product details panel using the pre-existing extension helper:
  ```dart
  if (scrap.fabric != null && scrap.fabric!.isNotEmpty) ...[
    const SizedBox(height: 20),
    const Divider(color: Color(0xFFE2E6E8), height: 1, thickness: 1),
    const SizedBox(height: 20),
    _buildInfoRow("Fabric:", scrap.fabric!.toDisplayString()),
  ]
  ```
