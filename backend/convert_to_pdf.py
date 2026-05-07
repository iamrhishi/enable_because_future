#!/usr/bin/env python
"""
Convert FITTING_API.md to PDF using pandoc
"""

import subprocess
import os
import sys

def convert_md_to_pdf():
    """Convert markdown to PDF using pandoc and system utilities"""
    
    md_file = "FITTING_API.md"
    pdf_file = "FITTING_API.pdf"
    html_file = "/tmp/FITTING_API.html"
    
    # Check if markdown file exists
    if not os.path.exists(md_file):
        print(f"Error: {md_file} not found")
        return False
    
    print(f"Converting {md_file} to PDF...")
    
    # Try using pandoc with HTML intermediate
    try:
        # Step 1: Convert markdown to HTML
        cmd_md_to_html = f"pandoc {md_file} -o {html_file} -t html --metadata title='Fitting Analysis API Documentation'"
        result = subprocess.run(cmd_md_to_html, shell=True, capture_output=True, text=True)
        
        if result.returncode != 0:
            print(f"Error converting markdown to HTML: {result.stderr}")
            return False
        
        print(f"✓ Generated HTML: {html_file}")
        
        # Step 2: Try using pdfkit (requires wkhtmltopdf)
        try:
            import pdfkit
            options = {
                'page-size': 'A4',
                'margin-top': '0.75in',
                'margin-right': '0.75in',
                'margin-bottom': '0.75in',
                'margin-left': '0.75in',
                'encoding': "UTF-8",
                'no-outline': None,
                'enable-local-file-access': None,
            }
            
            pdfkit.from_file(html_file, pdf_file, options=options)
            print(f"✓ PDF created: {pdf_file}")
            
            # Clean up HTML temp file
            if os.path.exists(html_file):
                os.remove(html_file)
            
            return True
        except Exception as e:
            print(f"pdfkit not available: {e}")
            print("Trying alternative approach...")
        
        # Step 3: If pdfkit fails, try using reportlab with markdown parsing
        try:
            from reportlab.lib.pagesizes import letter, A4
            from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
            from reportlab.lib.units import inch
            from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, PageBreak, Table, TableStyle
            from reportlab.lib import colors
            from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_JUSTIFY
            import markdown
            from html.parser import HTMLParser
            
            # Read HTML file
            with open(html_file, 'r', encoding='utf-8') as f:
                html_content = f.read()
            
            # Create PDF document
            doc = SimpleDocTemplate(pdf_file, pagesize=A4, topMargin=0.75*inch, bottomMargin=0.75*inch)
            story = []
            styles = getSampleStyleSheet()
            
            # Add title
            title_style = ParagraphStyle(
                'CustomTitle',
                parent=styles['Heading1'],
                fontSize=24,
                textColor=colors.HexColor('#1f2937'),
                spaceAfter=30,
                alignment=TA_CENTER,
                fontName='Helvetica-Bold'
            )
            story.append(Paragraph("Fitting Analysis API Documentation", title_style))
            story.append(Spacer(1, 0.2*inch))
            
            # Add meta information
            meta_style = ParagraphStyle(
                'Meta',
                parent=styles['Normal'],
                fontSize=9,
                textColor=colors.grey,
                alignment=TA_CENTER
            )
            story.append(Paragraph("Version 1.0 | April 2026", meta_style))
            story.append(Spacer(1, 0.2*inch))
            
            # Parse HTML and convert to reportlab elements
            lines = html_content.split('\n')
            for line in lines:
                line = line.strip()
                if not line:
                    continue
                
                # Handle headings
                if line.startswith('<h1'):
                    text = line.replace('<h1>', '').replace('</h1>', '').strip()
                    story.append(Spacer(1, 0.2*inch))
                    story.append(Paragraph(text, styles['Heading1']))
                    story.append(Spacer(1, 0.1*inch))
                elif line.startswith('<h2'):
                    text = line.replace('<h2>', '').replace('</h2>', '').strip()
                    story.append(Spacer(1, 0.15*inch))
                    story.append(Paragraph(text, styles['Heading2']))
                    story.append(Spacer(1, 0.08*inch))
                elif line.startswith('<h3'):
                    text = line.replace('<h3>', '').replace('</h3>', '').strip()
                    story.append(Paragraph(text, styles['Heading3']))
                    story.append(Spacer(1, 0.05*inch))
                elif line.startswith('<p'):
                    text = line.replace('<p>', '').replace('</p>', '').strip()
                    if text:
                        story.append(Paragraph(text, styles['BodyText']))
                        story.append(Spacer(1, 0.08*inch))
                elif line.startswith('<li'):
                    text = line.replace('<li>', '').replace('</li>', '').strip()
                    if text:
                        bullet_style = ParagraphStyle(
                            'BulletStyle',
                            parent=styles['Normal'],
                            leftIndent=20,
                            bulletIndent=10,
                        )
                        from reportlab.platypus import Paragraph as P
                        story.append(Paragraph(f"• {text}", bullet_style))
                        story.append(Spacer(1, 0.04*inch))
            
            # Build PDF
            doc.build(story)
            print(f"✓ PDF created using reportlab: {pdf_file}")
            
            # Clean up HTML temp file
            if os.path.exists(html_file):
                os.remove(html_file)
            
            return True
            
        except Exception as e:
            print(f"reportlab conversion failed: {e}")
    
    except Exception as e:
        print(f"Error: {e}")
        return False
    
    return False

if __name__ == "__main__":
    success = convert_md_to_pdf()
    sys.exit(0 if success else 1)
