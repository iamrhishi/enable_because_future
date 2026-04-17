#!/usr/bin/env python3
"""Generate Fit Analysis Frontend Guide PDF using reportlab"""

from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch, cm
from reportlab.lib.colors import HexColor, black, white
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak
from reportlab.lib.enums import TA_LEFT, TA_CENTER

# Colors
GREEN = HexColor('#22c55e')
LIGHT_GREEN = HexColor('#84cc16')
ORANGE = HexColor('#f97316')
RED = HexColor('#ef4444')
DARK_GRAY = HexColor('#374151')
LIGHT_GRAY = HexColor('#f3f4f6')
HEADER_BG = HexColor('#1f2937')

def create_pdf():
    doc = SimpleDocTemplate(
        "FIT_ANALYSIS_GUIDE.pdf",
        pagesize=A4,
        rightMargin=1.5*cm,
        leftMargin=1.5*cm,
        topMargin=1.5*cm,
        bottomMargin=1.5*cm
    )

    styles = getSampleStyleSheet()

    # Custom styles
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=24,
        spaceAfter=20,
        textColor=DARK_GRAY
    )

    h2_style = ParagraphStyle(
        'CustomH2',
        parent=styles['Heading2'],
        fontSize=14,
        spaceBefore=15,
        spaceAfter=10,
        textColor=DARK_GRAY
    )

    h3_style = ParagraphStyle(
        'CustomH3',
        parent=styles['Heading3'],
        fontSize=11,
        spaceBefore=10,
        spaceAfter=5,
        textColor=DARK_GRAY
    )

    body_style = ParagraphStyle(
        'CustomBody',
        parent=styles['Normal'],
        fontSize=9,
        spaceAfter=8,
        leading=12
    )

    code_style = ParagraphStyle(
        'Code',
        parent=styles['Normal'],
        fontSize=8,
        fontName='Courier',
        backColor=LIGHT_GRAY,
        leftIndent=10,
        spaceAfter=8
    )

    story = []

    # Title
    story.append(Paragraph("Fit Analysis - Frontend Integration Guide", title_style))
    story.append(Paragraph("BecauseFuture | April 2026", body_style))
    story.append(Spacer(1, 20))

    # Section 1: Fit Classification
    story.append(Paragraph("1. Fit Classification System", h2_style))

    fit_data = [
        ['Status', 'Difference', 'Color', 'Meaning'],
        ['Body Fit', '< 0.1 cm', 'Green', 'Perfect match'],
        ['Good Fit', '0.1 - 1.9 cm', 'Light Green', 'Comfortable'],
        ['Loose Fit', '2.0 - 3.9 cm', 'Orange', 'Slightly oversized'],
        ['Tight', '>= 4.0 cm', 'Red', 'Too small'],
    ]

    fit_table = Table(fit_data, colWidths=[2.5*cm, 3*cm, 2.5*cm, 4*cm])
    fit_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), HEADER_BG),
        ('TEXTCOLOR', (0, 0), (-1, 0), white),
        ('FONTSIZE', (0, 0), (-1, -1), 8),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('GRID', (0, 0), (-1, -1), 0.5, DARK_GRAY),
        ('BACKGROUND', (0, 1), (-1, 1), HexColor('#dcfce7')),
        ('BACKGROUND', (0, 2), (-1, 2), HexColor('#ecfccb')),
        ('BACKGROUND', (0, 3), (-1, 3), HexColor('#ffedd5')),
        ('BACKGROUND', (0, 4), (-1, 4), HexColor('#fee2e2')),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (0, 0), (-1, -1), 5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
    ]))
    story.append(fit_table)
    story.append(Spacer(1, 15))

    # Section 2: Screen API Mapping
    story.append(Paragraph("2. Screen → API Mapping", h2_style))

    screen_data = [
        ['Screen', 'APIs to Call', 'Auth'],
        ['Home / Try-On', 'GET /api/body-measurements (check exists)', 'JWT'],
        ['Fit Analysis', '1. GET /api/body-measurements\n2. GET /api/sizing/garment?url=...\n3. POST /api/fit-analysis (each size)', 'JWT\nNo\nJWT'],
        ['Measurements', 'POST /api/body-measurements', 'JWT'],
    ]

    screen_table = Table(screen_data, colWidths=[3*cm, 9*cm, 2*cm])
    screen_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), HEADER_BG),
        ('TEXTCOLOR', (0, 0), (-1, 0), white),
        ('FONTSIZE', (0, 0), (-1, -1), 8),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('GRID', (0, 0), (-1, -1), 0.5, DARK_GRAY),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('TOPPADDING', (0, 0), (-1, -1), 5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
    ]))
    story.append(screen_table)
    story.append(Spacer(1, 15))

    # Section 3: API Reference
    story.append(Paragraph("3. API Reference", h2_style))

    story.append(Paragraph("3.1 Get Body Measurements", h3_style))
    story.append(Paragraph("GET /api/body-measurements | Auth: JWT", code_style))

    story.append(Paragraph("3.2 Get Garment Data (Brand Portal)", h3_style))
    story.append(Paragraph("GET /api/sizing/garment?url={product_url} | Auth: None", code_style))
    story.append(Paragraph("Returns: measurements_by_size object with sizes as keys (S, M, L, XL...)", body_style))

    story.append(Paragraph("3.3 Analyze Fit", h3_style))
    story.append(Paragraph("POST /api/fit-analysis | Auth: JWT", code_style))
    story.append(Paragraph('Body: { "garment_type": "upper|lower", "garment_size": "M", "garment_measurements": {...} }', code_style))
    story.append(Spacer(1, 10))

    # Section 4: Measurement Mappings
    story.append(Paragraph("4. Measurement Mappings", h2_style))

    story.append(Paragraph("Upper Garments (tops, shirts):", h3_style))
    upper_data = [
        ['Garment Field', 'Body Measurement', 'Transform'],
        ['breast_width', 'breast_circumference', '÷ 2'],
        ['front_length', 'collarbone_to_belly_button_length', 'direct'],
        ['arm_length', 'arm_length', 'direct'],
        ['arm_width', 'biceps_circumference', '÷ 2'],
    ]
    upper_table = Table(upper_data, colWidths=[3.5*cm, 6*cm, 2*cm])
    upper_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), HEADER_BG),
        ('TEXTCOLOR', (0, 0), (-1, 0), white),
        ('FONTSIZE', (0, 0), (-1, -1), 8),
        ('GRID', (0, 0), (-1, -1), 0.5, DARK_GRAY),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
    ]))
    story.append(upper_table)
    story.append(Spacer(1, 10))

    story.append(Paragraph("Lower Garments (pants, jeans):", h3_style))
    lower_data = [
        ['Garment Field', 'Body Measurement', 'Transform'],
        ['waist', 'waist_circumference', '÷ 2'],
        ['hip', 'hip_circumference', '÷ 2'],
        ['front_crotch', 'waist_to_crotch_front_length', 'direct'],
        ['inner_leg_length', 'inner_leg_length', 'direct'],
        ['thigh', 'upper_thigh_circumference', '÷ 2'],
    ]
    lower_table = Table(lower_data, colWidths=[3.5*cm, 6*cm, 2*cm])
    lower_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), HEADER_BG),
        ('TEXTCOLOR', (0, 0), (-1, 0), white),
        ('FONTSIZE', (0, 0), (-1, -1), 8),
        ('GRID', (0, 0), (-1, -1), 0.5, DARK_GRAY),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
    ]))
    story.append(lower_table)
    story.append(Spacer(1, 15))

    # Section 5: UI Data Mapping
    story.append(Paragraph("5. UI Elements → Response Data", h2_style))

    ui_data = [
        ['UI Element', 'Data Source'],
        ['"Your Size: 38"', 'Size with highest accuracy'],
        ['"Accuracy: 80%"', '(body_fit_count + good_fits) / total × 100'],
        ['Colored lines on body', 'measurements[].fit_status → color'],
        ['Size arrows (< 36 >)', 'garment.measurements_by_size keys'],
        ['Garment name', 'garment.name'],
        ['Brand', 'garment.brand_partners.brand_name'],
    ]

    ui_table = Table(ui_data, colWidths=[4*cm, 10*cm])
    ui_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), HEADER_BG),
        ('TEXTCOLOR', (0, 0), (-1, 0), white),
        ('FONTSIZE', (0, 0), (-1, -1), 8),
        ('GRID', (0, 0), (-1, -1), 0.5, DARK_GRAY),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
    ]))
    story.append(ui_table)
    story.append(Spacer(1, 15))

    # Section 6: Color CSS
    story.append(Paragraph("6. Color Coding (CSS)", h2_style))
    story.append(Paragraph(
        "--fit-body: #22c55e;  --fit-good: #84cc16;  --fit-loose: #f97316;  --fit-tight: #ef4444;",
        code_style
    ))
    story.append(Spacer(1, 15))

    # Section 7: Flow
    story.append(Paragraph("7. Complete API Flow", h2_style))
    flow_text = """
    1. User taps "Fit Info" button
    2. GET /api/body-measurements → user measurements
    3. GET /api/sizing/garment?url=... → garment with measurements_by_size
    4. FOR EACH size: POST /api/fit-analysis → fit result
    5. Find best size (highest accuracy)
    6. Render UI: body silhouette + colored lines + size panels
    """
    story.append(Paragraph(flow_text.replace('\n', '<br/>'), body_style))
    story.append(Spacer(1, 15))

    # Section 8: Accuracy Formula
    story.append(Paragraph("8. Accuracy Calculation", h2_style))
    story.append(Paragraph(
        "accuracy = (body_fit_count + good_fits) / (body_fit_count + good_fits + loose_fit_count + tight_count) × 100",
        code_style
    ))

    # Build PDF
    doc.build(story)
    print("PDF created: FIT_ANALYSIS_GUIDE.pdf")

if __name__ == '__main__':
    create_pdf()
