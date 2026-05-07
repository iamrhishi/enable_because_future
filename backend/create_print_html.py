#!/usr/bin/env python
"""
Generate PDF documents from markdown files using HTML + CSS + print-like rendering
Creates proper PDF documents with styling
"""

import os

def create_styled_html_to_print(md_file, html_output):
    """Convert markdown to styled HTML ready for printing to PDF"""
    
    import markdown
    
    with open(md_file, 'r', encoding='utf-8') as f:
        md_content = f.read()
    
    # Convert markdown to HTML
    html_body = markdown.markdown(md_content, extensions=['tables', 'fenced_code', 'extra'])
    
    # Create complete HTML document with print-friendly styling
    html_doc = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>API Documentation</title>
    <style>
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}
        
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'Roboto', 'Oxygen', 'Ubuntu', 'Cantarell', sans-serif;
            line-height: 1.6;
            color: #1f2937;
            background: white;
            padding: 40px 20px;
        }}
        
        @media print {{
            body {{
                padding: 0;
                background: white;
            }}
            .page-break {{
                page-break-after: always;
            }}
        }}
        
        h1 {{
            font-size: 28px;
            font-weight: 700;
            margin: 30px 0 20px 0;
            color: #1f2937;
            border-bottom: 3px solid #3b82f6;
            padding-bottom: 10px;
        }}
        
        h2 {{
            font-size: 22px;
            font-weight: 600;
            margin: 25px 0 15px 0;
            color: #374151;
        }}
        
        h3 {{
            font-size: 16px;
            font-weight: 600;
            margin: 18px 0 12px 0;
            color: #4b5563;
        }}
        
        p {{
            margin-bottom: 12px;
            text-align: justify;
        }}
        
        ul, ol {{
            margin: 15px 0 15px 30px;
        }}
        
        li {{
            margin-bottom: 8px;
        }}
        
        code {{
            background: #f3f4f6;
            padding: 2px 6px;
            border-radius: 3px;
            font-family: 'Courier New', monospace;
            font-size: 13px;
        }}
        
        pre {{
            background: #f3f4f6;
            border-left: 4px solid #3b82f6;
            padding: 15px;
            margin: 15px 0;
            overflow-x: auto;
            border-radius: 4px;
        }}
        
        pre code {{
            background: none;
            padding: 0;
            font-size: 11px;
            line-height: 1.5;
        }}
        
        table {{
            width: 100%;
            border-collapse: collapse;
            margin: 20px 0;
            font-size: 13px;
        }}
        
        th, td {{
            border: 1px solid #e5e7eb;
            padding: 10px 12px;
            text-align: left;
        }}
        
        th {{
            background: #f3f4f6;
            font-weight: 600;
            color: #1f2937;
        }}
        
        tr:nth-child(even) {{
            background: #f9fafb;
        }}
        
        tr:hover {{
            background: #f3f4f6;
        }}
        
        blockquote {{
            border-left: 4px solid #3b82f6;
            padding-left: 16px;
            margin: 15px 0;
            color: #4b5563;
            font-style: italic;
        }}
        
        hr {{
            border: none;
            border-top: 2px solid #e5e7eb;
            margin: 30px 0;
        }}
        
        .warning {{
            background: #fef3c7;
            border-left: 4px solid #f59e0b;
            padding: 12px 15px;
            margin: 15px 0;
            border-radius: 3px;
        }}
        
        .success {{
            background: #dcfce7;
            border-left: 4px solid #22c55e;
            padding: 12px 15px;
            margin: 15px 0;
            border-radius: 3px;
        }}
        
        .info {{
            background: #dbeafe;
            border-left: 4px solid #3b82f6;
            padding: 12px 15px;
            margin: 15px 0;
            border-radius: 3px;
        }}
        
        em {{
            font-style: italic;
        }}
        
        strong {{
            font-weight: 600;
        }}
        
        @media print {{
            a {{
                color: #1f2937;
                text-decoration: none;
            }}
            pre {{
                page-break-inside: avoid;
            }}
            h1, h2, h3 {{
                page-break-after: avoid;
            }}
            table {{
                page-break-inside: avoid;
            }}
        }}
    </style>
</head>
<body>
{html_body}
<footer style="margin-top: 60px; padding-top: 20px; border-top: 1px solid #e5e7eb; text-align: center; color: #6b7280; font-size: 11px;">
    <p>Generated on April 17, 2026 | API Documentation for Because Future</p>
</footer>
</body>
</html>"""
    
    with open(html_output, 'w', encoding='utf-8') as f:
        f.write(html_doc)
    
    return True

# Convert both files
files_to_convert = [
    ('FITTING_API.md', 'FITTING_API_print.html'),
    ('API_INTEGRATION_GUIDE.md', 'API_INTEGRATION_GUIDE_print.html')
]

for md_file, html_file in files_to_convert:
    if os.path.exists(md_file):
        try:
            create_styled_html_to_print(md_file, html_file)
            file_size = os.path.getsize(html_file) / 1024
            print(f"✓ Created {html_file} ({file_size:.1f} KB)")
        except Exception as e:
            print(f"✗ Error creating {html_file}: {e}")
    else:
        print(f"⚠ File not found: {md_file}")

print("\n✅ HTML documents created - Open in browser and print to PDF (Cmd+P or Ctrl+P)")
