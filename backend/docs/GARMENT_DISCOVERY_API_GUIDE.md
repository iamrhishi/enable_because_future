# Conversational Garment Discovery API Integration Guide

This guide describes how to use the AI-Powered Conversational Garment Discovery API endpoints in the Flask backend.

---

## Overview

The Conversational Garment Discovery system allows users to interact with an AI fashion assistant through natural dialogue. The system:
1. **Parses User Intent & Preferences**: Extracts slot parameters such as garment category, subcategory, gender, color, price budget (`max_price`), brand, style, material, occasion, and size.
2. **Asks Targeted Follow-Up Questions**: If preferences are missing or ambiguous, the assistant asks clarifying questions and provides quick-reply suggestion chips.
3. **Retrieves & Ranks Garments**: Searches online e-commerce platforms and cached brand catalogs, returning direct product page links, images, price tags, and try-on compatibility flags.
4. **Refines Options Continuously**: Enables progressive refinements such as asking for cheaper options, different colors, another brand, or specific styles while maintaining full session context.

---

## Base URL

```text
http://localhost:8000
```

---

## Authentication

All endpoints support both authenticated users and anonymous guest sessions:
- **JWT Header**: `Authorization: Bearer <your_jwt_token>`
- **Custom Header**: `X-User-ID: <user_id>`
- **JSON Body**: `"user_id": "<user_id>"` (optional, defaults to `"guest"`)

---

## API Endpoints Summary

| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `POST` | `/api/garment-discovery/sessions` | Create a new discovery session |
| `POST` | `/api/garment-discovery/chat` | Main conversational message turn endpoint |
| `POST` | `/api/garment-discovery/refine` | Quick action endpoint to refine recommendations |
| `GET` | `/api/garment-discovery/sessions/<session_id>` | Get session state, preferences, and message history |
| `GET` | `/api/garment-discovery/sessions` | List all discovery sessions for a user |
| `DELETE` | `/api/garment-discovery/sessions/<session_id>` | Delete a session and its message history |

---

## Detailed Endpoint Specifications

### 1. Main Conversational Turn: `POST /api/garment-discovery/chat`

Main endpoint to send user messages and receive AI responses + garment recommendations.

#### Request Body
```json
{
  "session_id": "optional-uuid-string",
  "message": "I am looking for a beige linen blazer under $90 for a summer wedding",
  "user_id": "user_demo_1",
  "preferences_override": {}
}
```

- `session_id` *(optional)*: UUID of an existing session. If omitted, a new session is created automatically.
- `message` *(required)*: User's natural language text prompt.
- `preferences_override` *(optional)*: Object to manually set or update extracted slots.

#### Response Body (200 OK)
```json
{
  "success": true,
  "session_id": "a1b2c3d4-e5f6-7890-abcd-1234567890ab",
  "intent": "search_garments",
  "preferences": {
    "category": "Upper body",
    "subcategory": "Blazers & Jackets",
    "color": "Beige",
    "max_price": 90.0,
    "material": "Linen",
    "occasion": "Wedding"
  },
  "message": {
    "sender": "assistant",
    "content": "Here are the top garments matching your request for Blazers & Jackets in Beige under $90. You can click any item to view product details or start a virtual try-on!",
    "created_at": "2026-07-02 11:30:00"
  },
  "garments": [
    {
      "id": "garment_zara_001",
      "title": "Zara Structured Linen Blend Blazer",
      "brand": "Zara",
      "category": "Upper body",
      "price": 89.90,
      "currency": "$",
      "color": "Beige",
      "sizes_available": ["XS", "S", "M", "L", "XL"],
      "url": "https://www.zara.com/us/en/structured-linen-blend-blazer-p02753021.html",
      "image_url": "https://images.unsplash.com/photo-1591047139829-d91aecb6caea?w=600&auto=format&fit=crop",
      "tryon_ready": true,
      "relevance_score": 0.95
    }
  ],
  "suggested_followups": [
    "Show cheaper options",
    "Try a different color",
    "Show another brand",
    "Filter for casual style"
  ]
}
```

---

### 2. Refine Recommendations: `POST /api/garment-discovery/refine`

Quick action endpoint for common refinement chips.

#### Request Body
```json
{
  "session_id": "a1b2c3d4-e5f6-7890-abcd-1234567890ab",
  "refinement_type": "cheaper",
  "value": "50"
}
```

- `refinement_type` *(required)*: `"cheaper"` \| `"different_color"` \| `"different_brand"` \| `"different_style"`
- `value` *(optional)*: Specific value for the refinement (e.g. color name or brand name).

#### Response Body (200 OK)
Returns updated preferences and newly filtered garment recommendations.

---

### 3. Create Session: `POST /api/garment-discovery/sessions`

#### Request Body
```json
{
  "user_id": "user_demo_1",
  "title": "Summer Beach Wedding Outfit"
}
```

---

### 4. Get Session Details & History: `GET /api/garment-discovery/sessions/<session_id>`

Returns full session context, extracted preference slots, and all past turn messages.

---

### 5. List User Sessions: `GET /api/garment-discovery/sessions?user_id=<user_id>`

Returns list of active discovery sessions for a given user.

---

### 6. Delete Session: `DELETE /api/garment-discovery/sessions/<session_id>`

Deletes a session and its dialogue history.

---

## How to Import & Use Postman Collection

1. Open **Postman**.
2. Click **Import** button in the top left.
3. Select the file: `backend/postman_collection.json`.
4. The collection **"Because Future - AI Conversational Garment Discovery"** will appear with pre-configured requests.
5. Execute `1. Create Discovery Session` or `2. Conversational Chat Turn (Initial Query)`. Postman will automatically save the `session_id` as a collection variable for subsequent requests!
