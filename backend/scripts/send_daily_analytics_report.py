#!/usr/bin/env python3
"""
Daily Analytics Report Script

Generates an XLSX report of yesterday's events, emails it to configured recipients,
then wipes the reported data.

Run via cron at 00:30 daily:
  30 0 * * * cd /path/to/backend && python scripts/send_daily_analytics_report.py

Environment variables:
  ANALYTICS_REPORT_EMAILS - Comma-separated list of recipient emails
  SMTP_HOST - SMTP server host (default: smtp.gmail.com)
  SMTP_PORT - SMTP server port (default: 587)
  SMTP_USER - SMTP username
  SMTP_PASSWORD - SMTP password (use app password for Gmail)
  SMTP_FROM - From email address
"""

import os
import sys
from datetime import datetime, timedelta
from io import BytesIO
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email.mime.text import MIMEText
from email import encoders

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from shared.analytics import get_events_since, get_daily_summary, delete_events_before
from shared.api_call_tracking import get_api_call_summary, delete_api_call_events_before
from shared.logger import logger


def generate_xlsx_report(events: list, summary: dict, api_call_summary: dict = None) -> bytes:
    """Generate XLSX report from events."""
    try:
        from openpyxl import Workbook
        from openpyxl.styles import Font, PatternFill, Alignment
    except ImportError:
        logger.error("openpyxl not installed. Run: pip install openpyxl")
        raise

    wb = Workbook()

    # ===== Summary Sheet =====
    ws_summary = wb.active
    ws_summary.title = "Summary"

    # Title
    ws_summary['A1'] = f"Analytics Report - {summary['date']}"
    ws_summary['A1'].font = Font(bold=True, size=14)
    ws_summary.merge_cells('A1:C1')

    ws_summary['A3'] = "Event Type"
    ws_summary['B3'] = "Count"
    ws_summary['A3'].font = Font(bold=True)
    ws_summary['B3'].font = Font(bold=True)

    row = 4
    for event_type, count in sorted(summary['by_type'].items(), key=lambda x: -x[1]):
        ws_summary[f'A{row}'] = event_type
        ws_summary[f'B{row}'] = count
        row += 1

    row += 1
    ws_summary[f'A{row}'] = "TOTAL"
    ws_summary[f'B{row}'] = summary['total_events']
    ws_summary[f'A{row}'].font = Font(bold=True)
    ws_summary[f'B{row}'].font = Font(bold=True)

    ws_summary.column_dimensions['A'].width = 25
    ws_summary.column_dimensions['B'].width = 12

    # ===== Events Detail Sheet =====
    ws_events = wb.create_sheet("Events")

    headers = ['Timestamp', 'Event Type', 'User ID', 'User Email', 'IP Address', 'User Agent', 'Metadata']
    header_fill = PatternFill(start_color="CCCCCC", end_color="CCCCCC", fill_type="solid")

    for col, header in enumerate(headers, 1):
        cell = ws_events.cell(row=1, column=col, value=header)
        cell.font = Font(bold=True)
        cell.fill = header_fill

    for row_idx, event in enumerate(events, 2):
        ws_events.cell(row=row_idx, column=1, value=event.get('created_at', ''))
        ws_events.cell(row=row_idx, column=2, value=event.get('event_type', ''))
        ws_events.cell(row=row_idx, column=3, value=event.get('user_id', ''))
        ws_events.cell(row=row_idx, column=4, value=event.get('user_email', ''))
        ws_events.cell(row=row_idx, column=5, value=event.get('ip_address', ''))
        ws_events.cell(row=row_idx, column=6, value=str(event.get('user_agent', ''))[:100])
        ws_events.cell(row=row_idx, column=7, value=str(event.get('metadata', '')))

    # Set column widths
    ws_events.column_dimensions['A'].width = 20
    ws_events.column_dimensions['B'].width = 20
    ws_events.column_dimensions['C'].width = 15
    ws_events.column_dimensions['D'].width = 30
    ws_events.column_dimensions['E'].width = 15
    ws_events.column_dimensions['F'].width = 40
    ws_events.column_dimensions['G'].width = 50

    # ===== API Calls Sheet (platform / website / unique users) =====
    if api_call_summary and api_call_summary.get('total_calls', 0) > 0:
        ws_api = wb.create_sheet("API Calls")

        ws_api['A1'] = f"API Call Breakdown - {api_call_summary['date']}"
        ws_api['A1'].font = Font(bold=True, size=14)
        ws_api.merge_cells('A1:B1')

        ws_api['A3'] = "Total API Calls"
        ws_api['B3'] = api_call_summary['total_calls']
        ws_api['A4'] = "Unique Users"
        ws_api['B4'] = api_call_summary['unique_users']
        ws_api['A3'].font = Font(bold=True)
        ws_api['A4'].font = Font(bold=True)

        row = 6
        ws_api[f'A{row}'] = "By Platform"
        ws_api[f'A{row}'].font = Font(bold=True)
        row += 1
        ws_api[f'A{row}'] = "Platform"
        ws_api[f'B{row}'] = "Calls"
        ws_api[f'A{row}'].font = Font(bold=True)
        ws_api[f'B{row}'].font = Font(bold=True)
        row += 1
        for platform, count in sorted(api_call_summary['by_platform'].items(), key=lambda x: -x[1]):
            ws_api[f'A{row}'] = platform
            ws_api[f'B{row}'] = count
            row += 1

        row += 1
        ws_api[f'A{row}'] = "By Website (web platform only)"
        ws_api[f'A{row}'].font = Font(bold=True)
        row += 1
        ws_api[f'A{row}'] = "Website"
        ws_api[f'B{row}'] = "Calls"
        ws_api[f'A{row}'].font = Font(bold=True)
        ws_api[f'B{row}'].font = Font(bold=True)
        row += 1
        for website, count in sorted(api_call_summary['by_website'].items(), key=lambda x: -x[1]):
            ws_api[f'A{row}'] = website
            ws_api[f'B{row}'] = count
            row += 1

        ws_api.column_dimensions['A'].width = 40
        ws_api.column_dimensions['B'].width = 12

    # ===== By Feature & Device Sheet =====
    if api_call_summary and api_call_summary.get('by_feature'):
        ws_feat = wb.create_sheet("By Feature & Device")

        ws_feat['A1'] = f"API Calls by Feature & Device - {api_call_summary['date']}"
        ws_feat['A1'].font = Font(bold=True, size=14)
        ws_feat.merge_cells('A1:D1')

        platforms = sorted({
            p for counts in api_call_summary['by_feature_and_platform'].values() for p in counts
        })
        headers = ['Feature'] + [p.title() for p in platforms] + ['Total']
        for col, h in enumerate(headers, 1):
            cell = ws_feat.cell(row=3, column=col, value=h)
            cell.font = Font(bold=True)
            cell.fill = header_fill

        row = 4
        for feature, total in sorted(api_call_summary['by_feature'].items(), key=lambda x: -x[1]):
            ws_feat.cell(row=row, column=1, value=feature)
            by_platform = api_call_summary['by_feature_and_platform'].get(feature, {})
            for col, platform in enumerate(platforms, 2):
                ws_feat.cell(row=row, column=col, value=by_platform.get(platform, 0))
            ws_feat.cell(row=row, column=len(platforms) + 2, value=total)
            row += 1

        ws_feat.column_dimensions['A'].width = 22
        for i in range(2, len(platforms) + 3):
            ws_feat.column_dimensions[ws_feat.cell(row=3, column=i).column_letter].width = 12

    # ===== By Feature & User Sheet =====
    if api_call_summary and api_call_summary.get('by_feature_and_user'):
        ws_fu = wb.create_sheet("By Feature & User")

        ws_fu['A1'] = f"API Calls by Feature & User - {api_call_summary['date']}"
        ws_fu['A1'].font = Font(bold=True, size=14)
        ws_fu.merge_cells('A1:C1')

        headers = ['Feature', 'User', 'Calls']
        for col, h in enumerate(headers, 1):
            cell = ws_fu.cell(row=3, column=col, value=h)
            cell.font = Font(bold=True)
            cell.fill = header_fill

        row = 4
        for feature, _ in sorted(api_call_summary['by_feature'].items(), key=lambda x: -x[1]):
            by_user = api_call_summary['by_feature_and_user'].get(feature, {})
            for user, count in sorted(by_user.items(), key=lambda x: -x[1]):
                ws_fu.cell(row=row, column=1, value=feature)
                ws_fu.cell(row=row, column=2, value=user)
                ws_fu.cell(row=row, column=3, value=count)
                row += 1

        ws_fu.column_dimensions['A'].width = 22
        ws_fu.column_dimensions['B'].width = 30
        ws_fu.column_dimensions['C'].width = 10

    # ===== Search by Website (Brand) Sheet =====
    if api_call_summary and api_call_summary.get('by_search_website'):
        ws_search = wb.create_sheet("Search by Website")

        ws_search['A1'] = f"Garment Search Count by Brand Website - {api_call_summary['date']}"
        ws_search['A1'].font = Font(bold=True, size=14)
        ws_search.merge_cells('A1:B1')

        headers = ['Website (Brand)', 'Search Calls']
        for col, h in enumerate(headers, 1):
            cell = ws_search.cell(row=3, column=col, value=h)
            cell.font = Font(bold=True)
            cell.fill = header_fill

        row = 4
        for website, count in sorted(api_call_summary['by_search_website'].items(), key=lambda x: -x[1]):
            ws_search.cell(row=row, column=1, value=website)
            ws_search.cell(row=row, column=2, value=count)
            row += 1

        ws_search.column_dimensions['A'].width = 35
        ws_search.column_dimensions['B'].width = 14

    # Save to bytes
    output = BytesIO()
    wb.save(output)
    output.seek(0)
    return output.getvalue()


