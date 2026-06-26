# Frontend Integration Guide: Body Measurements Estimation

This document provides instructions for frontend developers integrating with the new AI body measurement estimation endpoint.

---

## 1. Endpoint Overview

The backend uses a MediaPipe Pose Landmarker and Selfie Segmenter pipeline to calculate physical body measurements in centimeters based on a user's height, weight, and front-facing (plus optional side-facing) photos.

* **Endpoint**: `POST /api/body-measurements/estimate`
* **Authentication**: Required (JWT Bearer Token in `Authorization` header)
* **Headers**: `Content-Type: application/json`

---

## 2. Request Structure

### JSON Body Fields:
- `height` (required, `number`): User's height in centimeters. Must be between 50 and 250 cm.
- `weight` (required, `number`): User's weight in kilograms. Must be between 20 and 250 kg.
- `frontImage` (required, `string`): Base64 data URI of the front-facing body photo (e.g., `data:image/jpeg;base64,...`).
- `sideImage` (optional, `string`): Base64 data URI of the side-profile body photo.
- `save` (optional, `boolean`): Whether to save the estimated measurements to the database. Defaults to `false`. Can also be sent as a query parameter `?save=true`.

### Example Request Payload:
```json
{
  "height": 175.0,
  "weight": 70.0,
  "frontImage": "data:image/jpeg;base64,/9j/4AAQSkZJRg...",
  "sideImage": "data:image/jpeg;base64,/9j/4AAQSkZJRg...",
  "save": false
}
```

---

## 3. Response Structure

On success, the estimated measurements are returned to the user. By default, they are NOT saved to the database directly. To save the estimated measurements to the user's record in the database, you must send the request again with `"save": true` in the JSON request body (or pass `?save=true` as a query parameter).

### Success Response (`200 OK`):
```json
{
  "success": true,
  "message": "Body measurements estimated and updated successfully",
  "data": {
    "measurements": {
      "id": 1,
      "user_id": "f3a6ad94",
      "height": 175.0,
      "weight": 70.0,
      "shoulder_circumference": 101.0,
      "arm_length": 51.0,
      "breast_circumference": 95.3,
      "under_breast_circumference": 74.8,
      "waist_circumference": 68.9,
      "hip_circumference": 87.2,
      "upper_thigh_circumference": 55.9,
      "biceps_circumference": 27.4,
      "collarbone_to_belly_button_length": 29.6,
      "waist_to_crotch_front_length": 22.5,
      "waist_to_crotch_back_length": 27.9,
      "inner_leg_length": 65.8,
      "foot_length": 25.7,
      "foot_width": 9.8,
      "unit": "metric",
      "created_at": "2026-06-24T12:24:00",
      "updated_at": "2026-06-24T12:24:00"
    },
    "confidence": 0.94,
    "frontOverlay": "data:image/png;base64,iVBORw0KG...",
    "sideOverlay": "data:image/png;base64,iVBORw0KG..."
  }
}
```

#### Fields returned in `data`:
* `measurements`: The updated database record representing all physical dimensions.
* `confidence`: A float representing the estimation's confidence metric.
* `frontOverlay`: Base64 PNG data URI containing the neon pose overlay/calipers drawn on top of the front photo.
* `sideOverlay`: Base64 PNG data URI overlay drawn on the side photo (or `null` if no side image was uploaded).

---

## 4. Error Responses

- **`400 Bad Request`**: Occurs if request payload format or parameters are invalid, or if the AI pipeline cannot detect a pose in the image:
  ```json
  {
    "success": false,
    "error": "No pose landmarks detected in the front-facing image. Please ensure the entire body is visible.",
    "error_code": "VALIDATION_ERROR"
  }
  ```
- **`415 Unsupported Media Type`**: Occurs if `Content-Type` header is not `application/json`.
- **`401 Unauthorized`**: Occurs if the JWT Bearer Token is missing, expired, or invalid.

---

## 5. Client Integration Best Practices

1. **Client-Side Image Downscaling (Highly Recommended)**:
   - High-resolution photos from smartphones (e.g. 12MP/48MP) should be resized before sending them over the network.
   - Resize images to a maximum height of `1280px` on a `<canvas>` element before base64 encoding them. This saves bandwidth, memory, and improves processing latency.
2. **Pose Guidelines for Users**:
   - Instruct the user to stand with the **entire body visible** (from head to toe).
   - Hold arms slightly away from the torso (A-pose) for front-facing photos.
   - Use form-fitting clothing to ensure accurate silhouette segmentation.
3. **Displaying Debug Overlays**:
   - Display `frontOverlay` and `sideOverlay` in the UI to give users a scanner-like experience. They can review where the joints and calipers were detected.

---

## 6. Estimate with Saved Avatar

If a user has already saved their avatar image in the system (via the `/api/save-avatar` or `/api/save-avatar-local` endpoints), you do not need to prompt them to upload/take a new front-facing photo. Instead, you can run the body measurement estimation pipeline using their stored avatar image as the front-facing photo.

* **Endpoint**: `POST /api/body-measurements/estimate-with-avatar`
* **Authentication**: Required (JWT Bearer Token in `Authorization` header)
* **Headers**: `Content-Type: application/json`

### JSON Request Payload:
- `height` (required, `number`): User's height in centimeters (50 to 250).
- `weight` (required, `number`): User's weight in kilograms (20 to 250).
- `sideImage` (optional, `string`): Base64 data URI of the side-profile body photo.
- `save` (optional, `boolean`): Whether to save the calculated measurements to the database. Defaults to `false`. Can also be sent as query parameter `?save=true`.

```json
{
  "height": 175.0,
  "weight": 70.0,
  "save": false
}
```

### Response:
Matches the structure of the standard `POST /api/body-measurements/estimate` response, including the `measurements` dictionary, the `confidence` score, and the generated pose and silhouette overlays (`frontOverlay` and `sideOverlay`).

### Avatar Specific Error Handling:
If the user does not have an avatar uploaded yet, the endpoint returns a `400 Bad Request`:
```json
{
  "success": false,
  "error": "No avatar image found. Please upload/save an avatar first.",
  "error_code": "VALIDATION_ERROR"
}
```
If you receive this response, you should redirect the user to the avatar upload/onboarding screen.

