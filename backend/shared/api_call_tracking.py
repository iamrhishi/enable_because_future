"""
Lightweight per-request tracking for the "API calls per website / device /
user count" section of the daily analytics report.

Fires from a global before_request hook (see app.py) on every /api/* call,
unlike shared/analytics.track_event which only fires on curated business
events (login, tryon, etc).

Platform detection:
  - The mobile app sends X-Client-Platform: mobile on every request (see
    api_client.dart) - if present, trust it.
  - Otherwise, treat the call as web. If Origin or Referer is present, its
    host is the specific retailer site the browser extension is running on;
    if neither is present, it's still web, just with an unknown site.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Dict, List, Optional
from urllib.parse import urlparse

from flask import Request
from shared.database import db_manager
from shared.logger import logger


def _extract_host(url: Optional[str]) -> Optional[str]:
    if not url:
        return None
    try:
        host = urlparse(url).netloc
        return host or None
    except Exception:
        return None


def detect_platform_and_website(request: Request) -> tuple[str, Optional[str]]:
    """Returns (platform, website_domain). platform is 'mobile' or 'web'."""
    client_platform = (request.headers.get('X-Client-Platform') or '').strip().lower()
    if client_platform == 'mobile':
        return 'mobile', None

    website_domain = _extract_host(request.headers.get('Origin')) or \
        _extract_host(request.headers.get('Referer'))
    return 'web', website_domain


def log_api_call(request: Request, user_id: Optional[str] = None) -> None:
    """Best-effort log of one API call. Never raises - must not break requests."""
    try:
        platform, website_domain = detect_platform_and_website(request)
        ip_address = request.headers.get('X-Forwarded-For', request.remote_addr)

        db_manager.execute_query(
            """
            INSERT INTO api_call_events (path, method, user_id, platform, website_domain, ip_address)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (request.path, request.method, user_id, platform, website_domain, ip_address)
        )
    except Exception as e:
        logger.warning(f"api_call_tracking.log_api_call failed: {e}")


def get_api_call_events_since(since: datetime) -> List[Dict]:
    try:
        rows = db_manager.execute_query(
            """
            SELECT id, path, method, user_id, platform, website_domain, ip_address, created_at
            FROM api_call_events
            WHERE created_at >= ?
            ORDER BY created_at ASC
            """,
            (since.strftime('%Y-%m-%d %H:%M:%S'),),
            fetch_all=True
        )
        return [dict(row) for row in rows]
    except Exception as e:
        logger.error(f"api_call_tracking.get_api_call_events_since failed: {e}")
        return []


def get_api_call_summary(date: datetime = None) -> Dict:
    """Summary for a day: totals by platform, by website domain, and unique user count."""
    if date is None:
        date = datetime.now() - timedelta(days=1)

    start = date.replace(hour=0, minute=0, second=0, microsecond=0)
    end = date.replace(hour=23, minute=59, second=59, microsecond=999999)
    start_s = start.strftime('%Y-%m-%d %H:%M:%S')
    end_s = end.strftime('%Y-%m-%d %H:%M:%S')

    summary = {
        'date': date.strftime('%Y-%m-%d'),
        'total_calls': 0,
        'by_platform': {},
        'by_website': {},
        'unique_users': 0,
    }

    try:
        platform_rows = db_manager.execute_query(
            """SELECT platform, COUNT(*) as count FROM api_call_events
               WHERE created_at >= ? AND created_at <= ? GROUP BY platform ORDER BY count DESC""",
            (start_s, end_s), fetch_all=True
        )
        for row in platform_rows:
            summary['by_platform'][row['platform']] = row['count']
            summary['total_calls'] += row['count']

        website_rows = db_manager.execute_query(
            """SELECT website_domain, COUNT(*) as count FROM api_call_events
               WHERE created_at >= ? AND created_at <= ? AND website_domain IS NOT NULL
               GROUP BY website_domain ORDER BY count DESC""",
            (start_s, end_s), fetch_all=True
        )
        for row in website_rows:
            summary['by_website'][row['website_domain']] = row['count']

        user_row = db_manager.execute_query(
            """SELECT COUNT(DISTINCT user_id) as count FROM api_call_events
               WHERE created_at >= ? AND created_at <= ? AND user_id IS NOT NULL""",
            (start_s, end_s), fetch_one=True
        )
        summary['unique_users'] = user_row['count'] if user_row else 0

    except Exception as e:
        logger.error(f"api_call_tracking.get_api_call_summary failed: {e}")

    return summary


def delete_api_call_events_before(before: datetime) -> int:
    """Archive then delete api_call_events older than `before`. Mirrors
    shared/analytics.delete_events_before."""
    try:
        cutoff = before.strftime('%Y-%m-%d %H:%M:%S')

        count_row = db_manager.execute_query(
            "SELECT COUNT(*) as count FROM api_call_events WHERE created_at < ?",
            (cutoff,), fetch_one=True
        )
        count = count_row['count'] if count_row else 0

        try:
            db_manager.execute_query(
                """INSERT INTO api_call_events_archive
                   (path, method, user_id, platform, website_domain, ip_address, created_at)
                   SELECT path, method, user_id, platform, website_domain, ip_address, created_at
                   FROM api_call_events WHERE created_at < ?""",
                (cutoff,)
            )
        except Exception as archive_error:
            logger.warning(f"api_call_tracking.delete_api_call_events_before: Failed to archive (continuing with wipe): {archive_error}")

        db_manager.execute_query(
            "DELETE FROM api_call_events WHERE created_at < ?",
            (cutoff,)
        )

        logger.info(f"api_call_tracking.delete_api_call_events_before: Deleted {count} events before {before}")
        return count

    except Exception as e:
        logger.error(f"api_call_tracking.delete_api_call_events_before failed: {e}")
        return 0
