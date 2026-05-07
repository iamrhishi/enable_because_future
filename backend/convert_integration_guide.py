#!/usr/bin/env python
"""
Convert API Integration Guide to PDF
"""

import subprocess
import os
import sys

def convert_to_pdf(md_file, pdf_file):
    """Convert markdown to PDF"""
    
    if not os.path.exists(md_file):
        print(f"Error: {md_file} not found")
        return False
    
    print(f"Converting {md_file} to PDF...")
    
    # Convert markdown to HTML first
    html_file = f"/tmp/{os.path.basename(md_file).replace('.md', '.html')}"
    cmd_md_to_html = f"pandoc {md_file} -o {html_file} -t html --metadata title='API Integration Guide'"
    result = subprocess.run(cmd_md_to_html, shell=True, capture_output=True, text=True)
    
    if result.returncode != 0:
        print(f"Error converting markdown to HTML: {result.stderr}")
        return False
    
    print(f"✓ Generated HTML: {html_file}")
    
    # Try using reportlab with HTML parsing
    try:
        from reportlab.lib.pagesizes import letter, A4
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.units import inch
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, PageBreak, Table, TableStyle, Preformatted
        from reportlab.lib import colors
        from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_JUSTIFY
        import re
        
        # Read HTML file
        with open(html_file, 'r', encoding='utf-8') as f:
            html_content = f.read()
        
        # Create PDF document with smaller margins for code blocks
        doc = SimpleDocTemplate(pdf_file, pagesize=A4, topMargin=0.5*inch, bottomMargin=0.5*inch, leftMargin=0.4*inch, rightMargin=0.4*inch)
        story = []
        styles = getSampleStyleSheet()
        
        # Custom styles
        title_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Heading1'],
            fontSize=20,
            textColor=colors.HexColor('#1f2937'),
            spaceAfter=12,
            alignment=TA_CENTER,
            fontName='Helvetica-Bold'
        )
        
        heading2_style = ParagraphStyle(
            'CustomHeading2',
            parent=styles['Heading2'],
            fontSize=14,
            textColor=colors.HexColor('#374151'),
            spaceAfter=10,
            spaceBefore=10,
            fontName='Helvetica-Bold'
        )
        
        heading3_style = ParagraphStyle(
            'CustomHeading3',
            parent=styles['Heading3'],
            fontSize=12,
            textColor=colors.HexColor('#4b5563'),
            spaceAfter=8,
            spaceBefore=6,
            fontName='Helvetica-Bold'
        )
        
        code_style = ParagraphStyle(
            'Code',
            parent=styles['Normal'],
            fontName='Courier',
            fontSize=8,
            textColor=colors.HexColor('#374151'),
            leading=9,
            leftIndent=10,
            backColor=colors.HexColor('#f3f4f6')
        )
        
        # Parse HTML and build story
        lines = html_content.split('\n')
        page_count = 0
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
            
            # Handle titles
            if line.startswith('<h1'):
                title_text = line.replace('<h1>', '').replace('</h1>', '').replace('<em>', '').replace('</em>', '').strip()
                story.append(Paragraph(title_text, title_style))
                story.append(Spacer(1, 0.1*inch))
            
            # Handle h2 headings
            elif line.startswith('<h2'):
                heading_text = line.replace('<h2>', '').replace('</h2>', '').replace('<em>', '').replace('</em>', '').strip()
                story.append(Spacer(1, 0.08*inch))
                story.append(Paragraph(heading_text, heading2_style))
                story.append(Spacer(1, 0.06*inch))
            
            # Handle h3 headings
            elif line.startswith('<h3'):
                heading_text = line.replace('<h3>', '').replace('</h3>', '').replace('<em>', '').replace('</em>', '').strip()
                story.append(Paragraph(heading_text, heading3_style))
                story.append(Spacer(1, 0.04*inch))
            
            # Handle code blocks
            elif line.startswith('<pre'):
                code_content = line.replace('<pre><code>', '').replace('</code></pre>', '').replace('<code>', '').replace('</code>', '').strip()
                if code_content:
                    story.append(Paragraph(code_content, code_style))
                    story.append(Spacer(1, 0.06*inch))
            
            # Handle paragraphs
            elif line.startswith('<p'):
                para_text = line.replace('<p>', '').replace('</p>', '').replace('<strong>', '<b>').replace('</strong>', '</b>').replace('<em>', '<i>').replace('</em>', '</i>').strip()
                if para_text and not para_text.startswith('curl') and not para_text.startswith('{') and not para_text.startswith('['):
                    story.append(Paragraph(para_text, styles['BodyText']))
                    story.append(Spacer(1, 0.05*inch))
            
            # Handle list items
            elif line.startswith('<li'):
                list_text = line.replace('<li>', '').replace('</li>', '').replace('<strong>', '<b>').replace('</strong>', '</b>').replace('<em>', '<i>').replace('</em>', '</i>').strip()
                if list_text:
                    bullet_style = ParagraphStyle(
                        'BulletStyle',
                        parent=styles['Normal'],
                        leftIndent=20,
                        fontSize=10,
                    )
                    story.append(Paragraph(f"• {list_text}", bullet_style))
                    story.append(Spacer(1, 0.03*inch))
            
            # Handle table rows (simple)
            elif '<table>' in line or '<tr>' in line or '<td>' in line:
                # Skip complex table parsing for now
                pass
            
            # Page break after each major section
            if '---' in line or '<hr' in line:
                if len(story) > 50:
                    story.append(PageBreak())
                    page_count += 1
        
        # Build PDF
        doc.build(story)
        print(f"✓ PDF created: {pdf_file}")
        
        # Clean up
        if os.path.exists(html_file):
            os.remove(html_file)
        
        return True
        
    except Exception as e:
        print(f"PDF conversion error: {e}")
        return False

if __name__ == "__main__":
    md_file = "API_INTEGRATION_GUIDE.md"
    pdf_file = "API_INTEGRATION_GUIDE.pdf"
    
    success = convert_to_pdf(md_file, pdf_file)
    sys.exit(0 if success else 1)
