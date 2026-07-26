"""
Analytics event tracking for daily reporting.

Events are captured, reported daily via email (XLSX), then wiped.
On date change: automatically sends report for previous day(s), wipes old data.
"""

from __future__ import annotations

import json
import threading
from datetime import datetime, timedelta
from typing import Optional, Dict, List
from flask import request

from shared.database import db_manager
from shared.logger import logger

# Lock to prevent concurrent report sending
_report_lock = threading.Lock()
_last_report_check_date: Optional[str] = None


class EventType:
    """Standard event types for analytics."""
    LOGIN = 'login'
    LOGIN_FAILED = 'login_failed'
    LOGOUT = 'logout'
    SIGNUP = 'signup'
    DELETE_ACCOUNT = 'delete_account'
    PASSWORD_RESET_REQUEST = 'password_reset_request'
    PASSWORD_RESET_COMPLETE = 'password_reset_complete'
    PASSWORD_CHANGE = 'password_change'
    TRYON_START = 'tryon_start'
    TRYON_COMPLETE = 'tryon_complete'
    TRYON_FAILED = 'tryon_failed'
    WARDROBE_ADD = 'wardrobe_add'
    WARDROBE_DELETE = 'wardrobe_delete'
    WISHLIST_ADD = 'wishlist_add'
    WISHLIST_REMOVE = 'wishlist_remove'
    AVATAR_UPLOAD = 'avatar_upload'
    AVATAR_SAVED = 'avatar_saved'
    AVATAR_FAILED = 'avatar_failed'


def _check_and_send_daily_report():
    """
    Check if date changed since last event. If so, send report for previous day(s) and wipe.
    Called automatically before each event is tracked.
    """
    global _last_report_check_date

    today_str = datetime.now().strftime('%Y-%m-%d')

    # Skip if already checked today
    if _last_report_check_date == today_str:
        return

    # Use lock to prevent concurrent report sending
    if not _report_lock.acquire(blocking=False):
        return  # Another thread is handling it

    try:
        # Double-check after acquiring lock
        if _last_report_check_date == today_str:
            return

        # Get the last event date from database
        last_event = db_manager.execute_query(
            "SELECT DATE(created_at) as event_date FROM analytics_events ORDER BY created_at DESC LIMIT 1",
            fetch_one=True
        )

        if not last_event or not last_event.get('event_date'):
            _last_report_check_date = today_str
            return

        last_event_date = last_event['event_date']

        # If last event was from a previous day, send report
        if last_event_date < today_str:
            logger.info(f"analytics: Date changed from {last_event_date} to {today_str}, sending daily report")
            try:
                _send_daily_report_for_date(last_event_date)
            except Exception as e:
                logger.error(f"analytics: Failed to send daily report: {e}")

        _last_report_check_date = today_str

    finally:
        _report_lock.release()


def _send_daily_report_for_date(date_str: str):
    """Send daily analytics report for a specific date and wipe that data."""
    from config import Config

    recipients_str = Config.ANALYTICS_REPORT_EMAILS
    if not recipients_str:
        logger.warning("analytics: ANALYTICS_REPORT_EMAILS not configured, skipping report")
        return

    recipients = [e.strip() for e in recipients_str.split(',') if e.strip()]
    if not recipients:
        return

    report_date = datetime.strptime(date_str, '%Y-%m-%d')
    start_of_day = report_date.replace(hour=0, minute=0, second=0, microsecond=0)
    end_of_day = report_date.replace(hour=23, minute=59, second=59, microsecond=999999)

    # Get events for that day
    events = get_events_since(start_of_day)
    events = [e for e in events if e.get('created_at', '') <= end_of_day.strftime('%Y-%m-%d %H:%M:%S')]

    if not events:
        logger.info(f"analytics: No events for {date_str}, skipping report")
        # Still wipe old data
        delete_events_before(datetime.now().replace(hour=0, minute=0, second=0, microsecond=0))
        return

    summary = get_daily_summary(report_date)
    logger.info(f"analytics: Sending report for {date_str} with {len(events)} events")

    # Import send script functions
    try:
        from scripts.send_daily_analytics_report import generate_xlsx_report, send_email_with_attachment
    except ImportError as e:
        logger.error(f"analytics: Could not import report script: {e}")
        return

    # Generate and send
    xlsx_data = generate_xlsx_report(events, summary)
    filename = f"analytics_report_{date_str}.xlsx"

    body_lines = [
        f"Analytics Report for {date_str}",
        "",
        "Summary:",
        f"  Total Events: {summary['total_events']}",
        ""
    ]
    for event_type, count in sorted(summary['by_type'].items(), key=lambda x: -x[1]):
        body_lines.append(f"  {event_type}: {count}")
    body_lines.extend(["", "See attached XLSX for full details.", "", "---", "BecauseFuture Analytics"])
    body = '\n'.join(body_lines)
    subject = f"[BecauseFuture] Daily Analytics Report - {date_str}"

    send_email_with_attachment(recipients, subject, body, xlsx_data, filename)

    # Wipe reported data
    deleted = delete_events_before(datetime.now().replace(hour=0, minute=0, second=0, microsecond=0))
    logger.info(f"analytics: Report sent, wiped {deleted} old events")