def send_email_with_attachment(
    recipients: list,
    subject: str,
    body: str,
    attachment_data: bytes,
    attachment_filename: str
):
    """Send email with XLSX attachment."""
    from config import Config

    smtp_host = Config.SMTP_HOST
    smtp_port = Config.SMTP_PORT
    smtp_user = Config.SMTP_USER
    smtp_password = Config.SMTP_PASSWORD
    smtp_from = Config.SMTP_FROM or smtp_user

    if not smtp_user or not smtp_password:
        logger.error("SMTP credentials not configured (SMTP_USER/EMAIL_HOST_USER and SMTP_PASSWORD/EMAIL_HOST_PASSWORD)")
        raise ValueError("SMTP credentials not configured")

    msg = MIMEMultipart()
    msg['From'] = smtp_from
    msg['To'] = ', '.join(recipients)
    msg['Subject'] = subject

    msg.attach(MIMEText(body, 'plain'))

    # Attach XLSX
    part = MIMEBase('application', 'vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    part.set_payload(attachment_data)
    encoders.encode_base64(part)
    part.add_header('Content-Disposition', f'attachment; filename="{attachment_filename}"')
    msg.attach(part)

    # Send
    with smtplib.SMTP(smtp_host, smtp_port) as server:
        server.starttls()
        server.login(smtp_user, smtp_password)
        server.sendmail(smtp_from, recipients, msg.as_string())

    logger.info(f"Email sent to {recipients}")


def main():
    """Main entry point."""
    from config import Config

    logger.info("send_daily_analytics_report: Starting")

    # Get recipient emails
    recipients_str = Config.ANALYTICS_REPORT_EMAILS
    if not recipients_str:
        logger.error("ANALYTICS_REPORT_EMAILS environment variable not set")
        sys.exit(1)

    recipients = [e.strip() for e in recipients_str.split(',') if e.strip()]
    if not recipients:
        logger.error("No valid recipient emails")
        sys.exit(1)

    # Calculate date range (yesterday)
    yesterday = datetime.now() - timedelta(days=1)
    start_of_yesterday = yesterday.replace(hour=0, minute=0, second=0, microsecond=0)
    end_of_yesterday = yesterday.replace(hour=23, minute=59, second=59, microsecond=999999)

    # Get events
    events = get_events_since(start_of_yesterday)
    # Filter to only yesterday (in case script runs late)
    events = [e for e in events if e.get('created_at', '') <= end_of_yesterday.strftime('%Y-%m-%d %H:%M:%S')]

    summary = get_daily_summary(yesterday)
    api_call_summary = get_api_call_summary(yesterday)

    if not events and not api_call_summary.get('total_calls'):
        logger.info(f"No events or API calls for {yesterday.strftime('%Y-%m-%d')}, skipping report")
        return

    logger.info(f"Found {len(events)} events, {api_call_summary.get('total_calls', 0)} API calls for {yesterday.strftime('%Y-%m-%d')}")

    # Generate XLSX
    xlsx_data = generate_xlsx_report(events, summary, api_call_summary)
    filename = f"analytics_report_{yesterday.strftime('%Y-%m-%d')}.xlsx"

    # Build email body
    body_lines = [
        f"Analytics Report for {yesterday.strftime('%Y-%m-%d')}",
        "",
        "Summary:",
        f"  Total Events: {summary['total_events']}",
        ""
    ]

    for event_type, count in sorted(summary['by_type'].items(), key=lambda x: -x[1]):
        body_lines.append(f"  {event_type}: {count}")

    if api_call_summary.get('total_calls'):
        body_lines.extend([
            "",
            f"API Calls: {api_call_summary['total_calls']} (unique users: {api_call_summary['unique_users']})",
        ])
        for platform, count in sorted(api_call_summary['by_platform'].items(), key=lambda x: -x[1]):
            body_lines.append(f"  {platform}: {count}")

    body_lines.extend([
        "",
        "See attached XLSX for full details.",
        "",
        "---",
        "This is an automated report from BecauseFuture Analytics."
    ])

    body = '\n'.join(body_lines)
    subject = f"[BecauseFuture] Daily Analytics Report - {yesterday.strftime('%Y-%m-%d')}"

    # Send email
    try:
        send_email_with_attachment(recipients, subject, body, xlsx_data, filename)
    except Exception as e:
        logger.error(f"Failed to send email: {e}")
        sys.exit(1)

    # Wipe reported data
    deleted = delete_events_before(datetime.now() - timedelta(days=1))
    deleted_calls = delete_api_call_events_before(datetime.now() - timedelta(days=1))
    logger.info(f"Wiped {deleted} events and {deleted_calls} API calls after sending report")

    logger.info("send_daily_analytics_report: Complete")


if __name__ == '__main__':
    main()
