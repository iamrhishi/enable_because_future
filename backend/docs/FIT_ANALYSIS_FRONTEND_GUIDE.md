# Fit Analysis - Frontend Integration Guide

**Project:** BecauseFuture
**Version:** 1.0
**Last Updated:** April 17, 2026

---

## Table of Contents

1. [Overview](#overview)
2. [Screen-by-Screen API Integration](#screen-by-screen-api-integration)
3. [API Reference](#api-reference)
4. [Measurement Mappings](#measurement-mappings)
5. [Fit Classification Logic](#fit-classification-logic)
6. [UI Implementation Guide](#ui-implementation-guide)
7. [Color Coding Reference](#color-coding-reference)
8. [Example API Flows](#example-api-flows)

---

## Overview

The Fit Analysis feature allows users to see how well a garment fits their body measurements before purchasing. The system uses a 4-tier classification:

| Classification | Difference | Color | Meaning |
|----------------|------------|-------|---------|
| **Body Fit** | < 0.1 cm | Green | Perfect match |
| **Good Fit** | 0.1 - 1.9 cm | Light Green | Comfortable fit |
| **Loose Fit** | 2.0 - 3.9 cm | Orange/Yellow | Slightly oversized |
| **Tight** | ≥ 4.0 cm (body > garment) | Red | Too small |

---

## Screen-by-Screen API Integration

### Screen 1: Home / Try-On View

**Purpose:** Main screen showing avatar with tried-on garment

**UI Elements:**
- User avatar with garment overlay
- "Fit Info" button (top right)
- Two "+" buttons for adding upper/lower garments

**APIs Required:**

| Action | API Endpoint | Auth | When to Call |
|--------|--------------|------|--------------|
| Load user avatar | `GET /api/avatar/{userid}` | JWT | On screen load |
| Get try-on result | `GET /api/job/{job_id}/result` | JWT | After try-on completes |
| Check if measurements exist | `GET /api/body-measurements` | JWT | On screen load (to enable/disable Fit Info) |

**Logic:**
```javascript
// On screen load
const hasMeasurements = await checkBodyMeasurements();
setFitInfoButtonEnabled(hasMeasurements);

// On "Fit Info" tap
if (hasMeasurements && currentGarmentUrl) {
    navigateToFitAnalysisScreen(currentGarmentUrl);
} else {
    showPrompt("Please add your body measurements first");
}
```

---

### Screen 2: Fit Analysis Screen

**Purpose:** Shows detailed fit analysis with body silhouette and color-coded measurements

**UI Elements:**
- Body silhouette with measurement lines
- "Your Size" panel (left) - recommended size
- "This Size" panel (right) - currently selected size with navigation arrows
- Color-coded measurement indicators on body
- Garment name and brand at bottom

**APIs Required (call in sequence):**

| Step | API Endpoint | Auth | Purpose |
|------|--------------|------|---------|
| 1 | `GET /api/body-measurements` | JWT | Get user's body measurements |
| 2 | `GET /api/sizing/garment?url={product_url}` | No | Get garment measurements from brand |
| 3 | `POST /api/fit-analysis` | JWT | Analyze fit for each size |

**Complete Flow:**

```javascript
async function loadFitAnalysis(garmentUrl) {
    // Step 1: Get user body measurements
    const bodyMeasurements = await fetch('/api/body-measurements', {
        headers: { 'Authorization': `Bearer ${jwtToken}` }
    }).then(r => r.json());

    // Step 2: Get garment data from brand portal
    const garmentData = await fetch(`/api/sizing/garment?url=${encodeURIComponent(garmentUrl)}`)
        .then(r => r.json());

    // garmentData.measurements_by_size = { "S": {...}, "M": {...}, "L": {...} }

    // Step 3: Analyze fit for each available size
    const fitResults = {};
    for (const [size, measurements] of Object.entries(garmentData.measurements_by_size)) {
        const analysis = await fetch('/api/fit-analysis', {
            method: 'POST',
            headers: {
                'Authorization': `Bearer ${jwtToken}`,
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                garment_type: garmentData.category === 'top' ? 'upper' : 'lower',
                garment_size: size,
                garment_measurements: measurements
            })
        }).then(r => r.json());

        fitResults[size] = analysis;
    }

    // Step 4: Find best fitting size (highest accuracy)
    const recommendedSize = findBestSize(fitResults);

    // Step 5: Render UI
    renderFitAnalysisUI(fitResults, recommendedSize, garmentData);
}

function findBestSize(fitResults) {
    let bestSize = null;
    let bestAccuracy = 0;

    for (const [size, result] of Object.entries(fitResults)) {
        const total = result.body_fit_count + result.good_fits +
                      result.loose_fit_count + result.tight_count;
        const accuracy = ((result.body_fit_count + result.good_fits) / total) * 100;

        if (accuracy > bestAccuracy) {
            bestAccuracy = accuracy;
            bestSize = size;
        }
    }

    return { size: bestSize, accuracy: bestAccuracy };
}
```

---

### Screen 3: Body Measurements Input

**Purpose:** User enters their body measurements

**UI Elements:**
- Input fields for each measurement
- Unit toggle (metric/imperial)
- Save button

**APIs Required:**

| Action | API Endpoint | Method | Auth |
|--------|--------------|--------|------|
| Load existing | `GET /api/body-measurements` | GET | JWT |
| Save new | `POST /api/body-measurements` | POST | JWT |
| Update existing | `PUT /api/body-measurements` | PUT | JWT |

**Measurement Fields with Validation:**

```javascript
const measurementFields = {
    // Basic
    height: { min: 50, max: 250, unit: 'cm', label: 'Height' },
    weight: { min: 20, max: 250, unit: 'kg', label: 'Weight' },

    // Upper Body
    shoulder_circumference: { min: 60, max: 200, unit: 'cm', label: 'Shoulder Circumference' },
    arm_length: { min: 25, max: 100, unit: 'cm', label: 'Arm Length' },
    biceps_circumference: { min: 10, max: 100, unit: 'cm', label: 'Biceps Circumference' },
    breast_circumference: { min: 50, max: 300, unit: 'cm', label: 'Breast/Chest Circumference' },
    under_breast_circumference: { min: 40, max: 300, unit: 'cm', label: 'Under Breast Circumference' },
    collarbone_to_belly_button_length: { min: 30, max: 150, unit: 'cm', label: 'Collarbone to Belly Button' },

    // Lower Body
    waist_circumference: { min: 30, max: 300, unit: 'cm', label: 'Waist Circumference' },
    hip_circumference: { min: 50, max: 300, unit: 'cm', label: 'Hip Circumference' },
    upper_thigh_circumference: { min: 25, max: 300, unit: 'cm', label: 'Upper Thigh Circumference' },
    waist_to_crotch_front_length: { min: 15, max: 100, unit: 'cm', label: 'Waist to Crotch (Front)' },
    waist_to_crotch_back_length: { min: 15, max: 100, unit: 'cm', label: 'Waist to Crotch (Back)' },
    inner_leg_length: { min: 50, max: 200, unit: 'cm', label: 'Inner Leg Length' },
    foot_length: { min: 10, max: 60, unit: 'cm', label: 'Foot Length' },
    foot_width: { min: 5, max: 20, unit: 'cm', label: 'Foot Width' }
};
```

---

## API Reference

### 1. Get Body Measurements

```
GET /api/body-measurements
Authorization: Bearer {jwt_token}
```

**Response:**
```json
{
    "success": true,
    "data": {
        "height": 170,
        "weight": 65,
        "breast_circumference": 95,
        "waist_circumference": 80,
        "hip_circumference": 100,
        "arm_length": 60,
        "inner_leg_length": 75,
        ...
    }
}
```

---

### 2. Get Garment Data (from Brand Portal)

```
GET /api/sizing/garment?url={product_url}
```

**Response:**
```json
{
    "success": true,
    "data": {
        "id": "691905ca-e414-4e7c-a321-106b5e118232",
        "name": "Blue Jeans Wide Leg High Rise",
        "category": "bottom",
        "subcategory": "Jeans",
        "fit_type": "wide",
        "material_stretch": "slight",
        "size_label": "34, 36, 38, 40",
        "brand_partners": {
            "brand_name": "Zara",
            "website": "https://zara.com"
        },
        "measurements_by_size": {
            "34": {
                "waist": 36,
                "hip": 48,
                "front_crotch": 26,
                "inner_leg_length": 78,
                "thigh": 30
            },
            "36": {
                "waist": 38,
                "hip": 50,
                "front_crotch": 27,
                "inner_leg_length": 78,
                "thigh": 31
            },
            "38": { ... },
            "40": { ... }
        }
    }
}
```

---

### 3. Analyze Fit

```
POST /api/fit-analysis
Authorization: Bearer {jwt_token}
Content-Type: application/json

{
    "garment_type": "lower",
    "garment_size": "36",
    "garment_measurements": {
        "waist": 38,
        "hip": 50,
        "front_crotch": 27,
        "inner_leg_length": 78,
        "thigh": 31
    }
}
```

**Response:**
```json
{
    "garment_type": "lower",
    "garment_size": "36",
    "overall_fit": "good fit",
    "body_fit_count": 1,
    "good_fits": 3,
    "loose_fit_count": 1,
    "tight_count": 0,
    "measurements": [
        {
            "metric": "waist",
            "body_value": 40,
            "garment_value": 38,
            "fit_status": "loose fit",
            "difference": 2.0
        },
        {
            "metric": "hip",
            "body_value": 50,
            "garment_value": 50,
            "fit_status": "body fit",
            "difference": 0.0
        },
        {
            "metric": "inner_leg_length",
            "body_value": 75,
            "garment_value": 78,
            "fit_status": "good fit",
            "difference": -3.0
        }
    ]
}
```

---

## Measurement Mappings

### How Body Measurements Map to Garment Measurements

The backend automatically transforms body measurements (circumferences) to compare with garment measurements (widths).

**Upper Garments (tops, shirts, jackets):**

| Garment Field | Body Measurement | Transform |
|---------------|------------------|-----------|
| `breast_width` | `breast_circumference` | ÷ 2 |
| `front_length` | `collarbone_to_belly_button_length` | direct |
| `arm_length` | `arm_length` | direct |
| `arm_width` | `biceps_circumference` | ÷ 2 |
| `shoulder_width` | `shoulder_circumference` | ÷ 2 |

**Lower Garments (pants, jeans, skirts):**

| Garment Field | Body Measurement | Transform |
|---------------|------------------|-----------|
| `waist` | `waist_circumference` | ÷ 2 |
| `hip` | `hip_circumference` | ÷ 2 |
| `front_crotch` | `waist_to_crotch_front_length` | direct |
| `inner_leg_length` | `inner_leg_length` | direct |
| `thigh` | `upper_thigh_circumference` | ÷ 2 |

---

## Fit Classification Logic

```
ALGORITHM: ClassifyMeasurementFit(body_value, garment_value)

1. difference = body_value - garment_value
2. abs_difference = ABS(difference)

3. IF abs_difference < 0.1 THEN
       RETURN "body fit"      // Perfect match
   ELSE IF abs_difference < 2 THEN
       RETURN "good fit"      // Comfortable
   ELSE IF abs_difference < 4 THEN
       RETURN "loose fit"     // Slightly loose
   ELSE IF difference > 0 THEN
       RETURN "tight"         // Body bigger = too tight
   ELSE
       RETURN "loose fit"     // Body smaller = too loose
```

**Overall Fit Determination:**
1. If ANY measurement is "tight" → overall = "tight"
2. If all measurements are "loose fit" → overall = "loose fit"
3. If all measurements are "body fit" → overall = "body fit"
4. Otherwise → overall = "good fit"

---

## UI Implementation Guide

### Body Silhouette Visualization

Use the transparent body outline image and overlay colored lines at measurement points:

```javascript
const measurementPositions = {
    // Lower body (for pants/jeans)
    waist: { y: '35%', label: 'High Waist' },
    hip: { y: '42%', label: 'Hip' },
    inner_leg_length: { y: '70%', label: 'Ankle Length', orientation: 'vertical' },

    // Upper body (for tops)
    breast_width: { y: '28%', label: 'Chest' },
    front_length: { y: '35%', label: 'Length', orientation: 'vertical' },
    arm_length: { y: '30%', label: 'Sleeve', orientation: 'diagonal' }
};

function renderMeasurementLine(measurement, fitStatus) {
    const colors = {
        'body fit': '#22c55e',    // Green
        'good fit': '#84cc16',    // Light green
        'loose fit': '#f97316',   // Orange
        'tight': '#ef4444'        // Red
    };

    return {
        color: colors[fitStatus],
        position: measurementPositions[measurement.metric],
        label: measurement.metric.replace(/_/g, ' ').toUpperCase()
    };
}
```

### Size Selector Component

```javascript
function SizeSelector({ sizes, currentSize, onSizeChange, fitResults }) {
    return (
        <div className="size-selector">
            <button onClick={() => onSizeChange(getPrevSize())}>←</button>
            <div className="current-size">
                <span className="size-label">This size:</span>
                <span className="size-value">{currentSize}</span>
                <span className="accuracy">{fitResults[currentSize].accuracy}%</span>
                <span className="fit-type">{fitResults[currentSize].overall_fit}</span>
            </div>
            <button onClick={() => onSizeChange(getNextSize())}>→</button>
        </div>
    );
}
```

### Accuracy Calculation

```javascript
function calculateAccuracy(fitResult) {
    const total = fitResult.body_fit_count +
                  fitResult.good_fits +
                  fitResult.loose_fit_count +
                  fitResult.tight_count;

    if (total === 0) return 0;

    // Good fits = body_fit + good_fit (acceptable fits)
    const goodFits = fitResult.body_fit_count + fitResult.good_fits;

    return Math.round((goodFits / total) * 100);
}
```

---

## Color Coding Reference

### CSS Variables

```css
:root {
    --fit-body: #22c55e;      /* Green - Perfect match */
    --fit-good: #84cc16;      /* Light Green - Comfortable */
    --fit-loose: #f97316;     /* Orange - Slightly loose */
    --fit-tight: #ef4444;     /* Red - Too tight */
    --fit-text-body: #166534;
    --fit-text-good: #365314;
    --fit-text-loose: #9a3412;
    --fit-text-tight: #991b1b;
}
```

### Fit Status Labels

```javascript
const fitLabels = {
    'body fit': 'Perfect Fit',
    'good fit': 'Good Fit',
    'loose fit': 'Loose',
    'tight': 'Very Tight'
};

const fitDescriptions = {
    'body fit': 'Exactly matches your measurements',
    'good fit': 'Comfortable fit with slight room',
    'loose fit': 'Loose fit, more room for movement',
    'tight': 'Too small, not recommended'
};
```

---

## Example API Flows

### Complete Fit Analysis Flow

```
User taps "Fit Info" on try-on screen
    │
    ▼
┌─────────────────────────────────────────┐
│ GET /api/body-measurements              │
│ Response: user's body measurements      │
└─────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────┐
│ GET /api/sizing/garment?url={url}       │
│ Response: garment with measurements_by_size │
└─────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────┐
│ FOR EACH size in measurements_by_size:  │
│   POST /api/fit-analysis                │
│   Body: { garment_type, garment_size,   │
│           garment_measurements }        │
└─────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────┐
│ Calculate best size (highest accuracy)  │
│ Render UI with:                         │
│   - Recommended size (left panel)       │
│   - Current size (right panel)          │
│   - Body silhouette with colored lines  │
│   - Garment name and brand              │
└─────────────────────────────────────────┘
```

---

## Postman Collection Endpoints

| Folder | Endpoint | Method | Auth |
|--------|----------|--------|------|
| Body Measurements | `/api/body-measurements` | GET | JWT |
| Body Measurements | `/api/body-measurements` | POST | JWT |
| Body Measurements | `/api/body-measurements` | PUT | JWT |
| Sizing [NEW v2] | `/api/sizing/garment` | GET | No |
| Sizing [NEW v2] | `/api/sizing/recommend` | POST | JWT |
| Fit Analysis [NEW] | `/api/fit-analysis` | POST | JWT |

---

## Assets Required

1. **Body Silhouette Image** - `Avatar transparenter Hintergrund 2.png`
   - Transparent PNG with body outline
   - Used as base for overlaying measurement lines

2. **Measurement Icons** (optional)
   - Waist icon
   - Hip icon
   - Length icon

3. **Color Legend** (optional)
   - Small color swatches with labels

---

## Error Handling

```javascript
async function handleFitAnalysis(garmentUrl) {
    try {
        // Check if user has body measurements
        const measurements = await getBodyMeasurements();
        if (!measurements) {
            showError("Please add your body measurements in Profile > Measurements");
            return;
        }

        // Get garment data
        const garment = await getGarmentData(garmentUrl);
        if (!garment) {
            showError("Garment sizing data not available for this product");
            return;
        }

        // Analyze fit
        const fitResults = await analyzeFit(garment, measurements);
        renderFitUI(fitResults);

    } catch (error) {
        if (error.status === 401) {
            redirectToLogin();
        } else if (error.status === 404) {
            showError("Sizing information not available");
        } else {
            showError("Unable to load fit analysis. Please try again.");
        }
    }
}
```

---

## Summary

| Screen | Primary API | Secondary APIs |
|--------|-------------|----------------|
| Home/Try-On | `GET /api/job/{id}/result` | `GET /api/body-measurements` |
| Fit Analysis | `POST /api/fit-analysis` | `GET /api/body-measurements`, `GET /api/sizing/garment` |
| Measurements | `POST /api/body-measurements` | `GET /api/body-measurements` |

**Key Points:**
1. Always check if user has body measurements before showing Fit Info
2. Call fit-analysis for EACH size to enable size comparison
3. Use color coding consistently across the app
4. Display accuracy percentage based on (body_fit + good_fits) / total

---

*Document generated: April 17, 2026*