def track_event(
    event_type: str,
    user_id: Optional[str] = None,
    user_email: Optional[str] = None,
    metadata: Optional[Dict] = None,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None
) -> bool:
    """
    Track an analytics event.

    Automatically checks if date changed and sends daily report before saving new event.

    Args:
        event_type: Type of event (use EventType constants)
        user_id: User ID if authenticated
        user_email: User email for reporting
        metadata: Additional event data (will be JSON serialized)
        ip_address: Client IP (auto-detected from request if not provided)
        user_agent: Client user agent (auto-detected from request if not provided)

    Returns:
        True if event was tracked successfully
    """
    try:
        # Check if date changed - send report if needed
        try:
            _check_and_send_daily_report()
        except Exception as e:
            logger.warning(f"analytics: Daily report check failed: {e}")
        # Auto-detect from Flask request context if available
        if ip_address is None:
            try:
                ip_address = request.headers.get('X-Forwarded-For', request.remote_addr)
            except RuntimeError:
                ip_address = None

        if user_agent is None:
            try:
                user_agent = request.headers.get('User-Agent', '')[:500]  # Limit length
            except RuntimeError:
                user_agent = None

        # Serialize metadata to JSON
        metadata_json = json.dumps(metadata) if metadata else None

        db_manager.execute_query(
            """
            INSERT INTO analytics_events
            (event_type, user_id, user_email, metadata, ip_address, user_agent)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (event_type, user_id, user_email, metadata_json, ip_address, user_agent)
        )

        logger.debug(f"analytics.track_event: {event_type} user_id={user_id}")
        return True

    except Exception as e:
        # Don't let analytics failures break the app
        logger.warning(f"analytics.track_event failed: {e}")
        return False


def get_events_since(since: datetime) -> List[Dict]:
    """
    Get all events since a given datetime.

    Args:
        since: Start datetime

    Returns:
        List of event dictionaries
    """
    try:
        rows = db_manager.execute_query(
            """
            SELECT id, event_type, user_id, user_email, metadata,
                   ip_address, user_agent, created_at
            FROM analytics_events
            WHERE created_at >= ?
            ORDER BY created_at ASC
            """,
            (since.strftime('%Y-%m-%d %H:%M:%S'),),
            fetch_all=True
        )

        events = []
        for row in rows:
            event = dict(row)
            # Parse metadata JSON
            if event.get('metadata'):
                try:
                    event['metadata'] = json.loads(event['metadata'])
                except:
                    pass
            events.append(event)

        return events

    except Exception as e:
        logger.error(f"analytics.get_events_since failed: {e}")
        return []


def get_daily_summary(date: datetime = None) -> Dict:
    """
    Get summary statistics for a day.

    Args:
        date: Date to summarize (default: yesterday)

    Returns:
        Summary dictionary with counts by event type
    """
    if date is None:
        from datetime import timedelta
        date = datetime.now() - timedelta(days=1)

    start = date.replace(hour=0, minute=0, second=0, microsecond=0)
    end = date.replace(hour=23, minute=59, second=59, microsecond=999999)

    try:
        rows = db_manager.execute_query(
            """
            SELECT event_type, COUNT(*) as count
            FROM analytics_events
            WHERE created_at >= ? AND created_at <= ?
            GROUP BY event_type
            ORDER BY count DESC
            """,
            (start.strftime('%Y-%m-%d %H:%M:%S'), end.strftime('%Y-%m-%d %H:%M:%S')),
            fetch_all=True
        )

        summary = {
            'date': date.strftime('%Y-%m-%d'),
            'total_events': 0,
            'by_type': {}
        }

        for row in rows:
            event_type = row['event_type']
            count = row['count']
            summary['by_type'][event_type] = count
            summary['total_events'] += count

        return summary

    except Exception as e:
        logger.error(f"analytics.get_daily_summary failed: {e}")
        return {'date': date.strftime('%Y-%m-%d'), 'total_events': 0, 'by_type': {}}


def delete_events_before(before: datetime) -> int:
    """
    Delete events before a given datetime.

    Args:
        before: Delete events older than this

    Returns:
        Number of events deleted
    """
    try:
        cutoff = before.strftime('%Y-%m-%d %H:%M:%S')

        # Get count first
        count_row = db_manager.execute_query(
            "SELECT COUNT(*) as count FROM analytics_events WHERE created_at < ?",
            (cutoff,),
            fetch_one=True
        )
        count = count_row['count'] if count_row else 0

        # Archive before deleting - the dashboard needs full history, but this
        # table gets wiped daily after the email report goes out.
        try:
            db_manager.execute_query(
                """INSERT INTO analytics_events_archive
                   (event_type, user_id, user_email, metadata, ip_address, user_agent, created_at)
                   SELECT event_type, user_id, user_email, metadata, ip_address, user_agent, created_at
                   FROM analytics_events WHERE created_at < ?""",
                (cutoff,)
            )
        except Exception as archive_error:
            logger.warning(f"analytics.delete_events_before: Failed to archive events (continuing with wipe): {archive_error}")

        # Delete
        db_manager.execute_query(
            "DELETE FROM analytics_events WHERE created_at < ?",
            (cutoff,)
        )

        logger.info(f"analytics.delete_events_before: Deleted {count} events before {before}")
        return count

    except Exception as e:
        logger.error(f"analytics.delete_events_before failed: {e}")
        return 0
